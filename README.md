
# Course Enrollment System

A REST API built with FastAPI and PostgreSQL for managing courses, students, and enrollments. The system tracks available seats, prevents overbooking, rejects duplicate active enrollments, and preserves cancellation history.

## Features

- Create, read, update, and delete courses.
- Register, view, update, and delete students.
- Enroll students in courses with limited seat capacity.
- Prevent enrollment when a course has no available seats.
- Prevent duplicate active enrollment in the same course.
- Cancel enrollments while preserving enrollment history.
- List enrollments by student or course.
- Validate request data using Pydantic.
- Explore endpoints through Swagger UI.

## Technology Stack

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL
- Psycopg
- Uvicorn

## Project Structure

```text
Course Enrollment System/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   └── crud.py
├── .env
├── .gitignore
├── README.md
└── requirements.txt
```

## Prerequisites

- Python installed
- PostgreSQL installed and running
- VS Code (recommended)

## Setup Instructions

### 1. Clone the repository

```bash
git clone YOUR_GITHUB_REPOSITORY_URL
cd "Course Enrollment System"
```

Replace `YOUR_GITHUB_REPOSITORY_URL` with your actual repository URL.

### 2. Create and activate a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
python -m pip install -r requirements.txt
```

### 4. Create the PostgreSQL database

Create a database named:

```text
course_enrollment_db
```

### 5. Configure environment variables

Create a `.env` file in the project root:

```text
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/course_enrollment_db
```

Replace `YOUR_PASSWORD` with your PostgreSQL password. Do not commit `.env` to GitHub.

### 6. Start the application

Run this command from the project root:

```powershell
uvicorn app.main:app --reload
```

### 7. Open the API documentation

Swagger UI:

http://127.0.0.1:8000/docs

API home:

http://127.0.0.1:8000/

## API Endpoints

### Courses

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/courses` | List courses |
| GET | `/courses/{course_id}` | Get a course |
| POST | `/courses` | Create a course |
| PUT | `/courses/{course_id}` | Update a course |
| DELETE | `/courses/{course_id}` | Delete a course if it has no enrollment history |

### Students

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/students` | List students |
| GET | `/students/{student_id}` | Get a student |
| POST | `/students` | Register a student |
| PUT | `/students/{student_id}` | Update a student |
| DELETE | `/students/{student_id}` | Delete a student if they have no enrollment history |

### Enrollments

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/enroll` | Enroll a student in a course |
| GET | `/enrollments/student/{student_id}` | List a student's enrollments |
| GET | `/enrollments/course/{course_id}` | List a course's enrollments |
| DELETE | `/enrollments/{enrollment_id}` | Cancel an enrollment |

## Enrollment Rules

- Course capacity must be greater than zero.
- Available seats cannot be negative or exceed capacity.
- A student cannot have duplicate active enrollments in the same course.
- Enrollment is rejected when no seats remain.
- Cancellation restores an available seat and preserves the enrollment record.
- Students and courses with enrollment history cannot be deleted.

## Testing

Use Swagger UI at `/docs` to test the endpoints, including successful requests, invalid input, duplicate enrollment, full-course enrollment, and cancellation.

## License

Add your chosen license before distributing this project publicly.
