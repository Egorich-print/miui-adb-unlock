# ADR-001 — Use accessibility actions instead of input injection

* Status: Accepted
* Date: 2026-10-25

## Context

MIUI 12 removes the ability to inject input events from the adb identity:
`InputManager.injectInputEvent()` accepts the call and the event is then dropped
by a filter inside `system_server`. The same hardening removes
`WRITE_SECURE_SETTINGS`, `GRANT_RUNTIME_PERMISSIONS` and `MANAGE_DEVICE_ADMINS`
for uid 2000.

The two developer options that would restore those capabilities are themselves
gated behind MIUI's verification, which needs a signed-in Xiaomi account and a
reachable network.

Everything else that was tried — raw `sendevent`, `uhid`, a third-party app with
privileged permissions, an instrumentation targeting the framework — was closed
by the platform or by the vendor.

One channel stayed open: the **stock `uiautomator` harness**. It connects to the
accessibility service as the `uiautomator` client and may act on any window.
Accessibility actions are dispatched by the accessibility service, not by the
input pipeline, so MIUI's input filter does not see them.

## Decision

The tool drives the MIUI Settings UI through
`AccessibilityNodeInfo.performAction(ACTION_CLICK / ACTION_SCROLL_FORWARD /
ACTION_SET_TEXT)` executed by a small Java driver inside the stock
`uiautomator runtest` harness.

Consequences accepted:

* the driver depends on the stock `uiautomator` harness being present on the
  device (true for every stock MIUI build);
* the driver must work around a screen that never goes idle, so it enumerates
  accessibility windows and shortens the idle timeout;
* coordinate-based automation is abandoned entirely — it is blocked by the
  vendor and unreliable on a device with a damaged digitiser.

## Alternatives rejected

| Alternative | Why not |
|---|---|
| `input tap` / `UiDevice.click()` | routed through `injectInputEvent`, dropped by MIUI |
| `sendevent` on `/dev/input/event*` | the shell is not in the `input` group |
| a virtual HID device through `/dev/uhid` | no HID driver in the kernel, every ioctl answers `ENOTTY` |
| an own APK with `WRITE_SECURE_SETTINGS` | signature\|privileged, cannot be held by a third-party app |
| instrumentation with `targetPackage="android"` | PMS requires the target to be signed with the same certificate; the platform key is Xiaomi's |
| writing `persist.security.adbinput` with `setprop` | SELinux denies property writes for the shell domain |
| editing the Wi-Fi/system configuration files | needs root; `/data/misc` is not readable by the shell |

## Consequences

* The tool can flip the options MIUI gates, as long as the device can pass
  MIUI's own verification.
* It is honest about the remaining gate: *Install over USB* additionally needs a
  Xiaomi account, and that is a vendor rule, not a tool limitation.
* The privileged knowledge (property names, provider, endpoint, labels) is
  isolated in `miui_adb_unlock/gates.py` so that a different MIUI build only
  requires editing that file.
