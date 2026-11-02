# Task Management API

This project provides a lightweight Django REST Framework API for managing tasks.
It also includes a browser-based dashboard at `/` for managing tasks through the API.

## Local setup

1. Create a virtual environment and activate it.
2. Copy `.env.example` to `.env` for local development. It enables Django's
   development static-file server; keep `DEBUG=False` in production.
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

- `GET /api/tasks/` — list all tasks
- `POST /api/tasks/` — create a task
- `GET /api/tasks/<id>/` — retrieve one task
- `PUT /api/tasks/<id>/` — replace a task
- `PATCH /api/tasks/<id>/` — partially update a task
- `DELETE /api/tasks/<id>/` — delete a task

The demonstration API intentionally has no authentication.

For production, set `DEBUG=False`, configure a secure `SECRET_KEY` and
`ALLOWED_HOSTS`, and run `python manage.py collectstatic`. Serve the collected
files from `STATIC_ROOT` using your deployment platform or web server.
