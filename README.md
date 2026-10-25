# miui-adb-unlock

**Enable the MIUI developer options that stock MIUI 12 blocks for the adb identity — without a Xiaomi account.**

[English](README.md) · [Русский](README.ru.md)

Xiaomi's MIUI 12 removes a set of capabilities from every adb session: you cannot
inject input events, cannot grant runtime permissions, cannot write
`Settings.Secure`, cannot set system properties, cannot become device owner.
The two developer options that would restore them — *USB debugging (security
settings)* and *Install over USB* — are themselves gated behind a vendor
verification that needs a signed-in Xiaomi account and a reachable network.

This tool flips those two options on a device you own, using the one channel MIUI
does not close: **accessibility actions**. It drives the stock `uiautomator`
harness on the phone and clicks the settings for you — no root, no modified
system image.

Measured on a Redmi Note 5 / MIUI 12: the click reaches MIUI's own verification,
and the vendor answers **"Sign in with your Mi Account"** — on this build *both*
options require a Mi Account sign-in, the online check alone is not enough. The
tool automates everything up to that point; the account is a vendor rule that no
amount of automation removes.

```
$ miui-adb-unlock doctor
[     ok] device — Redmi Note 5 (whyred) · Android 9 · MIUI V12 V12.0.2.0.PEIMIXM
[blocked] settings put secure/global — MIUI blocks WRITE_SECURE_SETTINGS for uid 2000 …
[blocked] pm grant — MIUI blocks GRANT_RUNTIME_PERMISSIONS for uid 2000
[blocked] input tap — events are accepted by the server and then dropped by MIUI's filter
[blocked] dpm set-device-owner — MANAGE_DEVICE_ADMINS is blocked for uid 2000
[blocked] setprop persist.* — SELinux denies property writes for the shell domain
[    off] security-debugging option — persist.security.adbinput=<unset>
[    off] install-over-usb option — persist.security.adbinstall=<unset>
[     no] device internet — MIUI verifies the device against srv.sec.miui.com …
[     ok] accessibility channel — uiautomator harness: dump
```

---

## Why the obvious approaches fail

MIUI 12 patches the checks in `system_server`, so the shell identity loses
capabilities that the shell package still *declares*:

| Operation | Result on MIUI 12 |
|---|---|
| `settings put secure/global …` | `SecurityException: … WRITE_SECURE_SETTINGS` |
| `pm grant`, `adb install -g` | `SecurityException` (`GRANT_RUNTIME_PERMISSIONS`) |
| `dpm set-device-owner` | `SecurityException` (`MANAGE_DEVICE_ADMINS`) |
| `input tap`, `input keyevent` | accepted by the server, then dropped by MIUI's filter |
| `setprop persist.*` | denied by SELinux (even `persist.sys.*`) |
| `/dev/input/event*` | `Permission denied` (group `input`) |
| `/dev/uhid` | no HID driver in the kernel |
| instrumentation with `targetPackage="android"` | dropped by PMS (target must share the signature) |
| signing with the platform key | Xiaomi's own key (`release-keys`, `CN=MIUI`), not the public AOSP test key |
| `adb root`, `su` | refused (production build) |

The details, with the exact code paths in the MIUI applications, are in
[`docs/research/miui-security-gates.md`](docs/research/miui-security-gates.md).

## What the options actually are

| UI option | Where the state lives | Who may write it |
|---|---|---|
| USB debugging (security settings) | system property `persist.security.adbinput` | uid 1000 (`android.uid.system`) only |
| Install over USB | MIUI preference `security_adb_install_enable`, mirrored into `persist.security.adbinstall` | uid 1000, through a `signature\|privileged` provider |

MIUI's own way of enabling them is
`com.android.settings.development.c` → `AdbInputApplyActivity` →
`AdbInstallVerifyActivity` → an HTTPS request to `srv.sec.miui.com/data/adb`.

Two gates were measured on the device:

* **offline** — the request is never made, MIUI shows the toast
  *"Подключитесь к сети и повторите попытку"*;
* **online** — the request goes out and the server rejects it with
  *"Sign in with your Mi Account"*, because the payload carries an empty
  `xiaomi_id` (no account is signed in).

With a Mi Account signed in, `AdbInputApplyActivity` takes a different branch and
shows a local dialog that sets the property without contacting the server.

