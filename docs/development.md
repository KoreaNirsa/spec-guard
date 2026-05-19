# Development

For contributors or local source testing:

```bash
git clone https://github.com/KoreaNirsa/spec-guard.git
cd spec-guard
python -m pip install -e ".[test]"
```

Run tests:

```bash
python -m pytest
```

## Test Boundary

Prefer tests that protect stable user-facing contracts over tests that pin incidental prose.
Core behavior coverage includes CLI execution, readiness decisions, plugin result contract shape,
packaging/import behavior, failure states, workflow installation, and contract validation.

Documentation and plugin workflow tests should assert durable commands, machine-readable files,
failure categories, safety boundaries, and setup paths. Avoid exact-sentence, screenshot URL,
transient version note, or broad Markdown snapshot assertions unless the wording is itself a
documented public contract.

Use the packaged example when you want to exercise SpecGuard without authoring a new spec first:

```bash
specguard init sample-run --non-interactive --no-llm
specguard example copy sample-run --force
specguard run specs/sample-run --no-llm --no-follow-up
```
