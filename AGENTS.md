# AGENTS.md — contract for coding agents

> Read this before changing anything in this repository.

## What this project is

`miui-adb-unlock` enables the MIUI developer options that MIUI 12 blocks for the
adb identity, by driving the Settings UI through accessibility actions instead of
input injection.

## Source of truth

| Question | File |
|---|---|
| How the tool behaves | `miui_adb_unlock/` (code) |
| What MIUI calls things | `miui_adb_unlock/gates.py` |
| What is verified to work | `STATUS.md` |
| What to do next | `docs/STATE.md` |
| Why a decision was taken | `docs/adr/` |
| Evidence for the MIUI claims | `docs/research/miui-security-gates.md` |

Never duplicate a MIUI-specific string outside `gates.py`.

## Rules

1. **Verify before claiming.** A statement about the device is only made after a
   command on a real device produced it. Record the command and the output in
   `docs/research/` when a new claim is added.
2. **One logical change — one commit.** Prefixes: `feat:`, `fix:`, `docs:`,
   `chore:`, `refactor:`, `test:`. Commit only with the user's permission.
3. **No secrets.** Wi-Fi passwords come from an environment variable. Never
   commit them, never log them, never put them in an issue or a doc.
4. **The harness jar is a build artifact.** `harness/miui-a11y.jar` is committed
   so that users need no Android SDK; rebuild it with
   `scripts/build-harness.sh` after every change under `harness/`.
5. **Do not weaken the checks.** The `doctor` command reports what is blocked on
   the device; it must not try to work around a gate silently.
6. **Keep the tool honest.** If an operation does not work, say so in
   `STATUS.md` under "Does not work" — that section is as important as "Works".

## Working order

1. `python3 -m pytest tests -q`
2. `python3 -m compileall -q miui_adb_unlock`
3. `bash scripts/build-harness.sh`
4. `python3 -m miui_adb_unlock doctor` against a connected device

## Device etiquette

* Kill leftover harness processes before a run (single `UiAutomation` client).
* Prefer accessibility actions over coordinates; a damaged digitiser produces
  phantom touches.
* Read the state back (`getprop`, `dumpsys`) instead of assuming the click worked.
