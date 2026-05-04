# TDD Scenarios: example

## Success Cases

- [ ] Valid credentials return access and refresh tokens.
- [ ] A valid refresh token rotates and returns a new token pair.

## Failure Cases

- [ ] Invalid credentials return a generic `401`.
- [ ] Replayed refresh token revokes the token family.
- [ ] Locked accounts cannot login until the lock expires.

## Boundary Cases

- [ ] Failed login attempts are rate-limited by account and IP.
- [ ] Expired access tokens are rejected.
