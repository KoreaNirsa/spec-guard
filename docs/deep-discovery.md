# Discovery

Discovery is SpecGuard's pre-spec exploration step.

It is adapted from the idea of a 100-question sequential self-interrogation framework, but SpecGuard uses 24 focused questions so the workflow stays usable.

In public workflow language, prefer `Discovery`. `Deep Discovery` can be used as the name of the technique or prompt pattern behind the artifact, but the project artifact should stay simple: `discovery.md`.

## Terminology

Recommended public term: `Discovery`.

Why:

- It is simple enough for contributors to understand without learning a new branded method first.
- It leaves room for multiple discovery techniques later.
- It keeps the workflow readable: `Discovery -> Spec -> Design -> Grill Me`.

Other terms considered:

- `Deep Discovery`: strong technique name, but it can sound heavier than the artifact needs to be.
- `SDD Discovery`: precise, but less friendly as a file and CLI concept.
- `Spec Discovery`: clear, but too close to the spec itself.
- `Intent Discovery`: useful conceptually, but less direct for engineering workflow docs.

## Position In The Workflow

```text
Discovery
  -> Spec
  -> Design
  -> Grill Me
  -> TDD
  -> Contract Check
```

Discovery asks what should be understood before a spec and design harden. Grill Me challenges the full SDD artifact set before implementation outputs are produced. They do not compete when used in that order.

## Question Phases

| Phase | Questions | Focus |
| --- | --- | --- |
| Foundation | Q1-Q4 | Goal, users, constraints, assumptions |
| Mechanisms | Q5-Q8 | Components, data flow, dependencies, state |
| Stress Test | Q9-Q12 | Edge cases, concurrency, security, recovery |
| Differentiation | Q13-Q15 | Existing options, unique value, non-goals |
| Feasibility | Q16-Q18 | Buildability, blockers, validation |
| Improvement | Q19-Q21 | Simplification, automation, unknowns |
| Synthesis | Q22-Q24 | Decision, required artifacts, stop conditions |

## Rule Of Thumb

Use Discovery to expose hidden assumptions. Use Grill Me to challenge weak implementation bases across discovery, spec, design, tests, and contracts.
