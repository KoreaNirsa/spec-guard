# Deep Discovery: {{ feature_name }}

Use this before writing `spec.md` or `design.md`. Keep answers short, concrete, and honest.

## Foundation

1. What problem are we actually solving?
2. Who fails or suffers if this is not built?
3. What constraints are non-negotiable?
4. What assumptions are we making too early?

## Mechanisms

5. What are the main moving parts?
6. What data enters, changes, and leaves the system?
7. Which dependencies can fail or lie?
8. What state must be tracked explicitly?

## Stress Test

9. What breaks first under bad input?
10. What breaks first under concurrency?
11. What security boundary can be bypassed?
12. What failure would be hardest to recover from?

## Differentiation

13. What existing workflow or tool already solves part of this?
14. What is genuinely different about this approach?
15. What should we intentionally not build?

## Feasibility

16. What can be built in one MVP pass?
17. What dependency, policy, or workflow can block delivery?
18. What can be validated without full implementation?

## Improvement

19. What can be simplified?
20. What can be automated later?
21. What important question is still unanswered?

## Synthesis

22. What is the final decision?
23. What artifacts must exist before implementation?
24. What would make us stop or redesign?
