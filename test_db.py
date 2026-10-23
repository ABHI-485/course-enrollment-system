from sqlalchemy import text
from app.database import engine

try:
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        print("PostgreSQL connection successful!")
        print("Test result:", result.scalar())

except Exception as error:
    print("Database connection failed.")
    print("Error:", error)