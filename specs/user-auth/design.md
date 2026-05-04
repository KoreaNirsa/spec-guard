# Design: user-auth

## Architecture

The API layer accepts login and refresh requests. The auth service validates credentials against the user store. The token service issues short-lived access tokens and rotating refresh tokens. Audit logging records successful and failed authentication events.

## Data Flow

1. Client submits email and password to `POST /auth/login`.
2. API validates required fields and basic email format.
3. Auth service checks credentials using the user store.
4. Rate limiter records failed attempts by account and IP.
5. Token service issues a 15 minute access token and rotating refresh token.
6. API returns token payload or a generic authentication error.

## State

- Initial state: anonymous
- Valid states: anonymous, authenticated, refreshable, locked
- Invalid states: authenticated without issued token, refreshable with reused refresh token
- Terminal state: authenticated, rejected, or locked

## Dependencies

- User store
- Token signer
- Refresh token store
- Rate limiter
- Audit logger

## Failure Handling

- User store timeout returns `503 Service Unavailable`.
- Token signing failure returns `500 Internal Server Error` and does not authenticate the user.
- Refresh token replay revokes the token family.
- Too many failed attempts locks the account for 15 minutes.
