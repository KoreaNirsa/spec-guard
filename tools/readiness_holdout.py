from __future__ import annotations

import argparse
import json
import math
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from tools.readiness_engine import run_readiness_review


HOLDOUT_SCHEMA = "specguard-readiness-holdout/v1"
HOLDOUT_PATH = Path(__file__).resolve().parent / "resources" / "holdout" / "readiness-holdout-v1.json"
REQUIRED_DOMAINS = {
    "server_side_ownership",
    "payment_idempotency_timeout_reconciliation",
    "webhook_signature_replay",
    "token_expiry_revocation",
    "delete_audit_restore_policy",
    "tenant_scoped_cache_keys",
    "terminal_state_transitions",
    "bounded_retry_backoff",
}
SUPPORTED_LANGUAGES = {"en", "ko", "mixed"}
LABELS = {"ready", "weak"}
VARIANT_NAMES = ("safe", "unsafe")
RISK_STATEMENT = (
    "This frozen holdout estimates deterministic readiness behavior on scenarios "
    "that were not used to tune the calibrated regression suite. Zero observed "
    "failures do not imply zero production risk."
)


def load_holdout(path: Path = HOLDOUT_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_holdout(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != HOLDOUT_SCHEMA:
        errors.append(f"schema must be {HOLDOUT_SCHEMA}")
    if payload.get("status") != "frozen":
        errors.append("status must be frozen")
    if payload.get("corpus_scope") != "holdout":
        errors.append("corpus_scope must be holdout")
    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        errors.append("version must be a non-empty string")
    freeze_policy = payload.get("freeze_policy")
    if not isinstance(freeze_policy, dict):
        errors.append("freeze_policy must be an object")
    else:
        if freeze_policy.get("expectation_changes_require_explicit_review") is not True:
            errors.append("holdout expectation changes must require explicit review")
        if freeze_policy.get("heuristic_tuning_uses_holdout_failures") is not False:
            errors.append("holdout failures must not be tuning inputs")
    calibrated_source = payload.get("calibrated_fixture_source")
    if not isinstance(calibrated_source, str) or not calibrated_source.startswith("excluded: "):
        errors.append("calibrated_fixture_source must explicitly mark the calibrated suite as excluded")

    review_policy = payload.get("review_policy")
    if not isinstance(review_policy, dict):
        errors.append("review_policy must be an object")
    else:
        if review_policy.get("independent_reviewer_count") != 2:
            errors.append("review_policy must require two independent reviewers")
        if review_policy.get("execution_requires_resolved_labels") is not True:
            errors.append("execution must require resolved labels")

    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        return [*errors, "pairs must be a list"]
    if len(pairs) < 30:
        errors.append(f"holdout must contain at least 30 pairs, found {len(pairs)}")

    pair_ids: set[str] = set()
    semantic_scenarios: set[str] = set()
    domain_counts: defaultdict[str, int] = defaultdict(int)
    language_counts: defaultdict[str, int] = defaultdict(int)
    for index, pair in enumerate(pairs):
        prefix = f"pairs[{index}]"
        if not isinstance(pair, dict):
            errors.append(f"{prefix} must be an object")
            continue
        pair_id = pair.get("id")
        if not isinstance(pair_id, str) or not pair_id.strip():
            errors.append(f"{prefix}.id must be non-empty")
        elif pair_id in pair_ids:
            errors.append(f"duplicate pair id: {pair_id}")
        else:
            pair_ids.add(pair_id)

        domain = pair.get("domain")
        if domain not in REQUIRED_DOMAINS:
            errors.append(f"{prefix}.domain must be one of the required risk domains")
        else:
            domain_counts[domain] += 1
        language = pair.get("language")
        if language not in SUPPORTED_LANGUAGES:
            errors.append(f"{prefix}.language must be en, ko, or mixed")
        else:
            language_counts[language] += 1

        semantic_scenario = pair.get("semantic_scenario")
        if not isinstance(semantic_scenario, str) or not semantic_scenario.strip():
            errors.append(f"{prefix}.semantic_scenario must be non-empty")
        elif semantic_scenario in semantic_scenarios:
            errors.append(f"duplicate semantic scenario: {semantic_scenario}")
        else:
            semantic_scenarios.add(semantic_scenario)

        if not isinstance(pair.get("minimum_semantic_statement"), str) or not pair["minimum_semantic_statement"].strip():
            errors.append(f"{prefix}.minimum_semantic_statement must be non-empty")
        if not isinstance(pair.get("unsafe_mutation"), str) or not pair["unsafe_mutation"].strip():
            errors.append(f"{prefix}.unsafe_mutation must be non-empty")

        provenance = pair.get("provenance")
        if not isinstance(provenance, dict):
            errors.append(f"{prefix}.provenance must be an object")
        else:
            for field in ("source", "created", "review_basis", "independence_note"):
                if not isinstance(provenance.get(field), str) or not provenance[field].strip():
                    errors.append(f"{prefix}.provenance.{field} must be non-empty")
            if provenance.get("not_calibrated_fixture") is not True:
                errors.append(f"{prefix}.provenance.not_calibrated_fixture must be true")

        for variant_name in VARIANT_NAMES:
            variant = pair.get(variant_name)
            variant_prefix = f"{prefix}.{variant_name}"
            if not isinstance(variant, dict):
                errors.append(f"{variant_prefix} must be an object")
                continue
            for field in ("title", "contract", "acceptance", "errors", "design"):
                if not isinstance(variant.get(field), str) or not variant[field].strip():
                    errors.append(f"{variant_prefix}.{field} must be non-empty")
            if not isinstance(variant.get("case_id"), str) or not variant["case_id"].strip():
                errors.append(f"{variant_prefix}.case_id must be non-empty")
            expected = variant.get("expected")
            if expected not in LABELS:
                errors.append(f"{variant_prefix}.expected must be ready or weak")
            labels = variant.get("reviewer_labels")
            if not isinstance(labels, list) or len(labels) != 2:
                errors.append(f"{variant_prefix}.reviewer_labels must contain two labels")
                labels = []
            reviewer_ids: set[str] = set()
            for label_index, label_record in enumerate(labels):
                label_prefix = f"{variant_prefix}.reviewer_labels[{label_index}]"
                if not isinstance(label_record, dict):
                    errors.append(f"{label_prefix} must be an object")
                    continue
                reviewer_id = label_record.get("reviewer_id")
                if not isinstance(reviewer_id, str) or not reviewer_id.strip():
                    errors.append(f"{label_prefix}.reviewer_id must be non-empty")
                elif reviewer_id in reviewer_ids:
                    errors.append(f"{variant_prefix} has duplicate reviewer id {reviewer_id}")
                else:
                    reviewer_ids.add(reviewer_id)
                if label_record.get("label") not in LABELS:
                    errors.append(f"{label_prefix}.label must be ready or weak")
                if label_record.get("independent") is not True:
                    errors.append(f"{label_prefix}.independent must be true")

            adjudication = variant.get("adjudication")
            if not isinstance(adjudication, dict):
                errors.append(f"{variant_prefix}.adjudication must be an object")
                continue
            label_values = {record.get("label") for record in labels if isinstance(record, dict)}
            if label_values == {expected}:
                if adjudication.get("status") != "not_required":
                    errors.append(f"{variant_prefix} unanimous labels must be not_required")
            else:
                if adjudication.get("status") != "resolved":
                    errors.append(f"{variant_prefix} disagreement must be resolved")
                if adjudication.get("final_label") != expected:
                    errors.append(f"{variant_prefix} adjudication must resolve to expected label")
                if not isinstance(adjudication.get("reason"), str) or not adjudication["reason"].strip():
                    errors.append(f"{variant_prefix} resolved disagreement needs a reason")
            if adjudication.get("final_label", expected) != expected:
                errors.append(f"{variant_prefix}.adjudication.final_label must equal expected")

        safe = pair.get("safe") if isinstance(pair.get("safe"), dict) else {}
        unsafe = pair.get("unsafe") if isinstance(pair.get("unsafe"), dict) else {}
        if safe.get("contract") == unsafe.get("contract"):
            errors.append(f"{prefix} safe and unsafe contracts must differ")
        if safe.get("design") == unsafe.get("design"):
            errors.append(f"{prefix} safe and unsafe designs must differ")
        if safe.get("expected") != "ready":
            errors.append(f"{prefix}.safe.expected must be ready")
        if unsafe.get("expected") != "weak":
            errors.append(f"{prefix}.unsafe.expected must be weak")

    missing_domains = sorted(REQUIRED_DOMAINS - set(domain_counts))
    if missing_domains:
        errors.append(f"missing required domains: {', '.join(missing_domains)}")
    missing_languages = sorted(SUPPORTED_LANGUAGES - set(language_counts))
    if missing_languages:
        errors.append(f"missing required languages: {', '.join(missing_languages)}")
    if any(count < 3 for count in domain_counts.values()):
        errors.append("each risk domain must contain at least three semantic pairs")
    return errors


def assert_valid_holdout(payload: dict[str, Any]) -> None:
    errors = validate_holdout(payload)
    if errors:
        raise ValueError("Invalid frozen readiness holdout:\n- " + "\n- ".join(errors))


def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> tuple[float, float] | None:
    if trials <= 0:
        return None
    proportion = successes / trials
    denominator = 1 + (z * z / trials)
    centre = (proportion + (z * z / (2 * trials))) / denominator
    margin = (
        z
        * math.sqrt(
            (proportion * (1 - proportion) / trials)
            + (z * z / (4 * trials * trials))
        )
        / denominator
    )
    return max(0.0, centre - margin), min(1.0, centre + margin)


def _metric(successes: int, trials: int) -> dict[str, Any]:
    interval = wilson_interval(successes, trials)
    rate = successes / trials if trials else None
    return {
        "successes": successes,
        "trials": trials,
        "rate": rate,
        "percent": rate * 100 if rate is not None else None,
        "confidence_interval_95": (
            {
                "lower": interval[0],
                "upper": interval[1],
                "lower_percent": interval[0] * 100,
                "upper_percent": interval[1] * 100,
            }
            if interval is not None
            else None
        ),
    }


def _classification_metrics(records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    records = list(records)
    true_positive = sum(1 for record in records if record["expected"] == "weak" and record["blocked"])
    true_negative = sum(1 for record in records if record["expected"] == "ready" and not record["blocked"])
    false_positive = sum(1 for record in records if record["expected"] == "ready" and record["blocked"])
    false_negative = sum(1 for record in records if record["expected"] == "weak" and not record["blocked"])
    return {
        "case_count": len(records),
        "ready_case_count": sum(record["expected"] == "ready" for record in records),
        "weak_case_count": sum(record["expected"] == "weak" for record in records),
        "confusion_matrix": {
            "true_positive_blocked_weak": true_positive,
            "true_negative_allowed_ready": true_negative,
            "false_positive_blocked_ready": false_positive,
            "false_negative_allowed_weak": false_negative,
        },
        "weak_recall": _metric(true_positive, true_positive + false_negative),
        "ready_specificity": _metric(true_negative, true_negative + false_positive),
        "false_positive_rate": _metric(false_positive, true_negative + false_positive),
        "false_negative_rate": _metric(false_negative, true_positive + false_negative),
    }


def build_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    by_language: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_domain[record["domain"]].append(record)
        by_language[record["language"]].append(record)
    return {
        "overall": _classification_metrics(records),
        "by_domain": {
            key: _classification_metrics(by_domain[key])
            for key in sorted(by_domain)
        },
        "by_language": {
            key: _classification_metrics(by_language[key])
            for key in sorted(by_language)
        },
    }


def _render_package(root: Path, pair: dict[str, Any], variant_name: str) -> Path:
    variant = pair[variant_name]
    package = root / "packages" / variant["case_id"]
    language = pair["language"]
    contract = variant["contract"]
    acceptance = variant["acceptance"]
    error_cases = variant["errors"]
    design = variant["design"]
    package.mkdir(parents=True, exist_ok=True)
    package.joinpath("discovery.md").write_text(
        f"""# Discovery: {variant['title']}

## Foundation
- Goal: evaluate a frozen readiness holdout scenario.
- Domain: {pair['domain']}.
- Language profile: {language}.
- Semantic risk: {pair['minimum_semantic_statement']}.

## Stress Test
- The safe and unsafe variants differ only at the minimum semantic mutation recorded by the corpus.
- This package is provider-free benchmark input and is not a calibrated fixture.

## Synthesis
- The gate must allow the safe contract and block the unsafe contract before implementation.
""",
        encoding="utf-8",
    )
    package.joinpath("spec.md").write_text(
        f"""# Feature: {variant['title']}

## Summary
- {pair['minimum_semantic_statement']}

## Requirements
- {contract}

## Acceptance Criteria
- {acceptance}

## Error Cases
- {error_cases}

## Out of Scope
- Implementation details outside this holdout scenario.
""",
        encoding="utf-8",
    )
    package.joinpath("technical-design.md").write_text(
        f"""# Technical Design: {variant['title']}

## Architecture
- {design}

## Data Flow
1. The service receives the authenticated request and validates the authored contract.
2. The service applies the domain boundary before returning or mutating data.

## State
- Requests have explicit success and failure outcomes.

## Failure Handling
- Authored error behavior is returned without silently delegating the risk decision to a client or caller.
""",
        encoding="utf-8",
    )
    package.joinpath("plan.md").write_text(
        """# Plan

## Scope
- Implement only the behavior in spec.md and technical-design.md.

## Verification
- Run the provider-free readiness gate before implementation.
""",
        encoding="utf-8",
    )
    package.joinpath("tasks.md").write_text(
        """# Tasks

- [ ] Review the holdout contract.
- [ ] Stop implementation handoff when the gate reports NOT_READY.
""",
        encoding="utf-8",
    )
    package.joinpath("constitution.md").write_text(
        """# Constitution

- The server owns security, data isolation, state, and failure decisions.
- Do not add behavior that is not explicit in the authored package.
""",
        encoding="utf-8",
    )
    return package


def _run_variant(root: Path, pair: dict[str, Any], variant_name: str) -> dict[str, Any]:
    variant = pair[variant_name]
    package = _render_package(root, pair, variant_name)
    result = run_readiness_review(package, review_level="low")
    report_path = package / "readiness-review.json"
    report: dict[str, Any] = {}
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    readiness = report.get("readiness", {})
    summary = report.get("summary", {})
    implementation_ready = bool(readiness.get("implementation_ready", False))
    return {
        "case_id": variant["case_id"],
        "pair_id": pair["id"],
        "variant": variant_name,
        "domain": pair["domain"],
        "language": pair["language"],
        "expected": variant["expected"],
        "blocked": not implementation_ready,
        "implementation_ready": implementation_ready,
        "readiness": readiness.get("status"),
        "issue_summary": {
            "critical": int(summary.get("critical", 0)),
            "major": int(summary.get("major", 0)),
            "minor": int(summary.get("minor", 0)),
        },
        "finding_titles": [
            issue.get("title", "")
            for issue in report.get("issues", [])
            if isinstance(issue, dict)
        ],
        "gate_ok": result.ok,
    }


def _run_pair(root: Path, pair: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        _run_variant(root, pair, "safe"),
        _run_variant(root, pair, "unsafe"),
    )


def run_holdout(
    payload: dict[str, Any] | None = None,
    *,
    max_workers: int = 4,
) -> dict[str, Any]:
    payload = load_holdout() if payload is None else payload
    assert_valid_holdout(payload)
    pairs = sorted(payload["pairs"], key=lambda pair: pair["id"])
    with tempfile.TemporaryDirectory(prefix="specguard-readiness-holdout-") as temp_dir:
        root = Path(temp_dir)
        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(pairs)))) as executor:
            pair_results = list(executor.map(lambda pair: _run_pair(root, pair), pairs))

    case_records = [record for pair_result in pair_results for record in pair_result]
    case_records.sort(key=lambda record: (record["pair_id"], record["variant"]))
    pair_records = []
    for pair, (safe_result, unsafe_result) in zip(pairs, pair_results):
        minimum_statement_changed = pair["safe"]["contract"] != pair["unsafe"]["contract"]
        metamorphic_passed = (
            minimum_statement_changed
            and safe_result["implementation_ready"]
            and not unsafe_result["implementation_ready"]
        )
        pair_records.append({
            "pair_id": pair["id"],
            "domain": pair["domain"],
            "language": pair["language"],
            "safe_case_id": safe_result["case_id"],
            "unsafe_case_id": unsafe_result["case_id"],
            "minimum_semantic_statement": pair["minimum_semantic_statement"],
            "unsafe_mutation": pair["unsafe_mutation"],
            "minimum_statement_changed": minimum_statement_changed,
            "safe_implementation_ready": safe_result["implementation_ready"],
            "unsafe_implementation_ready": unsafe_result["implementation_ready"],
            "passed": metamorphic_passed,
        })
    passed_pairs = sum(pair["passed"] for pair in pair_records)
    return {
        "schema": "specguard-readiness-holdout-result/v1",
        "corpus": {
            "schema": payload["schema"],
            "version": payload["version"],
            "status": payload["status"],
            "pair_count": len(pairs),
            "case_count": len(case_records),
            "source": "tools/resources/holdout/readiness-holdout-v1.json",
            "calibrated_suite_source": payload["calibrated_fixture_source"],
            "freeze_policy": payload["freeze_policy"],
        },
        "execution": {
            "provider": "none",
            "review_level": "low",
            "max_workers": max(1, max_workers),
            "results_are_separate_from_calibrated_suite": True,
        },
        "risk_statement": RISK_STATEMENT,
        "metamorphic": {
            "pair_count": len(pair_records),
            "passed_pairs": passed_pairs,
            "failed_pairs": [pair["pair_id"] for pair in pair_records if not pair["passed"]],
            "all_pairs_passed": passed_pairs == len(pair_records),
            "pairs": pair_records,
        },
        "metrics": build_metrics(case_records),
        "cases": case_records,
    }


def _validation_summary(payload: dict[str, Any]) -> dict[str, Any]:
    errors = validate_holdout(payload)
    return {
        "schema": payload.get("schema"),
        "valid": not errors,
        "errors": errors,
        "pair_count": len(payload.get("pairs", [])) if isinstance(payload.get("pairs"), list) else 0,
        "languages": sorted({pair.get("language") for pair in payload.get("pairs", []) if isinstance(pair, dict)}),
        "domains": sorted({pair.get("domain") for pair in payload.get("pairs", []) if isinstance(pair, dict)}),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or run the frozen readiness holdout.")
    parser.add_argument("--corpus", type=Path, default=HOLDOUT_PATH)
    parser.add_argument("--validate", action="store_true", help="Validate corpus labels and schema.")
    parser.add_argument("--run", action="store_true", help="Run the provider-free readiness gate.")
    parser.add_argument("--output", type=Path, help="Write the JSON result to this path.")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args(argv)
    payload = load_holdout(args.corpus)
    if args.run:
        result = run_holdout(payload, max_workers=args.max_workers)
    else:
        result = _validation_summary(payload)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if args.run:
        return 0
    return 0 if result.get("valid", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
