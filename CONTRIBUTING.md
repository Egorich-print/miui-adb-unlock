# Contributing

## Gates (all green before a commit)

| Gate | Command |
|------|---------|
| Lint  | `python3 -m compileall -q miui_adb_unlock` |
| Test  | `python3 -m pytest tests -q` |
| Build | `bash scripts/build-harness.sh` |

## Commit rules

- One logical change — one commit.
- Prefixes: `feat:`, `fix:`, `docs:`, `chore:`, `refactor:`, `test:`.
- Commit only with the user's permission.

## Secrets

Never commit keys, tokens or Wi-Fi passwords. The `wifi` command takes the
password from an environment variable for exactly this reason.

## Changing the MIUI knowledge

Every MIUI-specific string (labels, property names, provider names, endpoints)
lives in `miui_adb_unlock/gates.py`. Do not scatter them through the code.
