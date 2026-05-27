# Plugin Examples And Contributor Fixtures

This page explains which SpecGuard plugin examples are packaged for users and which fixtures exist only for contributor validation.

## Packaged Example

The packaged authored example is stored in:

```text
tools/resources/example/
```

Users can copy it into a workspace with:

```bash
specguard example copy specs/your-feature-name --force
specguard run specs/your-feature-name --no-llm --no-follow-up
```

This example is intentionally compact. It exists to exercise the installed CLI path and a blocked readiness path. It must not grow into a full sample application without a separate scope decision.

## Contributor-Only Fixtures

Plugin workflow scenario fixtures live at:

```text
tests/fixtures/plugin-workflow-scenarios/scenarios.json
```

These fixtures are not packaged resources and are not copied by `specguard example copy`. They are contributor-only checks for durable plugin behavior:

- install and CLI availability guidance
- successful `ready` runs with allowed handoff
- `ready_with_warnings` runs with allowed handoff
- blocked `not_ready` runs
- `stale_review` recovery guidance
- `validation_failed_before_review` recovery guidance
- `missing_cli` guidance

The fixtures assert stable commands, file names, failure categories, and safety boundaries. They should not pin exact Markdown report sentences or screenshot-based behavior.

## Local Validation

Run the plugin example and fixture checks from the repository root:

```bash
python -m pytest tests/plugin/test_specguard_plugin_workflow.py -q
python -m pytest tests/plugin/test_plugin_result_contract.py -q
```

Run packaging tests only when packaged resources or package metadata change:

```bash
python -m pytest tests/packaging/test_packaging.py -q
```

The contributor fixtures are intentionally separate from benchmark fixtures. Do not duplicate benchmark cases here; add only the compact scenario metadata needed to protect plugin workflow behavior.
