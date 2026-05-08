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

Use the packaged example when you want to exercise SpecGuard without authoring a new spec first:

```bash
specguard init sample-run --non-interactive --no-llm
specguard example copy sample-run --force
specguard run specs/sample-run --no-llm --no-follow-up
```
