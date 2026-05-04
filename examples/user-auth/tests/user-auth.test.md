# TDD Scenarios: user-auth

## Source

- Spec: `spec.md`

## Success Cases

- [ ] Valid credentials return an access token and refresh token.
- [ ] Invalid credentials return `401 Unauthorized`.
- [ ] Missing email or password returns `400 Bad Request`.
- [ ] Expired access tokens are rejected.
- [ ] Refresh token replay is detected and rejected.

## Failure Cases

- [ ] Missing email
- [ ] Missing password
- [ ] Invalid password
- [ ] Unknown user
- [ ] Expired access token
- [ ] Replayed refresh token
- [ ] Too many failed login attempts

## Boundary Cases

- [ ] Empty values, maximum values, and duplicate requests are handled.
- [ ] Concurrent or repeated requests do not create unsafe side effects.

## Notes

Generated from a spec with 856 characters. Replace these scenarios with executable tests before implementation.
