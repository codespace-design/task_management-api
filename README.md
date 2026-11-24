# Task Management API

This project provides a lightweight Django REST Framework API for managing tasks.
It also includes a browser-based dashboard at `/` for managing tasks through the API.

## Additional documentation

- [Day 15 authentication review and API guide](docs/DAY-15-DELIVERABLES.md)
- [Day 14 deliverables](docs/DAY-14-DELIVERABLES.md)
- [Bug report summary](docs/BUG-REPORT.md)

## Local setup

1. Create a virtual environment and activate it.
2. Copy `.env.example` to `.env` for local development. It enables Django's
   development static-file server; keep `DEBUG=False` in production.
   Generate a unique local signing key with
   `python -c "import secrets; print(secrets.token_urlsafe(48))"` and replace
   the example `SECRET_KEY` value.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run database migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```
6. Open `http://127.0.0.1:8000/` to use the task dashboard.

## API endpoints

- `POST /api/auth/register/` — register as an employer or candidate
- `POST /api/auth/token/` — log in with email and password; receive access and refresh tokens
- `POST /api/auth/token/refresh/` — rotate a refresh token and get a new access token
- `POST /api/auth/logout/` — blacklist the authenticated user's refresh token
- `GET /api/profiles/candidate/` — view your candidate profile
- `POST /api/profiles/candidate/` — initialize or reactivate your candidate profile
- `PUT/PATCH /api/profiles/candidate/` — update your candidate profile
- `DELETE /api/profiles/candidate/` — soft-delete your candidate profile
- `GET /api/profiles/employer/` — view your employer profile
- `POST /api/profiles/employer/` — initialize or reactivate your employer profile
- `PUT/PATCH /api/profiles/employer/` — update your employer profile
- `DELETE /api/profiles/employer/` — soft-delete your employer profile
- `/api/profiles/candidate/<user_id>/` and `/api/profiles/employer/<user_id>/` — admin access by user ID
- `POST/PUT /api/profiles/candidate/resume/` — upload or replace your resume
- `GET /api/profiles/candidate/resume/` — download your resume
- `DELETE /api/profiles/candidate/resume/` — remove your resume without deleting your profile
- `/api/profiles/candidate/<user_id>/resume/` — admin access to a candidate's resume
- `GET /api/tasks/` — search, filter, and paginate tasks (any authenticated role)
- `POST /api/tasks/` — create a task (employer or admin)
- `GET /api/tasks/<id>/` — retrieve one task (any authenticated role)
- `PUT /api/tasks/<id>/` — replace a task (creator employer or admin)
- `PATCH /api/tasks/<id>/` — partially update a task (creator employer or admin)
- `DELETE /api/tasks/<id>/` — delete a task (creator employer or admin)

Registration requires an email, password, and role (`employer` or `candidate`);
phone is optional and unique when provided. Passwords are validated with Django's
configured validators and stored as hashes. New users start unverified. Admin
accounts must be created by staff using `python manage.py createsuperuser` or the
Django admin; public registration cannot assign the admin role.

All task API endpoints require a JWT access token. Candidates can read tasks;
employers can create and modify their own tasks, and admins can modify any
task. All authenticated roles can read tasks. Registration, login, and
token refresh are public endpoints; logout requires authentication. Send the
access token as `Authorization: Bearer <access-token>`. Access tokens expire
after five minutes; refresh tokens expire after one day, rotate on use, and are
blacklisted on logout. Store tokens securely in clients, never commit them, and
use HTTPS outside local development. A logged-out access token remains usable
until its short expiry; logout prevents further refreshes.
Schedule `python manage.py flushexpiredtokens` regularly to remove expired
blacklist records.

The task list uses page-number pagination and returns `count`, `next`,
`previous`, and `results`. Use `page` to select a page; page size defaults to
`API_PAGE_SIZE` (20) and can be overridden with `page_size`, capped by
`API_MAX_PAGE_SIZE` (100). Both settings can be configured through environment
variables.

