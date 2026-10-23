
from fastapi import HTTPException
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Course, Student, Enrollment
from app.schemas import CourseCreate, CourseUpdate, StudentCreate, StudentUpdate


# ==================== COURSES ====================

def get_courses(db: Session):
    return db.scalars(select(Course).order_by(Course.id)).all()


def get_course(db: Session, course_id: int):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def create_course(db: Session, data: CourseCreate):
    course = Course(
        title=data.title,
        description=data.description,
        capacity=data.capacity,
        seats_available=data.capacity,
        fee=data.fee,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return course


def update_course(db: Session, course_id: int, data: CourseUpdate):
    """Update course details and optionally change its ID.

    The database must have ON UPDATE CASCADE on enrollments.course_id; the
    one-time migration script in the project installs that foreign-key rule.
    """
    course = get_course(db, course_id)
    original_id = int(course.id)
    changes = data.model_dump(exclude_unset=True)
    requested_id = changes.pop("id", None)
    target_id = original_id if requested_id is None else int(requested_id)

    if target_id <= 0:
        raise HTTPException(status_code=400, detail="Course ID must be a positive integer")

    if target_id != original_id and db.get(Course, target_id) is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Course ID {target_id} is already used by another course",
        )

    new_capacity = changes.get("capacity", course.capacity)
    new_seats = changes.get("seats_available", course.seats_available)

    if new_seats > new_capacity:
        raise HTTPException(
            status_code=400,
            detail="Available seats cannot exceed course capacity",
        )

    if new_capacity - new_seats < course.capacity - course.seats_available:
        raise HTTPException(
            status_code=400,
            detail="Capacity cannot be reduced below the number of occupied seats",
        )

    for field, value in changes.items():
        setattr(course, field, value)

    # Assign the new primary key only after validating the requested target.
    if target_id != original_id:
        course.id = target_id

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                f"Could not change Course ID to {target_id}. The ID may already "
                "exist, or the database foreign-key migration may not have been run."
            ),
        ) from exc

    # If a manual ID is larger than the sequence value, move the sequence
    # forward to prevent a later auto-generated ID from colliding with it.
    if target_id != original_id:
        try:
            db.execute(text("""
                SELECT setval(
                    pg_get_serial_sequence('courses', 'id'),
                    GREATEST(
                        (SELECT COALESCE(MAX(id), 1) FROM courses),
                        nextval(pg_get_serial_sequence('courses', 'id'))
                    ),
                    true
                )
            """))
            db.commit()
        except Exception:
            db.rollback()
            # The primary-key update has already committed. Don't report the
            # change itself as failed solely because the sequence sync failed;
            # show a clear message in application logs instead.
            import logging
            logging.getLogger(__name__).exception(
                "Course ID changed, but the PostgreSQL ID sequence could not be synchronized."
            )

    db.expire_all()
    updated_course = db.get(Course, target_id)
    if updated_course is None:
        raise HTTPException(status_code=500, detail="Course updated but could not be reloaded")
    return updated_course


def delete_course(db: Session, course_id: int):
    course = get_course(db, course_id)

    if db.scalar(
        select(Enrollment.id).where(Enrollment.course_id == course_id).limit(1)
    ) is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a course with enrollment history",
        )

    db.delete(course)
    db.commit()
    return {"message": "Course deleted successfully"}


# ==================== STUDENTS ====================

def get_students(db: Session):
    return db.scalars(select(Student).order_by(Student.id)).all()


def get_student(db: Session, student_id: int):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


def create_student(db: Session, data: StudentCreate):
    existing = db.scalar(
        select(Student).where(Student.email == str(data.email))
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A student with this email already exists",
        )

    student = Student(name=data.name, email=str(data.email))
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def update_student(db: Session, student_id: int, data: StudentUpdate):
    student = get_student(db, student_id)
    changes = data.model_dump(exclude_unset=True)

    if "email" in changes and changes["email"] is not None:
        changes["email"] = str(changes["email"])
        existing = db.scalar(
            select(Student).where(
                Student.email == changes["email"],
                Student.id != student_id,
            )
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="A student with this email already exists",
            )

    for field, value in changes.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


def delete_student(db: Session, student_id: int):
    student = get_student(db, student_id)

    if db.scalar(
        select(Enrollment.id).where(
            Enrollment.student_id == student_id
        ).limit(1)
    ) is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a student with enrollment history",
        )

    db.delete(student)
    db.commit()
    return {"message": "Student deleted successfully"}


# ==================== ENROLLMENTS ====================

def enroll_student(db: Session, student_id: int, course_id: int):
    try:
        get_student(db, student_id)
        get_course(db, course_id)

        existing = db.scalar(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
                Enrollment.status == "active",
            )
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="Student is already actively enrolled in this course",
            )

        # Reserve one seat only if a seat is still available.
        result = db.execute(
            update(Course)
            .where(
                Course.id == course_id,
                Course.seats_available > 0,
            )
            .values(seats_available=Course.seats_available - 1)
        )

        if result.rowcount == 0:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="No seats available for this course",
            )

        enrollment = Enrollment(
            student_id=student_id,
            course_id=course_id,
            status="active",
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return enrollment

    except Exception:
        db.rollback()
        raise


def get_student_enrollments(db: Session, student_id: int):
    get_student(db, student_id)
    return db.scalars(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.id)
    ).all()


def get_course_enrollments(db: Session, course_id: int):
    get_course(db, course_id)
    return db.scalars(
        select(Enrollment)
        .where(Enrollment.course_id == course_id)
        .order_by(Enrollment.id)
    ).all()


def cancel_enrollment(db: Session, enrollment_id: int):
    try:
        enrollment = db.get(Enrollment, enrollment_id)

        if enrollment is None:
            raise HTTPException(
                status_code=404,
                detail="Enrollment not found",
            )

        if enrollment.status == "cancelled":
            raise HTTPException(
                status_code=400,
                detail="Enrollment is already cancelled",
            )

        # Restore the seat and cancel the enrollment in one transaction.
        result = db.execute(
            update(Course)
            .where(
                Course.id == enrollment.course_id,
                Course.seats_available < Course.capacity,
            )
            .values(seats_available=Course.seats_available + 1)
        )

        if result.rowcount == 0:
            raise HTTPException(
                status_code=409,
                detail="Could not restore the course seat",
            )

        enrollment.status = "cancelled"
        db.commit()
        db.refresh(enrollment)
        return enrollment

    except Exception:
        db.rollback()
        raise
