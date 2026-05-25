# SpecGuard v0.4.1 Release Notes

## English

## SpecGuard v0.4.1

SpecGuard v0.4.1 is a stabilization release for the deterministic local
readiness gate, Korean gate-only evidence, benchmark traceability, and Codex
plugin documentation. It keeps the existing `specguard` CLI as the canonical
engine and does not change the `readiness-review.json` schema.

### Highlights

- Stabilized the recorded v0.4.1 English and Korean gate-only benchmark layer.
- Added readiness coverage matrix tooling and audit documentation for fixture
  gaps, result coverage, and follow-up issue triage.
- Added fixture drift guards so benchmark fixture expansion is explicit and
  duplicate mappings fail fast.
- Tightened readiness heuristics around workspace invite recipient binding,
  audit immutability, background job retry budgets, and Critical finding
  evidence shape.
- Clarified Korean support as deterministic low-mode coverage for explicit
  unsafe wording, not full CLI localization or full Korean production support.
- Documented Codex plugin hardening, guided PR Review setup boundaries, and the
  future CLI-driven Grill me loop.

### Added

- Readiness coverage matrix generator and checked-in coverage audit.
- Calibration triage protocol for false positives, false negatives, evidence
  quality, fixture gaps, and Korean counterpart gaps.
- Fixture drift tests for benchmark case expansion and duplicate source mapping.
- Audit and background job readiness fixture pairs.
- v0.4.1 release notes linked from the README.
- Design documentation for a future CLI-driven Grill me loop.

### Changed

- Bumped the package version from `0.4.0` to `0.4.1`.
- Refreshed the v0.4.1 gate-only benchmark artifact with 198 evaluated cases:
  99 English cases and 99 corresponding Korean cases.
- Updated README, benchmark, readiness rules, language support, and coverage
  audit documentation to preserve the recorded v0.4.1 support boundary.
- Improved Korean support claim wording so measured coverage and unsupported
  localization claims stay separate.
- Improved Codex plugin documentation for supported versions, PR Review setup,
  plugin hardening priorities, and setup flow.

### Fixed

- Reduced workspace invite recipient-binding false positives by narrowing safe
  recipient evidence detection.
- Blocked unsafe invite recipient-binding wording that could otherwise be missed.
- Enforced more actionable Critical finding evidence shape and source filtering.
- Clarified background job retry budget fixture behavior.

### Benchmark Results

The recorded v0.4.1 gate-only benchmark evaluates 198 cases: 99 English cases
and 99 corresponding Korean cases.

| Metric | English 99 | Korean 99 |
| --- | ---: | ---: |
| Weak specs blocked before implementation | 65/65 | 65/65 |
| Weak-spec block rate | 100.0% | 100.0% |
| Ready specs incorrectly blocked | 0/34 | 0/34 |
| False positive rate | 0.0% | 0.0% |
| Weak specs missed | 0/65 | 0/65 |
| False negative rate | 0.0% | 0.0% |

The current fixture source contains 100 English cases and 100 Korean cases. The
recorded v0.4.1 artifact covers 198 evaluated cases, so 2 new ready/reference
fixture results remain pending until the next benchmark refresh.

### Notes

- Python support remains `>=3.11`.
- The console script remains `specguard`.
- The default local gate remains `specguard run <package> --no-llm --no-follow-up`.
- SpecGuard PR Review remains optional and advisory.
- `readiness-review.json` remains on schema version `0.1`.
- LLM review is still opt-in and is not the default gate.
- The CLI-driven Grill me loop is design-only in this release.

### Known Limits

- Korean support is limited to deterministic low-mode coverage for explicit
  unsafe wording in the recorded benchmark layer.
- CLI output localization is not included.
- The recorded v0.4.1 benchmark artifact evaluates 198 cases, while the current
  fixture source contains 200 selected cases.
- A clean release-tag benchmark rerun is still a future validation step.

### Validation

- `python -m pytest tests/test_packaging.py` - passed
- `python -m pytest tests/test_specguard_plugin_workflow.py tests/test_benchmark_metadata.py` - passed
- `python -m pytest` - 282 passed
- `git diff --check` - passed
- GitHub PR checks for #206 - passed

### What's Changed

- Narrow plugin workflow test contracts in #176.
- Calibrate readiness heuristics with evidence in #177.
- Document Codex plugin hardening roadmap in #178.
- Document Codex PR Review setup workflow in #179.
- Improve Korean readiness finding evidence in #180.
- Add readiness coverage matrix generator in #191.
- Add readiness coverage audit in #193.
- Expand readiness coverage matrix in #195.
- Add readiness calibration triage protocol in #196.
- Add benchmark fixture drift guards in #197.
- Add audit readiness fixture pairs in #198.
- Block unsafe invite recipient binding in #199.
- Tighten invite safe-binding evidence in #200.
- Enforce Critical evidence shape in #201.
- Refresh v0.4.1 stabilization benchmark metrics in #202.
- Add background job readiness fixtures in #203.
- Align Korean support claims in #204.
- Design the CLI-driven Grill me loop in #205.
- Prepare the v0.4.1 release in #206.

**Full Changelog**: https://github.com/KoreaNirsa/spec-guard/compare/v0.4.0...v0.4.1

---

## 한국어

## SpecGuard v0.4.1

SpecGuard v0.4.1은 결정적 로컬 readiness gate, 한국어 gate-only 근거,
벤치마크 추적성, Codex 플러그인 문서를 안정화하는 패치 릴리즈입니다.
기존 `specguard` CLI를 계속 기준 엔진으로 유지하며, `readiness-review.json`
스키마는 변경하지 않습니다.

### 주요 내용

