
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db
from database.models import Student
from werkzeug.security import generate_password_hash

USERNAME = "admin"
EMAIL = "admin@gmail.com"
PASSWORD = "admin123"


def main():
    db = get_db()
    try:
        existing = db.query(Student).filter(
            (Student.username == USERNAME) | (Student.email == EMAIL)
        ).first()
        if existing:
            existing.is_admin = True
            existing.password_hash = generate_password_hash(PASSWORD)
            db.commit()
            print(f"[OK] Updated existing user {existing.username!r} as admin (password reset to {PASSWORD!r}).")
        else:
            student = Student(
                username=USERNAME,
                email=EMAIL,
                password_hash=generate_password_hash(PASSWORD),
                major="ECE",
                strategy="balanced",
                workload_tolerance=0.5,
                gpa=0.0,
                is_admin=True,
            )
            db.add(student)
            db.commit()
            print(f"[OK] Created admin user: {USERNAME!r} / {EMAIL!r} / password {PASSWORD!r}")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
