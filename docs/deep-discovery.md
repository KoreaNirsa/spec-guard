# Deep Discovery

Deep Discovery is SpecGuard's pre-spec exploration step.

It is adapted from the idea of a 100-question sequential self-interrogation framework, but the MVP uses 24 focused questions so the workflow stays usable.

## Position In The Workflow

```text
Deep Discovery
  -> Spec
  -> Design
  -> Grill Me
  -> TDD
  -> Contract Check
```

Deep Discovery asks what should be understood before a design exists. Grill Me attacks the design after it exists. They do not compete when used in that order.

## Question Phases

| Phase | Questions | Focus |
| --- | --- | --- |
| Foundation | Q1-Q4 | Goal, users, constraints, assumptions |
| Mechanisms | Q5-Q8 | Components, data flow, dependencies, state |
| Stress Test | Q9-Q12 | Edge cases, concurrency, security, recovery |
| Differentiation | Q13-Q15 | Existing options, unique value, non-goals |
| Feasibility | Q16-Q18 | MVP buildability, blockers, validation |
| Improvement | Q19-Q21 | Simplification, automation, unknowns |
| Synthesis | Q22-Q24 | Decision, required artifacts, stop conditions |

## Rule Of Thumb

Use Deep Discovery to discover hidden assumptions. Use Grill Me to punish weak designs.
