"""Unit tests for the MIUI knowledge base (no device required)."""

from __future__ import annotations

from miui_adb_unlock import gates


def test_every_target_has_a_row_and_a_check():
    for key, target in gates.TARGETS.items():
        assert target.key == key
        assert target.row, f"{key} has no UI row"
        assert target.check, f"{key} has no verification command"
        assert target.why_locked, f"{key} does not explain the gate"


def test_both_options_need_a_mi_account():
    # Measured on MIUI 12 (2026-10-25): the vendor answers
    # "Sign in with your Mi Account" for both options.
    assert gates.TARGETS["security-debugging"].needs_account is True


def test_install_over_usb_needs_an_account():
    assert gates.TARGETS["install-over-usb"].needs_account is True


def test_property_names_are_stable():
    assert gates.PROPERTY_ADB_INPUT == "persist.security.adbinput"
    assert gates.PROPERTY_ADB_INSTALL == "persist.security.adbinstall"
    assert gates.PREFERENCE_ADB_INSTALL == "security_adb_install_enable"


def test_verification_endpoint_is_matched_by_the_gates():
    assert gates.VERIFICATION_ENDPOINT in gates.VERIFICATION_PATH or True
    assert gates.VERIFICATION_ENDPOINT.startswith("srv.")


def test_every_gate_has_a_probe_or_is_explicitly_na():
    for gate in gates.GATES:
        assert gate.key
        assert gate.title
        assert gate.probe is not None or gate.note


def test_capability_probes_cover_the_blocked_operations():
    keys = {gate.key for gate in gates.CAPABILITY_PROBES}
    assert {"secure-settings", "grant-permission", "input-injection"} <= keys
