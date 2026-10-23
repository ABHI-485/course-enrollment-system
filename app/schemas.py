
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------- Course schemas ----------

class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=150)
    description: str | None = None
    capacity: int = Field(gt=0)
    fee: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class CourseUpdate(BaseModel):
    # Optional new primary-key value. When changed, PostgreSQL cascades the
    # new ID to enrollments.course_id after the one-time FK migration runs.
    id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = None
    capacity: int | None = Field(default=None, gt=0)
    seats_available: int | None = Field(default=None, ge=0)
    fee: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    capacity: int
    seats_available: int
    fee: Decimal


# ---------- Student schemas ----------

class StudentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr


class StudentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None


class StudentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr


# ---------- Enrollment schemas ----------

class EnrollmentCreate(BaseModel):
    student_id: int = Field(gt=0)
    course_id: int = Field(gt=0)


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int
    course_id: int
    status: str
