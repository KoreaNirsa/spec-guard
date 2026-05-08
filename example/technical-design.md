# Technical Design: Todo Privacy API

## Architecture

- API layer accepts create, list, update, and delete todo requests.
- TodoService validates input fields and calls TodoRepository.
- TodoRepository reads and writes todos by `todo_id`.
- Data model fields: `todo_id`, `title`, `status`, `created_at`, `updated_at`.

## Data Flow

1. Caller sends a todo request with an access token.
2. The service validates that the token exists.
3. The service reads or writes todos using `todo_id`.
4. The service returns the todo response or a documented error.

## State

- Initial state: request received.
- Valid states: created, active, completed, deleted.
- Invalid states: missing token, empty title, unknown todo id.
- Terminal state: success response or documented error.

## Failure Handling

- Missing access token returns `401 UNAUTHENTICATED`.
- Unknown `todo_id` returns `404 TODO_NOT_FOUND`.
- Empty title returns `400 INVALID_TITLE`.
- Repository write failure returns `500 TODO_WRITE_FAILED`.