## How this tool works

MIUI blocks `InputManager.injectInputEvent()` for the shell, but it does **not**
block accessibility actions. The stock `uiautomator` harness works on the device,
so the tool:

1. pushes a small Java driver to `/data/local/tmp`;
2. asks it to find the developer-options row and `performAction(ACTION_CLICK)`;
3. confirms MIUI's own verification dialog with the same mechanism;
4. verifies the resulting state (`getprop persist.security.adbinput`).

Accessibility actions are dispatched by the accessibility service, not by the
input pipeline, so MIUI's input filter never sees them. A side benefit: the tool
keeps working on devices with a damaged digitiser, where phantom touches make
coordinate-based tapping unreliable.

The driver also has to cope with two MIUI quirks that are handled for you:

* the Settings list never becomes *idle*, so `getRootInActiveWindow()` times out —
  the driver enumerates accessibility windows instead and shortens the idle wait;
* a stale harness process keeps the `UiAutomation` service registered, so every
  run kills leftovers first.

## Requirements

* `adb` with the device connected and **USB debugging enabled** (this part is not
  blocked by MIUI).
* The device must reach `srv.sec.miui.com` for MIUI's verification to pass.
* Python 3.9+ on the host. No third-party Python packages.
* The driver jar is shipped pre-built; rebuilding it needs the Android SDK
  (see [`scripts/build-harness.sh`](scripts/build-harness.sh)).

## Install

```shell
git clone https://github.com/Egorich-print/miui-adb-unlock
cd miui-adb-unlock
python3 -m pip install -e .        # or: python3 -m miui_adb_unlock
```

Running from a checkout without installing works too:

```shell
python3 -m miui_adb_unlock doctor
```

## Usage

```shell
# 1. What is blocked on this device right now?
miui-adb-unlock doctor

# 2. Enable "USB debugging (security settings)".
#    Needs the device online; no Xiaomi account required.
miui-adb-unlock unlock security-debugging

# 3. Confirm the adb capabilities came back.
miui-adb-unlock verify

# 4. "Install over USB" — MIUI asks for a Xiaomi account for this one.
miui-adb-unlock unlock install-over-usb

# 5. Bring the device online (if it is not).
MIUI_WIFI_PASSWORD='…' miui-adb-unlock wifi 'MyNetwork'

# 6. Inspect the accessibility tree of the current screen.
miui-adb-unlock dump
```

Use `--serial <serial>` when several devices are connected, and `-v` to see the
driver traces.

### Passwords

Passwords are never stored and never logged. The `wifi` command reads the
password from an environment variable (`MIUI_WIFI_PASSWORD` by default) and
passes it to the device in a single accessibility action. Keep it in your shell
history-free environment:

```shell
read -rs MIUI_WIFI_PASSWORD && export MIUI_WIFI_PASSWORD
miui-adb-unlock wifi 'Ultra_Wi-Fi_2.0'
unset MIUI_WIFI_PASSWORD
```

## What it changes on the device

* the developer option you asked for (a MIUI preference and/or a system property);
* `/data/local/tmp/miui-a11y.jar` and `/data/local/tmp/miui_a11y_cmd.txt` (harness);
* nothing else. No app is installed, no system partition is touched, no account
  is created.

## Documentation map

| Need | File |
|---|---|
| Current state | [STATUS.md](STATUS.md) |
| What to do next | [docs/STATE.md](docs/STATE.md) |
| Architecture | [docs/architecture/overview.md](docs/architecture/overview.md) |
| Decisions | [docs/adr/](docs/adr/) |
| Reverse engineering of the gates | [docs/research/miui-security-gates.md](docs/research/miui-security-gates.md) |
| Repository layout rules | [docs/REPOSITORY_GUIDE.md](docs/REPOSITORY_GUIDE.md) |
| Rules for agents | [AGENTS.md](AGENTS.md) |
| Change history | [CHANGELOG.md](CHANGELOG.md) |

## Legal and safety

Use this only on devices you own or are authorised to administer. It enables
options that the vendor deliberately restricted; some of them weaken the
device's protection against a malicious host computer. It does not bypass
Android's security model, does not need root, and does not touch the system
partition.

## License

MIT — see [LICENSE](LICENSE).
