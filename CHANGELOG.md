# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Semver tags on releases.

## [0.1.0] — 2026-10-25

### Added

- `doctor` command: reports device identity, active MIUI gates and whether the
  device can pass MIUI's online verification.
- `unlock` command: drives the developer-options UI through accessibility
  actions to enable *USB debugging (security settings)*.
- `verify` command: probes whether the adb capabilities came back.
- `wifi` command: connects the device to a network through MIUI's Wi-Fi screen
  without exposing the password on the command line.
- `dump` command: prints the accessibility tree of the active screen.
- On-device accessibility driver (`harness/`): click, scroll, type, dump.
- Fixes found while running the flow against a real device: the Settings
  component name is quoted (the device shell expanded `$` in the inner class and
  started the crashing drawer instead), MIUI's crash dialog is dismissed and the
  Settings process is started on a sub-settings screen first, because the drawer
  of this build cannot inflate `android.support.v7.widget.CardView`.
- The driver now searches every accessibility window (MIUI's warning dialog lives
  in its own window) and prints the package name in the dump.
- The unlock flow clicks MIUI's multi-step warning dialog
  (`com.miui.securitycenter:id/accept`) until the option is really enabled, and
  the `wifi` command clicks the network name instead of the "⋮" button.
