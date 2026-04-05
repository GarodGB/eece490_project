import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from database.db import init_db, test_connection
from scripts.load_data_to_db_fast import load_courses_fast, load_prerequisites_fast

def main():
    print("=" * 60)
    print("DATABASE SETUP (FAST MODE)")
    print("=" * 60)
    
    print("\nTesting database connection...")
    if not test_connection():
        print("[ERROR] Database connection failed!")
        print("Please check your database credentials in config.py")
        return
    
    print("[OK] Database connection successful!")
    
    print("\nInitializing database...")
    try:
        init_db()
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return
    
    print("\n" + "-" * 60)
    try:
        course_dict = load_courses_fast()
    except Exception as e:
        print(f"[ERROR] Failed to load courses: {e}")
        return
    
    print("\n" + "-" * 60)
    try:
        load_prerequisites_fast(course_dict)
    except Exception as e:
        print(f"[ERROR] Failed to load prerequisites: {e}")
        return
    
    print("\n" + "=" * 60)
    print("DATABASE SETUP COMPLETE!")
    print("=" * 60)
    print("\nYou can now run the application with: python app.py")

if __name__ == '__main__':
    main()
