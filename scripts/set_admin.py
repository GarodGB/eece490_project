
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from database.db import get_db
from database.models import Student


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/set_admin.py <username>")
        print("Example: python scripts/set_admin.py admin")
        return
    username = sys.argv[1].strip()
    db = get_db()
    try:
        student = db.query(Student).filter(Student.username == username).first()
        if not student:
            print(f"[ERROR] No user found with username: {username!r}")
            return
        student.is_admin = True
        db.commit()
        print(f"[OK] User {username!r} is now an admin.")
    except Exception as e:
        db.rollback()
        print(f"[ERROR] {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
