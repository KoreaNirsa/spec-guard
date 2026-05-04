# Implementation Output: example

Use this feature folder as the implementation context for Codex, Claude Code, or another coding agent.

## Agent Input Artifacts

- `spec.md`
- `technical-design.md`
- `tests/example.test.md`
- `contracts/openapi.yaml`

## SpecGuard-Only Artifacts

- `discovery.md` is for SpecGuard discovery and user refinement.
- `grill.md` and `grill.json` are for SpecGuard adversarial validation.
- Coding agents should treat the agent input artifacts as the implementation basis.

## Output Location

- Put generated application code under `develop/<stack>/`.
- Examples: `develop/spring/`, `develop/react/`, `develop/fastapi/`.

## Implementation Rules

- Keep code aligned with `spec.md` and `technical-design.md`.
- Implement or preserve the behavior described in `tests/`.
- Keep API shape compatible with files under `contracts/`.
- When implementation reveals missing behavior, update the spec and rerun SpecGuard.
