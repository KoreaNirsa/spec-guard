# SpecGuard Review Result

- Review mode: initial

## Readiness

- Status: NOT READY
- Criteria: Critical=0, Major=0, Minor<=5
- Current: Critical=0, Major=1, Minor=0

## Critical Issues

- None detected by the local heuristic engine.

## Major Issues

### Delete semantics are unsafe

Description: The spec allows deletion but does not define hard delete, soft delete, restore, or audit behavior.

Impact: Data loss and compliance issues can appear after code generation.

Fix: Choose hard or soft delete explicitly and define audit records, restore behavior, and API response codes.

## Minor Issues

- None detected by the local heuristic engine.

## Improvement Suggestions

- Convert every Critical and Major item into acceptance criteria before implementation.
- Add tests for authorization, invalid state, retry, timeout, and duplicate request behavior.
- Re-run `specguard run` after updating `spec.md` and `technical-design.md`.

## Prompt Mode

```text
You are SpecGuard's readiness review board: a principal software architect, security reviewer, reliability engineer, API contract reviewer, and test strategist.

Your task is NOT to approve the implementation basis.
Your task is to BREAK the implementation basis before a coding agent sees it.

Review every spec package artifact together: Discovery, spec, plan, tasks, constitution, checklists, technical design, and any other authored spec document.

Use the SpecGuard Review method:
- Find contradictions between artifacts.
- Attack missing requirements, undefined state, ambiguous ownership, weak contracts, unsafe retries, auth gaps, versioning gaps, and untestable acceptance criteria.
- Convert implementation guesses into Critical or Major findings.
- Treat style-only improvements as Minor.

Implementation-ready threshold:
- Critical: 0
- Major: 0
- Minor: 5 or fewer, and none may hide a requirement ambiguity.
```

## Input Summary

- discovery.md: 1930 characters
- spec.md: 865 characters
- technical-design.md: 2006 characters
