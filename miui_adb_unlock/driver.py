"""Client for the on-device accessibility driver.

The driver itself is a Java class that runs inside the stock ``uiautomator runtest``
harness on the phone (see ``harness/``). This module pushes it, feeds it one
command at a time and parses the single result line it prints.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .adb import Adb, AdbError

JAR_NAME = "miui-a11y.jar"
REMOTE_JAR = "/data/local/tmp/" + JAR_NAME
REMOTE_COMMAND = "/data/local/tmp/miui_a11y_cmd.txt"
DRIVER_CLASS = "com.miuiadblock.A11yDriver"
RESULT_RE = re.compile(r"^\[miui-a11y\]\s+(OK|ERR)\s*(.*)$", re.MULTILINE)
TRACE_RE = re.compile(r"^\[miui-a11y\]\s+TRACE\s+(.*)$", re.MULTILINE)


@dataclass
class DriverResult:
    ok: bool
    message: str
    trace: List[str]
    raw: str

    def __str__(self) -> str:  # pragma: no cover - convenience only
        return ("OK " if self.ok else "ERR ") + self.message


class Driver:
    """Drives the on-device accessibility driver."""

    def __init__(self, adb: Adb, jar: Optional[Path] = None, retries: int = 3) -> None:
        self.adb = adb
        self.jar = jar or self._default_jar()
        self.retries = retries
        self._pushed = False

    @staticmethod
    def _default_jar() -> Path:
        return Path(__file__).resolve().parent.parent / "harness" / JAR_NAME

    # -- harness lifecycle -------------------------------------------------

    def ensure_harness(self) -> None:
        """Pushes the driver jar to the device (idempotent)."""
        if self._pushed:
            return
        if not self.jar.exists():
            raise AdbError(
                f"driver jar not found: {self.jar}\n"
                "Build it with scripts/build-harness.sh (needs the Android SDK)."
            )
        result = self.adb.push(str(self.jar), REMOTE_JAR)
        if not result.ok:
            raise AdbError("cannot push the driver jar:\n" + result.output)
        self.adb.shell(f"chmod 755 {REMOTE_JAR}")
        self._pushed = True

    def kill_stale(self) -> None:
        """Kills leftover harness processes.

        Android allows a single ``UiAutomation`` client at a time; a harness
        process that did not exit cleanly keeps the service registered and the
        next run fails with "already registered".
        """
        self.adb.shell("pkill -f uiautomator")

    # -- commands ----------------------------------------------------------

    def run(self, command: str, retries: Optional[int] = None) -> DriverResult:
        """Runs one driver command and returns its result."""
        attempts = self.retries if retries is None else retries
        last: Optional[DriverResult] = None
        for attempt in range(attempts):
            self.ensure_harness()
            self.kill_stale()
            self.adb.shell(f"printf '%s' {self._quote(command)} > {REMOTE_COMMAND}")
            raw = self.adb.shell(
                f"uiautomator runtest {REMOTE_JAR} -e class {DRIVER_CLASS}",
                timeout=180,
            ).output
            result = self._parse(raw)
            last = result
            if result.ok:
                return result
            # A stale harness or an unsettled screen is worth one more attempt.
            if "not-found" in result.message or "no-root" in result.message:
                return result
        assert last is not None
        return last

    def click(self, text: str) -> DriverResult:
        return self.run(f"click {text}")

    def click_contains(self, text: str) -> DriverResult:
        return self.run(f"clickcontains {text}")

    def click_id(self, resource_id: str) -> DriverResult:
        return self.run(f"clickid {resource_id}")

    def detail(self, text: str) -> DriverResult:
        return self.run(f"detail {text}")

    def long_click(self, text: str) -> DriverResult:
        return self.run(f"long {text}")

    def type_text(self, value: str) -> DriverResult:
        return self.run(f"text {value}")

    def dump(self) -> List[str]:
        """Returns the accessibility tree of the active window."""
        self.ensure_harness()
        self.kill_stale()
        self.adb.shell(f"printf '%s' 'dump' > {REMOTE_COMMAND}")
        raw = self.adb.shell(
            f"uiautomator runtest {REMOTE_JAR} -e class {DRIVER_CLASS}",
            timeout=180,
        ).output
        return [line for line in raw.splitlines() if "class=" in line]

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _parse(raw: str) -> DriverResult:
        trace = TRACE_RE.findall(raw)
        matches = RESULT_RE.findall(raw)
        if not matches:
            return DriverResult(False, "no result line from the driver", trace, raw)
        status, message = matches[-1]
        return DriverResult(status == "OK", message.strip(), trace, raw)

    @staticmethod
    def _quote(value: str) -> str:
        return "'" + value.replace("'", "'\\''") + "'"
