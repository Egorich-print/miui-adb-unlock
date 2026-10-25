# miui-adb-unlock — Status

> Updated: 2026-10-25
> Living detail: `docs/STATE.md`

## State: Prototype

### Works

- `doctor` — reports the device identity and which MIUI gates are active
  (verified on Redmi Note 5, MIUI 12 V12.0.2.0.PEIMIXM).
- `dump` — prints the accessibility tree of the active screen through the
  on-device driver.
- Accessibility driver — clicks, scrolls and types through
  `AccessibilityNodeInfo.performAction()`, working where input injection is
  blocked (verified: the click on *USB debugging (security settings)* opens
  `com.miui.securitycenter/…/AdbInstallVerifyActivity`).
- `unlock security-debugging` — reaches MIUI's verification dialog. The option
  itself flips only when the device can reach `srv.sec.miui.com`.

### Does not work

- `unlock install-over-usb` — MIUI demands a signed-in Xiaomi account for this
  option; without it the option stays off. Not a tool limitation.
- The unlock flow on a device without internet — MIUI's verification fails with
  the toast "Connect to the network and try again".

### Known limitations

- Verified on one device family (Redmi Note 5 / MIUI 12). Other MIUI builds use
  different labels and verification endpoints; the targets live in
  `miui_adb_unlock/gates.py` and are the first thing to adjust.
- The driver needs the stock `uiautomator` harness on the device (present on
  every stock MIUI build).
- The Wi-Fi helper clicks MIUI's own screens; it cannot rewrite a Wi-Fi profile
  that MIUI stored with the wrong security type (the framework refuses
  `addNetwork`/`removeNetwork` for unprivileged apps).
