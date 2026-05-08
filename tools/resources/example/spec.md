# Spec: Todo Privacy API

## Requirements

- The system must let logged-in users create todos.
- Todos are private user data.
- The system must let any logged-in user list todos.
- The system must let any logged-in user update any todo by `todo_id`.
- The system must let any logged-in user delete any todo by `todo_id`.
- The server does not need to check which user created the todo.
- The client is responsible for showing each user only their own todos.

## Acceptance Criteria

- [ ] A logged-in user can create a todo with `title` and `status`.
- [ ] A logged-in user can list todos.
- [ ] A logged-in user can update a todo by `todo_id`.
- [ ] A logged-in user can delete a todo by `todo_id`.
- [ ] A user can update a todo created by another user when the `todo_id` is known.

## Error Cases

- Missing access token returns `401 UNAUTHENTICATED`.
- Unknown `todo_id` returns `404 TODO_NOT_FOUND`.
- Empty title returns `400 INVALID_TITLE`.
