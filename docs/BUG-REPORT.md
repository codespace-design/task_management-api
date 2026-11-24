# API Testing Bug Report

## Summary

| ID | Severity | Finding | Status |
|---|---|---|---|
| API-001 | Medium | API errors had endpoint/framework-specific shapes, making clients handle validation, authentication, permission, and not-found failures differently. | Fixed |
| API-002 | Medium | Unexpected API server errors could return Django's HTML error page instead of a JSON API response. | Fixed |

## Details

### API-001: Inconsistent API error responses

**Impact:** Clients could not reliably inspect failures using a common status/message/errors structure. Validation responses exposed field errors directly, while other failures used a `detail` key.

**Fix:** Added a centralized Django REST Framework exception handler that returns `success`, `status_code`, `message`, and `errors` for API exceptions. HTTP status codes remain unchanged.

### API-002: Non-JSON API server errors

**Impact:** An unexpected exception on an `/api/` route could produce an HTML 500 response, violating the API's JSON error contract.

**Fix:** Added API-only response middleware to format HTTP 500 responses as the standard JSON error envelope. Non-API responses are unchanged.

## Verification

The Postman collection in `postman/Task Management API.postman_collection.json`
covers registration, JWT login/refresh/logout, profile access, task CRUD,
validation failures, unauthenticated requests, and candidate role violations.
Run it in collection order with the matching local environment.

- `python manage.py test`: 55 tests passed.
- `ruff check .`: passed.
- Both Postman JSON exports parsed successfully.

The Postman requests are supplied but have not been executed against a running
server as part of this verification.
