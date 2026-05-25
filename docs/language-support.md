# Language Support

## 한국어

SpecGuard 문서는 한국어를 기본 지원 언어로 다룹니다. 영어도 오픈소스 사용자, 기여자, 교차 언어 검토를 위해 함께 지원합니다.

한국어 문서는 한국어 사용자를 위한 기본 사용자-facing 경로여야 합니다. 같은 워크플로를 한국어와 영어 문서가 모두 다룰 때는 제품 동작, 검증 경계, 지원 한계를 동일하게 설명해야 합니다.

이 정책은 문서에만 적용됩니다. CLI 출력 현지화, API 동작 변경, 런타임 동작 확장은 v0.4.1 범위가 아닙니다.

## English

SpecGuard supports Korean as the default documentation language. English documentation is also supported.

When Korean and English docs describe the same workflow, both versions must describe the same product behavior, validation boundary, and support limits. English docs should be useful for contributors and open-source readers without introducing claims that are missing from Korean docs.

## Support Boundaries

| Area | Korean | English |
| --- | --- | --- |
| Documentation policy | Supported by default | Supported |
| User-facing workflow docs | Supported, prioritized for Korean users | Supported for contributors and open-source readers |
| Benchmark support notes | Supported when backed by measured results | Supported when backed by measured results |
| CLI output localization | Not in scope for v0.4.1 | Existing English output remains in place |
| Historical benchmark artifact translation | Not required | Existing artifacts remain valid |

## Required Docs

| Document | Korean status | English status |
| --- | --- | --- |
| `README.md` | Entry point must link to this policy. Korean companion content can be added when user-facing overview text is localized. | Existing overview is supported and links to this policy. |
| `docs/setup-to-user-flow.md` | Planned companion content for installation and review workflow. | Existing source is supported. |
| `docs/workflow.md` | Planned companion content for end-to-end workflow. | Existing source is supported. |
| `docs/spec-driven-benchmark.md` | Korean benchmark limits must stay aligned with measured v0.4.1 results and the current fixture matrix. | Existing benchmark methodology is supported. |
| `docs/readiness-rules.md` | Planned companion content for READY, READY_WITH_WARNINGS, and blocking rules. | Existing source is supported. |

## Korean Benchmark Claims

Korean support claims must stay within measured evidence:

- The recorded v0.4.1 gate-only artifact evaluates 99 English cases and 99 corresponding Korean cases.
- The current fixture source contains 100 English cases and 100 Korean cases. The coverage matrix records 2 selected ready/reference fixture results as missing from the v0.4.1 artifact until the benchmark is refreshed.
- Korean-only weak specs are covered when unsafe wording is explicit in the deterministic low-mode rules.
- Mixed Korean/English specs with English contract identifiers are supported when the relevant risk is explicit.
- Full Korean production support is not claimed until broader benchmark and product validation exist.

## Korean Finding Quality Calibration

Current known Korean false positives:

- None in the recorded v0.4.1 Korean 99-case gate-only layer.

Current known Korean false negatives:

- None in the recorded v0.4.1 Korean 99-case gate-only layer.

Current Korean support limitations:

- The checked-in fixture source is ahead of the recorded v0.4.1 benchmark artifact by 2 selected ready/reference cases, so 100-case Korean pass/fail claims must wait for a benchmark refresh.
- The v0.4.1 aggregate benchmark artifact does not persist full Critical finding evidence payloads; detailed evidence quality is tracked separately.
- Korean coverage remains deterministic and phrase-bound. It does not validate every Korean idiom, legal/privacy variant, LLM-backed Korean review quality, or full CLI localization.

The #175 finding-quality work targets representative Korean weak specs that already block correctly but can produce weaker findings than English/general heuristic cases. The concrete quality gap is missing `evidence[]` excerpts on Korean-specific deterministic blockers. Without source evidence, a finding can be less actionable even when its severity and readiness decision are correct.

Focused regression coverage should protect:

- Korean `READY` behavior through the medium review policy.
- Korean `READY_WITH_WARNINGS` behavior through the default low review policy.
- Korean `NOT_READY` behavior for explicit unsafe Korean wording.
- Critical Korean findings with concrete `evidence[]`, specific impact, and an actionable fix.

These tests should not snapshot exact Korean prose unless the phrase is intentionally part of a stable public contract.

## Maintenance Rule

Any PR that changes user-facing documentation should check whether this language policy needs an update. If a workflow is documented in both Korean and English, the PR should keep the behavior and support limits consistent in both languages.
