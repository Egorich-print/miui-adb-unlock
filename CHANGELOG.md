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
