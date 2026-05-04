# Grill Result

## Critical Issues

### Todo ownership boundary is unclear

Description: The technical design does not prove that users can only read or mutate their own todos.

Impact: A generated API may expose cross-user data through list, update, or delete operations.

Fix: Require owner-scoped queries and authorization checks for every todo read/write path.

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
You are a senior software architect, security expert, and reliability engineer.

Your task is NOT to approve the implementation basis.
Your task is to BREAK the implementation basis.

Analyze the Discovery, Spec, and Technical Design aggressively.
Identify logic flaws, edge cases, security issues, performance risks, and failure scenarios.
```

## Input Summary

- Discovery characters: 1900
- Spec characters: 865
- Technical design characters: 812