`GET /api/tasks/` supports `search` (case-insensitive keyword matching in title
and description), `role` (`admin`, `employer`, or `candidate` based on the
creator's role), `status` (`pending` or `completed`), and inclusive
`created_after` / `created_before` dates in `YYYY-MM-DD` format. Invalid filter
values return `400`. New tasks record their creator and include
`created_by_role` in responses; existing tasks without a recorded creator
return `null`. Tasks remain readable to all authenticated users.

Task lists have stable newest-first ordering. Date/status filters and creator
role lookups use database indexes, and the creator relation is loaded with
`select_related` to avoid per-task queries. Keyword search currently uses
substring matching; for very large datasets, use a database-specific
full-text-search index or a dedicated search service.

API errors use a consistent JSON envelope:

```json
{
  "success": false,
  "status_code": 400,
  "message": "Validation failed.",
  "errors": {"title": ["This field is required."]}
}
```

The same envelope is used for authentication, permission, not-found, and
unexpected API server errors. Successful response bodies remain endpoint-
specific; creates return `201`, normal reads and updates return `200`, and
deletes return `204`. Import the Postman collection and environment from
`postman/` to run the API and authorization checks. See
`docs/BUG-REPORT.md` for the verification summary.

For example, log in with `{"email":"person@example.com","password":"..."}` at
`/api/auth/token/`, then send the returned access token as a Bearer token when
calling `/api/tasks/`. Send the returned refresh token to
`/api/auth/token/refresh/` before the access token expires. Logout requires both
the current access token and its matching refresh token.

Candidate profiles contain skills, education, experience, and expected salary.
Employer profiles contain company name, website URL, company size, and a
verification status. Profiles are initialized when an account is registered.
Profile endpoints let the owner initialize/update or reactivate their profile;
deletion marks it inactive rather than removing its data. Inactive profiles
return 404 until reactivated. Admins can view and update candidate or employer
profiles by the associated user's ID. Only admins can change an employer's
verification status. Profile endpoints require an authenticated user with the
corresponding role, or an admin.

Resume files are uploaded as `multipart/form-data` in the `resume` field. PDF,
DOC, and DOCX files up to 5 MB are supported; extension, supplied MIME
type, and basic file signatures/container structure are validated. Files are
stored under `MEDIA_ROOT` with a generated name, and a successful replacement
removes the previous stored file. Resume downloads go through the authenticated
API and are sent as attachments; the API does not expose a public media URL.
`MEDIA_ROOT` and `MEDIA_URL` configure local development storage. Production
deployments should use private object storage or ensure the media directory is
not publicly served, and should add malware scanning before documents are used
or distributed. Signature checks do not detect malware or guarantee a document
is safe to open.

The browser dashboard offers login and registration. Its tokens stay in memory
for the current page session; signing in again is required after a reload.
Reusable `IsAdmin`, `IsEmployer`, `IsCandidate`, and `IsEmployerOrAdmin`
permissions are available in `apps.accounts.permissions`. Role checks are
applied as Django REST Framework permissions so they run after JWT
authentication. The task API has no job-posting or application models/endpoints;
those domain features are not represented by this task-management API.

Tasks are readable by all authenticated users. Employers can update or delete
only tasks they created; administrators can manage any task. Legacy tasks with
no recorded creator can be modified only by administrators.

This project uses a custom email-based user model (`AUTH_USER_MODEL` is
`accounts.User`). Configure it before the first database migration in a new
environment. Existing databases created with Django's default user model need a
backed-up, planned data migration before switching to this model. For production,
also configure secure secrets, email verification, and deployment-specific
permissions.

For production, set `DEBUG=False`, configure a secure `SECRET_KEY` and
`ALLOWED_HOSTS`, and run `python manage.py collectstatic`. Serve the collected
files from `STATIC_ROOT` using your deployment platform or web server. Configure
HTTPS and a production-grade database and cache before deploying authentication.
