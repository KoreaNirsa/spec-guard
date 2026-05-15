# Technical Design: todo-api

## Architecture

- Feature boundary: todo-api.
- Intent source: Authenticated users need to create, list, update, and delete their own todo items.
- Application layer: Coordinates validation, state changes, and responses for todo-api.
- Validation layer: Converts acceptance criteria and error cases into executable checks.
- Contract boundary: API or integration shape is captured under `contracts/`.

## Data Flow

1. Caller sends a request for the feature.
2. The system validates required input, authorization, and state.
3. The application layer performs the operation defined by the spec.
4. The system returns a success response or a documented error.
5. Acceptance focus: Creating a todo stores the current user as owner.; Listing todos returns only the current user's todos.; Updating another user's todo returns `404 Not Found` or `403 Forbidden`.

## State

- Initial state: Request received and not yet validated.
- Valid states: Accepted, rejected, completed, failed.
- Invalid states: Unauthorized, malformed, conflicting, or unsupported request.
- Terminal state: Success response, documented error response, or blocked implementation issue.

## Dependencies

- Source spec: `spec.md`.
- Requirement focus: The system must allow authenticated users to create todos.; The system must list only todos owned by the current user.; The system must allow users to mark their own todos as completed.
- Entity focus: Feature state and request data are explicit implementation inputs.
- Test scenarios: Generated under `tests/` after SpecGuard Review passes.
- Contract: Generated under `contracts/` after SpecGuard Review passes.

## Failure Handling

- Expected failures: Missing title; Empty title; Duplicate create request
- Invalid input returns a clear error.
- Unauthorized access is rejected before state change.
- Ambiguous behavior becomes a spec update instead of implementation guesswork.
- NOT_READY SpecGuard Review findings block implementation handoff.
