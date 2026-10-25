"""Knowledge about the MIUI gates that block adb on stock MIUI 12 builds.

Everything in this module was established by reading the decompiled MIUI
applications on a Redmi Note 5 (whyred, Android 9, MIUI 12 V12.0.2.0.PEIMIXM):

* ``com.android.settings`` — the developer-options preference controllers.
* ``com.miui.securitycenter`` — the permission/install centre.

The values are intentionally kept in one place so the tool never hard-codes
them deeper in the code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

# ---------------------------------------------------------------------------
# Where MIUI keeps the two developer options
# ---------------------------------------------------------------------------

#: "Отладка по USB (Настройки безопасности)" — MIUI mirrors this preference into
#: a system property; system_server reads the property to decide whether an adb
#: session may inject events / grant permissions.
PROPERTY_ADB_INPUT = "persist.security.adbinput"

#: "Установка через USB" — MIUI keeps the preference in its own store and mirrors
#: it into a second property.
PROPERTY_ADB_INSTALL = "persist.security.adbinstall"

#: The MIUI preference behind "Установка через USB". It is written through the
#: provider ``content://com.miui.securitycenter.remoteprovider`` (method
#: ``callPreference``, bundle ``{type: 1, key: ..., value: ...}``), which is
#: protected by a signature|privileged permission held by uid 1000 only.
PREFERENCE_ADB_INSTALL = "security_adb_install_enable"

#: The provider that owns MIUI's own preference store.
REMOTE_PREFERENCE_PROVIDER = "content://com.miui.securitycenter.remoteprovider"

#: The endpoint MIUI calls to verify the device before it enables the options.
#: Without a reachable network the verification fails with the toast
#: "Подключитесь к сети и повторите попытку" ("Connect to the network and try again").
VERIFICATION_ENDPOINT = "srv.sec.miui.com"

#: Verification endpoint path (both the global and the international build).
VERIFICATION_PATH = "/data/adb"


# ---------------------------------------------------------------------------
# UI targets
# ---------------------------------------------------------------------------

#: The Settings activity that hosts the MIUI developer-options dashboard.
SETTINGS_ACTIVITY = "com.android.settings/.Settings$DevelopmentSettingsDashboardActivity"

#: The Wi-Fi settings activity (explicit component: the implicit action may be
#: delivered to an already running top-most instance instead of opening the screen).
WIFI_ACTIVITY = "com.android.settings/.Settings$WifiSettingsActivity"


@dataclass(frozen=True)
class Target:
    """One developer option MIUI gates behind its own verification."""

    key: str
    title: str
    #: Label of the row in the developer-options list.
    row: str
    #: Human readable reason why a plain adb call cannot do it.
    why_locked: str
    #: Whether MIUI additionally demands a Xiaomi account for this option.
    needs_account: bool
    #: How the state can be verified from a shell after the option is on.
    check: str


TARGETS: Dict[str, Target] = {
    "security-debugging": Target(
        key="security-debugging",
        title="Отладка по USB (Настройки безопасности)",
        row="Отладка по USB (Настройки безопасности)",
        why_locked=(
            "state lives in the system property " + PROPERTY_ADB_INPUT
            + ", writable only by uid 1000"
        ),
        needs_account=False,
        check="getprop " + PROPERTY_ADB_INPUT,
    ),
    "install-over-usb": Target(
        key="install-over-usb",
        title="Установка через USB",
        row="Установка через USB",
        why_locked=(
            "state lives in the MIUI preference " + PREFERENCE_ADB_INSTALL
            + " behind a signature|privileged provider"
        ),
        needs_account=True,
        check="getprop " + PROPERTY_ADB_INSTALL,
    ),
}


# ---------------------------------------------------------------------------
# What MIUI blocks for the adb identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Gate:
    """One capability MIUI removes from the shell identity."""

    key: str
    title: str
    probe: str
    expect_ok: bool
    note: str = ""


#: Probes used by ``doctor``. Each one is a single adb call that is allowed to
#: fail; the tool reports the outcome instead of aborting.
GATES: List[Gate] = [
    Gate(
        key="secure-settings",
        title="settings put secure/global",
        probe="settings put secure miui_adb_unlock_probe 1",
        expect_ok=True,
        note="MIUI blocks WRITE_SECURE_SETTINGS for uid 2000 even though the shell "
        "package declares it",
    ),
    Gate(
        key="grant-permission",
        title="pm grant",
        probe="pm grant com.android.shell android.permission.WRITE_SECURE_SETTINGS",
        expect_ok=True,
        note="MIUI blocks GRANT_RUNTIME_PERMISSIONS for uid 2000",
    ),
    Gate(
        key="input-injection",
        title="input tap",
        probe="input tap 1 1",
        expect_ok=True,
        note="events are accepted by the server and then dropped by MIUI's filter",
    ),
    Gate(
        key="device-owner",
        title="dpm set-device-owner",
        probe="dpm remove-active-admin --user 0 com.android.shell/.NotAnAdmin",
        expect_ok=True,
        note="MANAGE_DEVICE_ADMINS is blocked for uid 2000",
    ),
    Gate(
        key="properties",
        title="setprop persist.*",
        probe="setprop persist.miui_adb_unlock_probe 1",
        expect_ok=True,
        note="SELinux denies property writes for the shell domain",
    ),
    Gate(
        key="install",
        title="adb install",
        probe=None,
        expect_ok=True,
        note="package installation itself is not blocked",
    ),
]


#: The adb capabilities that come back once "Отладка по USB (Настройки
#: безопасности)" is enabled. Each entry is a probe command that must succeed.
CAPABILITY_PROBES: List[Gate] = [
    Gate(
        key="secure-settings",
        title="settings put secure",
        probe="settings put secure miui_adb_unlock_probe 1",
        expect_ok=True,
    ),
    Gate(
        key="grant-permission",
        title="pm grant",
        probe="pm grant com.android.shell android.permission.WRITE_SECURE_SETTINGS",
        expect_ok=True,
    ),
    Gate(
        key="input-injection",
        title="input tap",
        probe="input tap 1 1",
        expect_ok=True,
    ),
]
