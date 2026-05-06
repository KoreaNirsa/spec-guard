# Discovery

Discovery is SpecGuard's init-time exploration step.

It is adapted from the idea of a 100-question sequential self-interrogation framework, but SpecGuard uses a focused question set so the workflow stays usable.

In public workflow language, prefer `Discovery`. `Deep Discovery` can be used as the name of the technique or prompt pattern behind the artifact, but the project artifact should stay simple: `discovery.md`.

## Terminology

Recommended public term: `Discovery`.

Why:

- It is simple enough for contributors to understand without learning a new branded method first.
- It leaves room for multiple discovery techniques later.
- It keeps the workflow readable: `Discovery -> Draft Spec -> User Refinement -> Technical Design -> SpecGuard Review`.

Other terms considered:

- `Deep Discovery`: strong technique name, but it can sound heavier than the artifact needs to be.
- `SDD Discovery`: precise, but less friendly as a file and CLI concept.
- `Spec Discovery`: clear, but too close to the spec itself.
- `Intent Discovery`: useful conceptually, but less direct for engineering workflow docs.

## Position In The Workflow

```text
Discovery
  -> Draft Spec
  -> User Refinement
  -> Technical Design
  -> SpecGuard Review
  -> TDD
  -> Contract Check
  -> Implementation Handoff
```

Discovery asks what should be understood before a spec and technical design harden. `specguard init` uses the answers to generate draft specs under `specs/`. SpecGuard Review later challenges the spec and technical design before tests, contracts, and the implementation handoff are produced.

## Question Phases

| Phase | Focus |
| --- | --- |
| Foundation | Goal, users, constraints, assumptions |
| Mechanisms | Components, data flow, dependencies, state |
| Stress Test | Edge cases, concurrency, security, recovery |
| Differentiation | Existing options, unique value, non-goals |
| Feasibility | Buildability, blockers, validation |
| Improvement | Simplification, automation, unknowns |
| Synthesis | Decision, required artifacts, stop conditions |

## Rule Of Thumb

Use Discovery to expose hidden assumptions. Use SpecGuard Review to challenge weak implementation bases across discovery, spec, technical design, tests, and contracts.
