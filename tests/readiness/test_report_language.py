from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from cli import specguard as specguard_cli
from tools.readiness_engine import run_readiness_review
from tools.report_language import detect_supported_language, resolve_report_language
from tools.runner import run_pipeline
from tools.post_run import render_plugin_readiness_summary
from tools.tdd_generator import generate_tests


def _write_package(path: Path, *, language: str = "en") -> None:
    path.mkdir(parents=True)
    if language == "ko":
        discovery = "# 탐색\n\n사용자가 자신의 할 일을 안전하게 관리해야 합니다.\n"
        spec = "# 스펙\n\n인증된 사용자는 자신의 할 일만 생성하고 조회할 수 있어야 합니다.\n"
        design = "# 기술 설계\n\n서버는 사용자 소유권을 확인한 뒤 데이터를 반환합니다.\n"
    else:
        discovery = "\n".join([
            "# Discovery: tasks",
            "",
            "## Foundation",
            "- Goal: Let users manage tasks safely.",
            "- Constraints: Keep the API small.",
            "",
            "## Mechanisms",
            "- Components: API and service.",
            "- Data flow: Request, validation, response.",
            "",
            "## Stress Test",
            "- First break: Invalid input.",
            "- Edge cases: Missing fields.",
            "",
            "## Synthesis",
            "- Decision: Build after validation.",
            "",
        ])
        spec = "\n".join([
            "# Spec: tasks",
            "",
            "## Requirements",
            "- The system must accept valid task input.",
            "",
            "## Acceptance Criteria",
            "- [ ] Valid task input succeeds.",
            "",
            "## Error Cases",
            "- Invalid task input",
            "",
        ])
        design = "\n".join([
            "# Technical Design: tasks",
            "",
            "## Architecture",
            "- The API calls a task service.",
            "",
            "## Data Flow",
            "1. The request arrives.",
            "2. The service validates input.",
            "3. The response is returned.",
            "",
            "## State",
            "- Initial state: request received.",
            "- Terminal state: completed.",
            "",
            "## Failure Handling",
            "- Invalid input returns a clear error.",
            "",
        ])
    path.joinpath("discovery.md").write_text(discovery, encoding="utf-8")
    path.joinpath("spec.md").write_text(spec, encoding="utf-8")
    path.joinpath("technical-design.md").write_text(design, encoding="utf-8")


def test_conversation_language_takes_precedence_over_english_spec() -> None:
    resolution = resolve_report_language(
        ["# Spec\n\nAuthenticated users can manage tasks."],
        conversation_language="ko",
    )

    assert resolution.code == "ko"
    assert resolution.source == "conversation"
    assert resolution.fallback_used is False


def test_korean_spec_is_used_when_conversation_context_is_unavailable() -> None:
    resolution = resolve_report_language(
        ["사용자는 자신의 결제 내역만 안전하게 조회할 수 있어야 합니다."],
    )

    assert resolution.code == "ko"
    assert resolution.source == "spec"
    assert resolution.fallback_used is False


def test_mixed_or_unsupported_language_falls_back_to_english() -> None:
    mixed = resolve_report_language(["hello world 안녕 세계"])
    unsupported = resolve_report_language(["利用者は自分の項目だけを表示します"])

    assert mixed.as_dict() == {"code": "en", "source": "fallback", "fallback_used": True}
    assert unsupported.as_dict() == {"code": "en", "source": "fallback", "fallback_used": True}
    assert detect_supported_language("") is None


def test_unsupported_conversation_hint_defers_to_spec_language() -> None:
    resolution = resolve_report_language(
        ["사용자는 자신의 결제 내역만 안전하게 조회할 수 있어야 합니다."],
        conversation_language="ja",
    )

    assert resolution.code == "ko"
    assert resolution.source == "spec"


def test_readiness_report_records_conversation_language_and_renders_korean(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "tasks"
    _write_package(feature)

    result = run_readiness_review(feature, conversation_language="ko")
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))
    report = feature.joinpath("readiness-review.md").read_text(encoding="utf-8")

    assert result.details["report_language"] == "ko"
    assert result.details["report_language_source"] == "conversation"
    assert payload["report_language"] == {
        "code": "ko",
        "source": "conversation",
        "fallback_used": False,
    }
    assert report.startswith("# SpecGuard 검토 결과\n\n## 요약\n")
    assert "## 준비 상태" in report
    assert "## 개선 제안" in report


def test_readiness_report_infers_korean_from_authored_package(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "tasks"
    _write_package(feature, language="ko")

    run_readiness_review(feature)
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert payload["report_language"] == {
        "code": "ko",
        "source": "spec",
        "fallback_used": False,
    }


def test_pipeline_propagates_conversation_language_to_human_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    feature = tmp_path / "specs" / "tasks"
    _write_package(feature)
    monkeypatch.setenv("SPECGUARD_CONVERSATION_LANGUAGE", "ko")

    result = run_pipeline(feature)
    payload = json.loads(feature.joinpath("readiness-review.json").read_text(encoding="utf-8"))

    assert result.ok is True
    assert feature.joinpath("readiness-review.md").read_text(encoding="utf-8").startswith("# SpecGuard 검토 결과")
    assert feature.joinpath("grill.md").read_text(encoding="utf-8").startswith("# SpecGuard 검토 질문")
    assert feature.joinpath("tests", "tasks.test.md").read_text(encoding="utf-8").startswith("# TDD 시나리오")
    assert feature.joinpath("implementation-output.md").read_text(encoding="utf-8").startswith("# 구현 인계")
    assert "- 보고서 언어: ko (conversation)" in render_plugin_readiness_summary(feature, payload)


def test_cli_next_action_uses_resolved_report_language(tmp_path: Path, capsys) -> None:
    feature = tmp_path / "specs" / "tasks"
    feature.mkdir(parents=True)
    feature.joinpath("implementation-output.md").write_text("# Handoff\n", encoding="utf-8")
    report = {
        "readiness": {"status": "ready_with_warnings", "implementation_ready": True},
        "summary": {"critical": 0, "major": 1, "minor": 0},
        "issues": [{"severity": "Major", "title": "Delete semantics are unsafe"}],
        "report_language": {"code": "ko", "source": "conversation", "fallback_used": False},
    }

    specguard_cli._print_ready_with_warnings_guidance(
        SimpleNamespace(path=str(feature)),
        [(feature, report)],
    )

    rendered = capsys.readouterr().out
    assert "다음 작업" in rendered
    assert "스펙은 경고가 있지만 구현할 수 있습니다" in rendered
    assert "구현 인계 경로" in rendered
    assert "재실행 명령" in rendered


def test_tdd_output_regenerates_when_only_resolved_language_changes(tmp_path: Path) -> None:
    feature = tmp_path / "specs" / "tasks"
    _write_package(feature)
    feature.joinpath("readiness-review.json").write_text(
        json.dumps({"report_language": {"code": "en", "source": "conversation", "fallback_used": False}}),
        encoding="utf-8",
    )
    output = generate_tests(feature)
    assert output.read_text(encoding="utf-8").startswith("# TDD Scenarios:")

    feature.joinpath("readiness-review.json").write_text(
        json.dumps({"report_language": {"code": "ko", "source": "conversation", "fallback_used": False}}),
        encoding="utf-8",
    )
    regenerated = generate_tests(feature)

    assert regenerated.read_text(encoding="utf-8").startswith("# TDD 시나리오:")
