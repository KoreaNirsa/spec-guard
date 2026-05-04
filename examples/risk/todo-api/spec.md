# Spec: todo-api

## Problem

Authenticated users need to create, list, update, and delete their own todo items.

## Requirements

- The system must allow authenticated users to create todos.
- The system must list only todos owned by the current user.
- The system must allow users to mark their own todos as completed.
- The system must allow users to delete their own todos.
- The system must reject access to todos owned by another user.

## Acceptance Criteria

- [ ] Creating a todo stores the current user as owner.
- [ ] Listing todos returns only the current user's todos.
- [ ] Updating another user's todo returns `404 Not Found` or `403 Forbidden`.
- [ ] Deleting a todo records an audit event.

## Error Cases

- Missing title
- Empty title
- Duplicate create request
- Unauthorized request
- Cross-user todo access
- Delete request for a missing todo
