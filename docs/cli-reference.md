# CLI Reference

Common commands:

```bash
specguard init <spec-name>
specguard example copy <spec-name> --force
specguard actions install-pr-review
specguard run specs/<spec-name>
specguard auth status
```

Useful `run` options:

- `--force`: regenerate derived artifacts such as technical design.
- `--follow-up`: force the interactive continuation menu.
- `--no-follow-up`: exit immediately after the pipeline.
- `--llm`: run live LLM SpecGuard Review in the main pipeline instead of the default fast heuristic low-mode review.
- `--no-llm`: force local deterministic checks and heuristic SpecGuard Review.
- `--review-level {low,medium,high}`: choose the SpecGuard Review depth; defaults to `low`, or `medium` for `--strict-e2e`.
- `--experimental-auto-revise`: allow the follow-up menu to rewrite blocked specs and rerun Verification Review.
- `--strict-e2e`: experimental strict automation that uses an LLM to regenerate blocked specs and rerun Verification Review.
- `--strict-max-iterations`: bound the number of strict E2E verification iterations.

CI or scripted example:

```bash
specguard init billing-export --non-interactive --no-llm
specguard example copy billing-export --force
specguard run specs/billing-export --no-llm --no-follow-up
```
