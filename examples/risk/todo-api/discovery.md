# Deep Discovery: todo-api

## Foundation

- Goal: Let authenticated users manage todo items.
- User impact: Users need reliable personal task storage.
- Constraints: Keep CRUD API small for MVP.
- Assumption to test: Authentication alone may be treated as enough authorization.

## Mechanisms

- Components: API layer, todo service, repository, auth middleware.
- Data flow: Request enters API, service validates input, repository reads or writes by todo id, response returns a todo DTO.
- Dependencies: Auth middleware and todo database.
- State: Active, completed, deleted.

## Stress Test

- Bad input break: Missing title should be rejected.
- Concurrency break: Duplicate create requests can create duplicate todos.
- Security boundary: Cross-user read, update, or delete is the likely failure.
- Hard recovery: Hard delete can remove data without auditability.

## Differentiation

- Existing option: A generic CRUD scaffold can create endpoints quickly.
- Difference: SpecGuard should catch owner scoping and delete policy gaps before code generation.
- Non-goal: Collaboration or sharing is outside the MVP.

## Feasibility

- MVP build: Create, list, update, delete.
- Blocker: Owner scoping and delete semantics are not clear enough yet.
- Validation: Grill Me should block this design until ownership and deletion are explicit.

## Improvement

- Simplify: Define owner-scoped repository queries before adding filters or labels.
- Automate later: Contract examples can assert owner-safe response shapes.
- Open question: Should delete be soft delete with audit logging?

## Synthesis

- Decision: Do not implement until ownership boundary and delete semantics are fixed.
- Required artifacts: spec.md, design.md, grill.md, grill.json, tests, and OpenAPI contract.
- Stop condition: Any design that reads or writes todos by id without owner scope should be blocked.
