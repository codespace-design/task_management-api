# Task Management API

This project provides a lightweight Django REST Framework API for managing tasks.

## Local setup

1. Create a virtual environment and activate it.
2. Copy `.env.example` to `.env` and update the values for your local environment.
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

## API endpoints

- `GET /api/tasks/` — list all tasks
- `POST /api/tasks/` — create a task
- `GET /api/tasks/<id>/` — retrieve one task
- `PUT /api/tasks/<id>/` — replace a task
- `PATCH /api/tasks/<id>/` — partially update a task
- `DELETE /api/tasks/<id>/` — delete a task

The demonstration API intentionally has no authentication.
