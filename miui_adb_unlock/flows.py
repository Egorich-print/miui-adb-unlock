"""High level flows: diagnose the device and flip the gated developer options."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List, Optional

from .adb import Adb, AdbError
from .driver import Driver, DriverResult
from .gates import (
    CAPABILITY_PROBES,
    GATES,
    PROPERTY_ADB_INPUT,
    PROPERTY_ADB_INSTALL,
    SETTINGS_ACTIVITY,
    TARGETS,
    VERIFICATION_ENDPOINT,
    WIFI_ACTIVITY,
)

#: Flags needed so an explicit component opens the screen instead of being
#: delivered to an already running top-most instance.
FLAG_CLEAR_TASK = "0x10008000"


@dataclass
class Report:
    """A single diagnostic line."""

    name: str
    state: str
    detail: str = ""

    def __str__(self) -> str:
        suffix = f" — {self.detail}" if self.detail else ""
        return f"[{self.state:>7}] {self.name}{suffix}"


class Unlocker:
    """Drives the whole "flip a gated MIUI developer option" procedure."""

    def __init__(self, adb: Adb, driver: Driver, verbose: bool = False) -> None:
        self.adb = adb
        self.driver = driver
        self.verbose = verbose

    # -- helpers -----------------------------------------------------------

    def _log(self, message: str) -> None:
        if self.verbose:
            print(f"  · {message}")

    def _open_settings(self, component: str) -> None:
        self.adb.shell(f"am start -n {component} -f {FLAG_CLEAR_TASK}")
        time.sleep(4)

    def _focus(self) -> str:
        return self.adb.shell("dumpsys window | grep -m1 mCurrentFocus").stdout.strip()

    def _has_internet(self) -> bool:
        result = self.adb.shell(f"ping -c1 -W3 {VERIFICATION_ENDPOINT}")
        return "bytes from" in result.output

    # -- doctor ------------------------------------------------------------

    def doctor(self) -> List[Report]:
        """Collects a report about the device and the gates that are active."""
        reports: List[Report] = []

        model = self.adb.getprop("ro.product.model")
        device = self.adb.getprop("ro.product.device")
        release = self.adb.getprop("ro.build.version.release")
        miui = self.adb.getprop("ro.miui.ui.version.name")
        incremental = self.adb.getprop("ro.build.version.incremental")
        reports.append(
            Report(
                "device",
                "ok" if model else "fail",
                f"{model} ({device}) · Android {release} · MIUI {miui} {incremental}",
            )
        )

        for gate in GATES:
            if gate.probe is None:
                reports.append(Report(gate.title, "n/a", gate.note))
                continue
            result = self.adb.shell(gate.probe)
            blocked = "SecurityException" in result.output or "Permission denial" in result.output
            failed = not result.ok
            if blocked or failed:
                reports.append(Report(gate.title, "blocked", gate.note))
            else:
                reports.append(Report(gate.title, "open", gate.note))

        adb_input = self.adb.getprop(PROPERTY_ADB_INPUT)
        reports.append(
            Report(
                "security-debugging option",
                "on" if adb_input == "1" else "off",
                f"{PROPERTY_ADB_INPUT}={adb_input or '<unset>'}",
            )
        )
        adb_install = self.adb.getprop(PROPERTY_ADB_INSTALL)
        reports.append(
            Report(
                "install-over-usb option",
                "on" if adb_install == "1" else "off",
                f"{PROPERTY_ADB_INSTALL}={adb_install or '<unset>'}",
            )
        )

        reports.append(
            Report(
                "device internet",
                "yes" if self._has_internet() else "no",
                "MIUI verifies the device against " + VERIFICATION_ENDPOINT
                + " before enabling the options",
            )
        )

        probe = self.driver.run("dump")
        reports.append(
            Report(
                "accessibility channel",
                "ok" if probe.ok else "fail",
                "uiautomator harness: " + probe.message,
            )
        )
        return reports

    # -- unlock ------------------------------------------------------------

    def unlock(self, target_key: str) -> List[Report]:
        """Flips one of the gated developer options."""
        target = TARGETS[target_key]
        reports: List[Report] = []

        if not self._has_internet():
            reports.append(
                Report(
                    "prerequisite",
                    "fail",
                    "the device has no internet; MIUI's verification "
                    + VERIFICATION_ENDPOINT
                    + " cannot succeed offline",
                )
            )
            return reports
        reports.append(Report("prerequisite", "ok", "device is online"))

        self._open_settings(SETTINGS_ACTIVITY)
        focus = self._focus()
        if "DeveloperSettings" not in focus and "DevelopmentSettings" not in focus:
            reports.append(Report("open developer options", "fail", focus))
            return reports
        reports.append(Report("open developer options", "ok", focus))

        click = self.driver.click(target.row)
        self._log("row click: " + click.message)
        if not click.ok:
            reports.append(Report("click the option", "fail", click.message))
            return reports
        reports.append(Report("click the option", "ok", target.row))

        time.sleep(3)
        focus = self._focus()
        reports.append(Report("MIUI verification", "ok", focus))

        confirm = self.driver.click_id("android:id/button1")
        self._log("confirm click: " + confirm.message)
        time.sleep(3)

        value = self.adb.getprop(
            PROPERTY_ADB_INPUT if target_key == "security-debugging" else PROPERTY_ADB_INSTALL
        )
        if value == "1":
            reports.append(Report("option state", "on", target.title))
        else:
            reports.append(
                Report(
                    "option state",
                    "off",
                    target.title + " is still off (" + target.why_locked + ")",
                )
            )
        return reports

    # -- verify ------------------------------------------------------------

    def verify(self) -> List[Report]:
        """Checks whether the adb capabilities came back."""
        reports: List[Report] = []
        for probe in CAPABILITY_PROBES:
            result = self.adb.shell(probe.probe)
            blocked = "SecurityException" in result.output or "Permission denial" in result.output
            reports.append(
                Report(probe.title, "blocked" if blocked or not result.ok else "open")
            )
        return reports

    # -- wifi --------------------------------------------------------------

    def wifi(self, ssid: str, password: Optional[str]) -> List[Report]:
        """Connects the device to a Wi-Fi network through the Settings UI."""
        reports: List[Report] = []
        self._open_settings(WIFI_ACTIVITY)
        reports.append(Report("open wi-fi settings", "ok", self._focus()))

        detail = self.driver.detail(ssid)
        if not detail.ok:
            detail = self.driver.click(ssid)
        self._log("network click: " + detail.message)
        if not detail.ok:
            reports.append(Report("select network", "fail", detail.message))
            return reports
        reports.append(Report("select network", "ok", ssid))

        time.sleep(2)
        if password:
            typed = self.driver.type_text(password)
            self._log("password field: " + typed.message)
            if not typed.ok:
                reports.append(Report("type password", "fail", typed.message))
                return reports
            reports.append(Report("type password", "ok", f"{len(password)} characters"))

        confirm = self.driver.click_id("android:id/button1")
        self._log("connect click: " + confirm.message)
        time.sleep(8)

        connected = self.adb.shell("dumpsys wifi | grep -m1 mWifiInfo").stdout
        online = "bytes from" in self.adb.shell(f"ping -c1 -W3 {VERIFICATION_ENDPOINT}").output
        state = "online" if online else ("connected" if "Ultra_Wi-Fi" in connected else "off")
        reports.append(Report("wi-fi", state, connected.strip()))
        return reports
