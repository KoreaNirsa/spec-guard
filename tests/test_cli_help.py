from __future__ import annotations

import pytest

from cli.specguard import build_parser


def _help_text(capsys: pytest.CaptureFixture[str], *args: str) -> str:
    parser = build_parser()
    with pytest.raises(SystemExit) as exc:
        parser.parse_args([*args, "--help"] if args else ["--help"])
    assert exc.value.code == 0
    return capsys.readouterr().out


def test_top_level_help_lists_user_workflow_order(capsys: pytest.CaptureFixture[str]) -> None:
    help_text = _help_text(capsys)

    assert "usage: specguard [-h] {init,example,run,actions,auth} ..." in help_text
    assert "init                Create draft specs and install the default readiness" in help_text
    assert "example             Copy the packaged authored example" in help_text
    assert "run                 Validate specs and produce implementation handoff" in help_text
    assert "actions             Install consumer GitHub Actions workflows" in help_text
    assert "auth                Configure or inspect local LLM provider settings" in help_text


def test_run_help_explains_llm_follow_up_and_strict_modes(capsys: pytest.CaptureFixture[str]) -> None:
    help_text = _help_text(capsys, "run")

    assert "LLM review is enabled by default when a provider is configured" in help_text
    assert "Skip live LLM requests and use local generators plus" in help_text
    assert "--no-follow-up" in help_text
    assert "--follow-up" in help_text
    assert "--strict-e2e" in help_text
    assert "--review-level {high,low,medium}" in help_text
    assert "specguard run specs/team-invite --review-level medium" in help_text
    assert "specguard auth setup --mode codex --timeout 600 --skip-login" in help_text


def test_auth_help_distinguishes_config_checks_from_live_requests(capsys: pytest.CaptureFixture[str]) -> None:
    setup_help = _help_text(capsys, "auth", "setup")
    status_help = _help_text(capsys, "auth", "status")

    assert "Codex mode uses the local Codex CLI/session" in setup_help
    assert "OpenAI mode uses the Responses API" in setup_help
    assert "Codex timeout: 600s" in setup_help
    assert "OpenAI timeout: 180s" in setup_help
    assert "not a full live model request" in setup_help
    assert "without making a live model request" in status_help


def test_example_copy_help_shows_init_copy_run_flow(capsys: pytest.CaptureFixture[str]) -> None:
    help_text = _help_text(capsys, "example", "copy")

    assert "Typical sample flow: init -> copy -> run." in help_text
    assert "specguard auth setup --mode codex --model gpt-5.4 --skip-login" in help_text
    assert "specguard init team-invite --non-interactive --no-llm" in help_text
    assert "specguard example copy team-invite --force" in help_text
    assert "specguard run specs/team-invite --no-follow-up" in help_text
