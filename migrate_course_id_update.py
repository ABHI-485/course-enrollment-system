r"""Enable safe changes to Course IDs in the Course Enrollment System.

Run once from the project root:
    .\.venv\Scripts\python.exe migrate_course_id_update.py

This keeps enrollment history intact by making PostgreSQL update
`enrollments.course_id` automatically when `courses.id` changes.
"""
from __future__ import annotations

from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def migrate(engine: Engine) -> bool:
    inspector = inspect(engine)
    foreign_keys = inspector.get_foreign_keys("enrollments")
    target = next(
        (
            fk for fk in foreign_keys
            if fk.get("referred_table") == "courses"
            and fk.get("constrained_columns") == ["course_id"]
            and fk.get("referred_columns") == ["id"]
        ),
        None,
    )
    if target is None or not target.get("name"):
        raise RuntimeError(
            "Could not find the enrollments.course_id -> courses.id foreign key. "
            "Check that the project tables exist in the configured database."
        )

    options = target.get("options") or {}
    if str(options.get("onupdate", "")).upper() == "CASCADE":
        print("Migration not needed: course ID updates already cascade to enrollments.")
        return False

    quote = engine.dialect.identifier_preparer.quote
    constraint_name = quote(target["name"])
    child_table = quote("enrollments")
    parent_table = quote("courses")
    child_columns = ", ".join(quote(col) for col in target["constrained_columns"])
    parent_columns = ", ".join(quote(col) for col in target["referred_columns"])
    statement = (
        f"ALTER TABLE {child_table} ADD CONSTRAINT {constraint_name} "
        f"FOREIGN KEY ({child_columns}) REFERENCES {parent_table} ({parent_columns})"
    )
    ondelete = options.get("ondelete")
    if ondelete:
        statement += f" ON DELETE {str(ondelete).upper()}"
    statement += " ON UPDATE CASCADE"
    if options.get("deferrable") is True:
        statement += " DEFERRABLE"
        initially = options.get("initially")
        if initially:
            statement += f" INITIALLY {str(initially).upper()}"

    # Do both DDL statements in one PostgreSQL transaction so a failed add
    # rolls back the drop and leaves the original constraint in place.
    with engine.begin() as connection:
        connection.execute(text(
            f"ALTER TABLE {child_table} DROP CONSTRAINT {constraint_name}"
        ))
        connection.execute(text(statement))

    print("Migration complete: changing courses.id will update enrollment references automatically.")
    return True


def main() -> None:
    load_dotenv()
    # Reuse the application's configured engine and ensure SQLAlchemy knows
    # about the project's tables before inspecting the foreign key.
    from app.database import Base, engine
    from app import models  # noqa: F401 - registers table mappings on Base

    Base.metadata.create_all(bind=engine)
    try:
        migrate(engine)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
