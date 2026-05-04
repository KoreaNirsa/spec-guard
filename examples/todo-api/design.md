# Design: todo-api

## Architecture

The API layer authenticates requests and forwards todo commands to the todo service. The todo service reads and writes todo rows through a repository.

## Data Flow

1. Client sends an authenticated request.
2. API extracts the current user from the access token.
3. Todo service validates command input.
4. Repository reads or writes rows by todo id.
5. Delete requests remove the todo row.
6. API returns a todo DTO or an error response.

## State

- Initial state: active
- Valid states: active, completed, deleted
- Invalid states: completed without a title
- Terminal state: deleted

## Dependencies

- Auth middleware
- Todo database

## Failure Handling

- Database timeout returns `503 Service Unavailable`.
- Duplicate create requests are not yet defined.