- v0.4.1 영어/한국어 gate-only 벤치마크 레이어를 안정화했습니다.
- fixture gap, 결과 커버리지, 후속 이슈 triage를 추적하기 위한 readiness
  coverage matrix 도구와 audit 문서를 추가했습니다.
- 벤치마크 fixture 확장이 명시적으로 드러나고 중복 매핑이 빠르게 실패하도록
  fixture drift guard를 추가했습니다.
- workspace invite 수신자 바인딩, audit 불변성, background job retry budget,
  Critical finding evidence shape 관련 readiness heuristic을 보강했습니다.
- 한국어 지원 범위를 “명시적인 unsafe wording에 대한 deterministic low-mode
  coverage”로 명확히 했습니다. 전체 CLI 현지화나 완전한 한국어 production
  support를 의미하지 않습니다.
- Codex plugin hardening, guided PR Review setup 경계, 향후 CLI-driven Grill me
  loop 설계를 문서화했습니다.

### 추가

- readiness coverage matrix generator와 checked-in coverage audit.
- false positive, false negative, evidence quality, fixture gap, Korean
  counterpart gap을 위한 calibration triage protocol.
- benchmark case 확장과 중복 source mapping을 잡는 fixture drift test.
- audit 및 background job readiness fixture pair.
- README에서 연결되는 v0.4.1 릴리즈 노트.
- 향후 CLI-driven Grill me loop 설계 문서.

### 변경

- package version을 `0.4.0`에서 `0.4.1`로 올렸습니다.
- v0.4.1 gate-only benchmark artifact를 198개 평가 케이스로 갱신했습니다:
  영어 99개, 대응 한국어 99개.
- README, benchmark, readiness rules, language support, coverage audit 문서가
  기록된 v0.4.1 지원 경계를 유지하도록 갱신했습니다.
- 한국어 지원 문구를 보강해 측정된 coverage와 지원하지 않는 localization
  claim이 섞이지 않도록 했습니다.
- 지원 버전, PR Review setup, plugin hardening 우선순위, setup flow 관련 Codex
  plugin 문서를 개선했습니다.

### 수정

- safe recipient evidence detection을 좁혀 workspace invite 수신자 바인딩
  false positive를 줄였습니다.
- 놓칠 수 있던 unsafe invite recipient-binding wording을 차단했습니다.
- Critical finding evidence shape과 source filtering을 더 실행 가능하게
  보강했습니다.
- background job retry budget fixture 동작을 명확히 했습니다.

### 벤치마크 결과

기록된 v0.4.1 gate-only benchmark는 198개 케이스를 평가합니다: 영어 99개와
대응 한국어 99개입니다.

| 지표 | 영어 99 | 한국어 99 |
| --- | ---: | ---: |
| 구현 전 차단된 weak spec | 65/65 | 65/65 |
| weak spec 차단율 | 100.0% | 100.0% |
| 잘못 차단된 ready spec | 0/34 | 0/34 |
| false positive rate | 0.0% | 0.0% |
| 놓친 weak spec | 0/65 | 0/65 |
| false negative rate | 0.0% | 0.0% |

현재 fixture source에는 영어 100개와 한국어 100개 케이스가 있습니다. 기록된
v0.4.1 artifact는 198개 케이스를 평가했으므로, 새 ready/reference fixture
2개 결과는 다음 benchmark refresh까지 pending 상태로 남아 있습니다.

### 참고

- Python 지원 범위는 `>=3.11`로 유지됩니다.
- console script는 계속 `specguard`입니다.
- 기본 local gate는 계속 `specguard run <package> --no-llm --no-follow-up`입니다.
- SpecGuard PR Review는 optional/advisory 상태로 유지됩니다.
- `readiness-review.json`은 schema version `0.1`을 유지합니다.
- LLM review는 여전히 opt-in이며 default gate가 아닙니다.
- CLI-driven Grill me loop는 이번 릴리즈에서 설계 문서까지만 포함됩니다.

### 알려진 한계

- 한국어 지원은 기록된 benchmark layer에서 명시적인 unsafe wording을 잡는
  deterministic low-mode coverage로 제한됩니다.
- CLI 출력 현지화는 포함되지 않습니다.
- 기록된 v0.4.1 benchmark artifact는 198개 케이스를 평가했지만, 현재 fixture
  source에는 200개 selected case가 있습니다.
- clean release tag 기준 benchmark rerun은 이후 검증 과제로 남아 있습니다.

### 검증

- `python -m pytest tests/test_packaging.py` - 통과
- `python -m pytest tests/test_specguard_plugin_workflow.py tests/test_benchmark_metadata.py` - 통과
- `python -m pytest` - 282개 통과
- `git diff --check` - 통과
- #206 GitHub PR checks - 통과

### 변경 목록

- #176: plugin workflow test contract 축소.
- #177: evidence 기반 readiness heuristic calibration.
- #178: Codex plugin hardening roadmap 문서화.
- #179: Codex PR Review setup workflow 문서화.
- #180: 한국어 readiness finding evidence 개선.
- #191: readiness coverage matrix generator 추가.
- #193: readiness coverage audit 추가.
- #195: readiness coverage matrix 확장.
- #196: readiness calibration triage protocol 추가.
- #197: benchmark fixture drift guard 추가.
- #198: audit readiness fixture pair 추가.
- #199: unsafe invite recipient binding 차단.
- #200: invite safe-binding evidence 보강.
- #201: Critical evidence shape 강제.
- #202: v0.4.1 stabilization benchmark metrics 갱신.
- #203: background job readiness fixture 추가.
- #204: 한국어 support claim 정렬.
- #205: CLI-driven Grill me loop 설계.
- #206: v0.4.1 release 준비.

**전체 변경 비교**: https://github.com/KoreaNirsa/spec-guard/compare/v0.4.0...v0.4.1
