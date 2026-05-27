---
name: specguard-spec-report
description: Use when a user asks Codex to create human-readable SpecGuard spec reports, Mermaid diagrams, HTML review summaries, visual readiness reports, or decision-review reports from an existing spec package and SpecGuard readiness artifacts without changing spec content.
---

# SpecGuard Human-Readable Spec Report

Use this skill when the user asks for a visual or human-readable report from an existing SpecGuard spec package, for example:

- "Generate a SpecGuard report for this package."
- "Create a Mermaid readiness diagram."
- "Create an HTML review report from the latest SpecGuard result."
- "Show the spec flow, readiness findings, and handoff status for review."

## Boundary

This skill is report-only. It must not patch `spec.md`, `discovery.md`, `technical-design.md`, `plan.md`, `tasks.md`, or any other authored spec file. It must not create implementation requirements, infer product behavior, or replace the default SpecGuard readiness workflow.

The report reads existing source-backed artifacts:

- the selected spec package path
- `readiness-review.json`, when present
- `readiness-review.md`, when present
- `implementation-output.md`, only to report handoff availability
- `input.artifacts[]`, `summary`, `issues[]`, and optional `issues[].evidence[]` from `readiness-review.json`

Keep source spec evidence, readiness findings, and report-only presentation separate. If the readiness artifact is missing, stale, malformed, or ambiguous, say that the next safe action is to rerun:

```bash
specguard run <package> --no-llm --no-follow-up
```

Do not use generated report wording as implementation input. Generated reports are presentation artifacts only and must stay out of future readiness source artifact sets. Each generated report file is not an authored spec input.

## Output Paths

Generate reports under the selected package `docs/` directory:

```text
<package>/docs/specguard-report.mmd
<package>/docs/specguard-report.html
```

These files are generated report artifacts. They summarize the latest structured readiness result for human review, but they are not authored spec inputs.

## Helper Script

From a SpecGuard repository checkout, run:

```bash
python plugins/specguard/skills/specguard-spec-report/scripts/spec_report.py <package>
```

The script creates the documented Mermaid and HTML report files. It reads the latest structured readiness artifacts and writes only the two generated report files under `<package>/docs/`.

## Report Content

Each report should include:

- spec package path
- readiness status and review level
- Critical, Major, and Minor finding summary
- top readiness findings by severity and title
- key evidence excerpts from `issues[].evidence[]`, when present
- readiness report paths
- handoff availability
- next action derived from the readiness state

For `not_ready`, show Critical findings first and state that implementation is blocked. For `ready` or `ready_with_warnings`, report implementation as available only when `readiness.implementation_ready` is true and `implementation-output.md` exists.

## Non-Goals

- Do not replace the Grill me loop or default SpecGuard Review.
- Do not reimplement the review engine.
- Do not invent missing product, API, persistence, security, or operational behavior.
- Do not treat generated `docs/specguard-report.mmd` or `docs/specguard-report.html` as authored spec artifacts.
