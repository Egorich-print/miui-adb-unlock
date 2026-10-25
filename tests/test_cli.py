"""Unit tests for the command line interface."""

from __future__ import annotations

import pytest

from miui_adb_unlock.cli import build_parser


def test_parser_exposes_every_command():
    parser = build_parser()
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"


def test_unlock_accepts_the_known_targets():
    parser = build_parser()
    args = parser.parse_args(["unlock", "security-debugging"])
    assert args.target == "security-debugging"


def test_unlock_rejects_unknown_targets():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["unlock", "something-else"])


def test_wifi_reads_the_password_from_the_environment():
    parser = build_parser()
    args = parser.parse_args(["wifi", "MyNetwork"])
    assert args.ssid == "MyNetwork"
    assert args.password_env == "MIUI_WIFI_PASSWORD"


def test_serial_is_optional():
    parser = build_parser()
    args = parser.parse_args(["--serial", "abc123", "verify"])
    assert args.serial == "abc123"
