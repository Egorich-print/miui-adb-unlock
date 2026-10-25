# STATE — what to do next

> Updated: 2026-10-25

## Done

- Reverse engineering of the MIUI gates (`docs/research/miui-security-gates.md`).
- On-device accessibility driver with scroll/click/type/dump.
- Python CLI: `doctor`, `unlock`, `verify`, `wifi`, `dump`.
- Verified end to end on Redmi Note 5 / MIUI 12: the click on *USB debugging
  (security settings)* opens MIUI's own verification activity.

## Open

1. **Complete the unlock with a Mi Account signed in.** The click path is
   proven end to end; the last mile is MIUI's own verification, which asks for a
   Mi Account ("Sign in with your Mi Account", measured 2026-10-25). With an
   account the flow takes the local branch and sets the property without the
   server — record the output in `docs/research/`.
2. **Multi-device label mapping.** The MIUI labels in `gates.py` are from one
   build; make the matching tolerant (substring, locale-independent).
3. **Wi-Fi profile repair.** MIUI refuses to change the security type of a saved
   network, and unprivileged apps may not rewrite the profile. Options to
   evaluate: guide the user through "forget + re-add", or drive the connect
   dialog with the security type chosen explicitly.
4. **Packaging.** Publish the harness jar as a release artifact; the repository
   keeps it for convenience.

## Blocked

- *Both options* without a signed-in Xiaomi account: MIUI's own rule, not a tool
  limitation. The practical goal of installing packages over USB already works —
  `adb install` is not blocked; the options additionally restore adb input
  injection, permission granting and secure-settings writes.
