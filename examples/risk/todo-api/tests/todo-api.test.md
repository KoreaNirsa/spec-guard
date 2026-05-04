# TDD Scenarios: todo-api

## Source

- Spec: `spec.md`

## Success Cases

- [ ] Creating a todo stores the current user as owner.
- [ ] Listing todos returns only the current user's todos.
- [ ] Updating another user's todo returns `404 Not Found` or `403 Forbidden`.
- [ ] Deleting a todo records an audit event.

## Failure Cases

- [ ] Missing title
- [ ] Empty title
- [ ] Duplicate create request
- [ ] Unauthorized request
- [ ] Cross-user todo access
- [ ] Delete request for a missing todo

## Boundary Cases

- [ ] Empty values, maximum values, and duplicate requests are handled.
- [ ] Concurrent or repeated requests do not create unsafe side effects.

## Notes

Generated from a spec with 865 characters. Replace these scenarios with executable tests before implementation.
