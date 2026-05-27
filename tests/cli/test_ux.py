from __future__ import annotations

from tools import ux


class FakeStdout:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def test_color_disabled_when_stdout_is_not_tty(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("CLICOLOR_FORCE", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(ux.sys, "stdout", FakeStdout(False))

    assert ux.green("ready") == "ready"


def test_no_color_overrides_tty(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr(ux.sys, "stdout", FakeStdout(True))

    assert ux.red("blocked") == "blocked"


def test_force_color_overrides_non_tty(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setattr(ux.sys, "stdout", FakeStdout(False))

    assert ux.green("ready") == "\033[32mready\033[0m"


def test_ci_disables_color_even_with_tty(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("CI", "true")
    monkeypatch.setattr(ux.sys, "stdout", FakeStdout(True))

    assert ux.yellow("warning") == "warning"
