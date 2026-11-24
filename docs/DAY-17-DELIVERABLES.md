# Day 17 – Job Listing, Filters, and Search

## Overview

The job discovery API exposes active listings publicly and returns paginated
results. It supports latest and featured feeds, keyword search, normalized
skill matching, and combined location, job type, salary, and experience
filters. Job ownership rules continue to apply to employer management routes.

## Listing endpoints

All routes are relative to `/api/`.

| Method and route | Authentication | Result |
|---|---|---|
| `GET /jobs/` | Public | Active jobs, filtered and paginated |
| `GET /jobs/featured/` | Public | Active jobs marked featured, filtered and paginated |
| `GET /jobs/latest/` | Public | Active jobs ordered newest first, filtered and paginated |
| `GET /jobs/<id>/` | Public | Active job detail; employers may read their own inactive/draft jobs and admins may read any job |

Candidates and anonymous visitors only see active listings. An employer's
normal `/jobs/` list is restricted to that employer's own jobs, including
draft and inactive entries; the featured and latest actions are public feeds
and return active listings. Admins can read all jobs in the normal list and
detail routes.

## Search and filters

Filters can be combined on the list, featured, and latest routes:

| Parameter | Example | Semantics |
|---|---|---|
| `search` | `?search=python engineer` | Case-insensitive terms. Every term must match at least one of title, description, location, experience text, or a job skill. |
| `skill` | `?skill=django` | Exact case-insensitive match against a normalized skill name. |
| `location` | `?location=remote` | Case-insensitive substring match in the location field. |
| `job_type` | `?job_type=full_time` | Exact choice: `full_time`, `part_time`, `contract`, `internship`, or `temporary`. |
| `min_experience_years` | `?min_experience_years=3` | Jobs whose maximum experience requirement is at least 3, or has no upper bound. |
| `max_experience_years` | `?max_experience_years=8` | Jobs whose minimum experience requirement is at most 8, or has no lower bound. |
| `min_salary` | `?min_salary=80000` | Jobs whose maximum salary is at least 80,000, or whose upper salary is undisclosed. |
| `max_salary` | `?max_salary=140000` | Jobs whose minimum salary is at most 140,000, or whose lower salary is undisclosed. |

The experience and salary filters are inclusive range-overlap checks. Jobs
with unspecified range endpoints are treated as open-ended. Supplying both
ends with the lower value greater than the upper value returns `400`. Invalid
numbers, negative values, unsupported job types, and search text longer than
200 characters, or skill names longer than 80 characters also return `400`
using the API's standard error envelope.

Example combined request:

```http
GET /api/jobs/?search=python%20engineer&skill=django&location=remote&job_type=full_time&min_experience_years=3&max_experience_years=8&min_salary=80000&max_salary=140000&page=1&page_size=20
```

## Pagination and ordering

The API uses page-number pagination. `page` chooses a page; `page_size`
defaults to `API_PAGE_SIZE` (20) and is capped by `API_MAX_PAGE_SIZE` (100).
Both settings are configurable through the environment and validated during
Django startup. A successful list response has this shape:

```json
{
  "count": 42,
  "next": "http://localhost:8000/api/jobs/?page=2",
  "previous": null,
  "results": [
    {
      "id": 12,
      "title": "Senior Python Engineer",
      "description": "Build and maintain API services.",
      "skills": ["django", "python"],
      "experience": "3+ years building backend applications",
      "minimum_experience_years": 3,
      "maximum_experience_years": 8,
      "minimum_salary": "80000.00",
      "maximum_salary": "140000.00",
      "location": "Remote, US",
      "job_type": "full_time",
      "status": "active",
      "is_featured": false,
      "employer": 7,
      "created_at": "2026-11-24T08:30:00Z",
      "updated_at": "2026-11-24T08:30:00Z"
    }
  ]
}
```

The model's stable ordering is newest `created_at` first, then descending ID
to break timestamp ties. Infinite-scroll clients can follow `next` until it
is `null`.

## Response fields

Job representations include `id`, `title`, `description`, `skills`,
`experience`, `minimum_experience_years`, `maximum_experience_years`,
`minimum_salary`, `maximum_salary`, `location`, `job_type`, `status`,
`is_featured`, `employer`, `created_at`, and `updated_at`. The employer field
is the owning user ID. Ownership, status, and featured state are not writable
through the REST API; employers manage lifecycle through the authenticated
activate/deactivate actions, and staff manage featuring through Django admin.

## Query and index design

- Job listings use `select_related("employer")` and prefetch skill entries to
  avoid per-result database queries during serialization.
- Status/date and status/featured/date indexes support the main active,
  featured, and latest feeds.
- Additional indexes cover employer/status, job type, salary bounds, and
  experience bounds.
- Skills are stored as per-job rows with a case-folded `normalized_name`.
  The name/job index supports exact skill filters; a per-job uniqueness
  constraint prevents duplicate skills differing only by case.
- Keyword skill matching uses an `EXISTS` subquery to avoid duplicate jobs in
  result pages. Other keyword fields use case-insensitive substring matching;
  for very large deployments, consider database full-text or trigram indexes
  after measuring the production query workload.
- Page-size limits cap response and serialization work.

Migration `0003_jobskill` copies the prior JSON skill arrays into the normalized
skill table. Migration `0004` removes the old JSON column only after that
backfill. Apply migrations with `python manage.py migrate`.

## Access control

Listing, featured, latest, and active detail reads are public. An employer
continues to see and mutate only its own jobs through the management routes;
other employers' job records are hidden with `404`. The public API never
accepts employer IDs, status, or `is_featured` as writable values. Candidates
cannot create or modify jobs. Administrators can read all jobs but API write
operations are employer-only.

## Verification

The test suite covers public active feeds, featured/latest behavior, combined
search and filters, range-validation errors, pagination, candidate visibility,
and employer ownership. The full Django suite passed with 69 tests; Ruff,
Django system checks, and migration consistency checks passed.
