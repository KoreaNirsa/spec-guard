# Spec: user-auth

## Problem

Users need a secure login flow that issues tokens for protected API access.

## Requirements

- The system must authenticate users with email and password.
- The system must issue an access token after successful login.
- The system must reject invalid credentials with a generic error.
- The system must protect authenticated endpoints from anonymous access.

## Acceptance Criteria

- [ ] Valid credentials return an access token and refresh token.
- [ ] Invalid credentials return `401 Unauthorized`.
- [ ] Missing email or password returns `400 Bad Request`.
- [ ] Expired access tokens are rejected.
- [ ] Refresh token replay is detected and rejected.

## Error Cases

- Missing email
- Missing password
- Invalid password
- Unknown user
- Expired access token
- Replayed refresh token
- Too many failed login attempts
