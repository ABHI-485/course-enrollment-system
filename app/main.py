
from fastapi import FastAPI, Depends, status
from sqlalchemy.orm import Session

from app.database import Base, engine, get_db
from app import models, crud

from app.schemas import (
    CourseCreate,
    CourseUpdate,
    CourseResponse,
    StudentCreate,
    StudentUpdate,
    StudentResponse,
    EnrollmentCreate,
    EnrollmentResponse,
)


# Create database tables if they do not exist
Base.metadata.create_all(bind=engine)


# Initialize FastAPI application
app = FastAPI(
    title="Course Enrollment System",
    description="Manage courses, students, and enrollments",
    version="1.0.0",
)


# ==================== HOME ====================

@app.get("/", tags=["Home"])
def home():
    return {
        "message": "Course Enrollment System API is running!"
    }


# ==================== COURSES ====================

@app.get(
    "/courses",
    response_model=list[CourseResponse],
    tags=["Courses"],
    summary="List Courses",
)
def list_courses(db: Session = Depends(get_db)):
    return crud.get_courses(db)


@app.get(
    "/courses/{course_id}",
    response_model=CourseResponse,
    tags=["Courses"],
    summary="Get Course",
)
def read_course(
    course_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_course(db, course_id)


@app.post(
    "/courses",
    response_model=CourseResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Courses"],
    summary="Create Course",
)
def add_course(
    data: CourseCreate,
    db: Session = Depends(get_db),
):
    return crud.create_course(db, data)


@app.put(
    "/courses/{course_id}",
    response_model=CourseResponse,
    tags=["Courses"],
    summary="Update Course",
)
def edit_course(
    course_id: int,
    data: CourseUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_course(db, course_id, data)


@app.delete(
    "/courses/{course_id}",
    tags=["Courses"],
    summary="Delete Course",
)
def remove_course(
    course_id: int,
    db: Session = Depends(get_db),
):
    return crud.delete_course(db, course_id)


# ==================== STUDENTS ====================

@app.get(
    "/students",
    response_model=list[StudentResponse],
    tags=["Students"],
    summary="List Students",
)
def list_students(db: Session = Depends(get_db)):
    return crud.get_students(db)


@app.get(
    "/students/{student_id}",
    response_model=StudentResponse,
    tags=["Students"],
    summary="Get Student",
)
def read_student(
    student_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_student(db, student_id)


@app.post(
    "/students",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Students"],
    summary="Create Student",
)
def add_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
):
    return crud.create_student(db, data)


@app.put(
    "/students/{student_id}",
    response_model=StudentResponse,
    tags=["Students"],
    summary="Update Student",
)
def edit_student(
    student_id: int,
    data: StudentUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_student(db, student_id, data)


@app.delete(
    "/students/{student_id}",
    tags=["Students"],
    summary="Delete Student",
)
def remove_student(
    student_id: int,
    db: Session = Depends(get_db),
):
    return crud.delete_student(db, student_id)


# ==================== ENROLLMENTS ====================

@app.post(
    "/enroll",
    response_model=EnrollmentResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Enrollments"],
    summary="Enroll Student",
)
def enroll(
    data: EnrollmentCreate,
    db: Session = Depends(get_db),
):
    return crud.enroll_student(
        db,
        data.student_id,
        data.course_id,
    )


@app.get(
    "/enrollments/student/{student_id}",
    response_model=list[EnrollmentResponse],
    tags=["Enrollments"],
    summary="List Student Enrollments",
)
def list_student_enrollments(
    student_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_student_enrollments(db, student_id)


@app.get(
    "/enrollments/course/{course_id}",
    response_model=list[EnrollmentResponse],
    tags=["Enrollments"],
    summary="List Course Enrollments",
)
def list_course_enrollments(
    course_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_course_enrollments(db, course_id)


@app.delete(
    "/enrollments/{enrollment_id}",
    tags=["Enrollments"],
    summary="Cancel Enrollment",
)
def unenroll(
    enrollment_id: int,
    db: Session = Depends(get_db),
):
    return crud.cancel_enrollment(db, enrollment_id)
