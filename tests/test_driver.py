"""Unit tests for the on-device driver client."""

from __future__ import annotations

from miui_adb_unlock.driver import Driver


def _driver() -> Driver:
    return Driver(adb=None)  # type: ignore[arg-type]


def test_parses_an_ok_result():
    raw = "[miui-a11y] OK click Установка через USB"
    result = Driver._parse(raw)
    assert result.ok
    assert "Установка через USB" in result.message


def test_parses_an_error_result():
    raw = "[miui-a11y] ERR not-found Отладка по USB"
    result = Driver._parse(raw)
    assert not result.ok
    assert "not-found" in result.message


def test_reports_a_missing_result_line():
    result = Driver._parse("INSTRUMENTATION_STATUS: numtests=1")
    assert not result.ok
    assert "no result line" in result.message


def test_collects_trace_lines():
    raw = (
        "[miui-a11y] TRACE scroll 1 -> true\n"
        "[miui-a11y] TRACE scroll 2 -> false\n"
        "[miui-a11y] ERR not-found target\n"
    )
    result = Driver._parse(raw)
    assert result.trace == ["scroll 1 -> true", "scroll 2 -> false"]
    assert not result.ok


def test_uses_the_last_result_line():
    raw = "[miui-a11y] ERR first\n[miui-a11y] OK second\n"
    result = Driver._parse(raw)
    assert result.ok
    assert result.message == "second"


def test_quotes_commands_safely():
    assert Driver._quote("a b") == "'a b'"
    assert Driver._quote("it's") == "'it'\\''s'"
