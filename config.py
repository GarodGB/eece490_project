import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Load local environment variables for development/demo (especially OPENAI_API_KEY).
# .env is intentionally not meant to be committed to GitHub.
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except Exception:
    pass

USE_MYSQL = os.environ.get('USE_MYSQL', '').lower() in ('1', 'true', 'yes')
DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', 8889))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', 'root')
DB_NAME = os.environ.get('DB_NAME', 'smart_academic')

INSTANCE_DIR = BASE_DIR / 'instance'
INSTANCE_DIR.mkdir(exist_ok=True)
SQLITE_DB_PATH = INSTANCE_DIR / 'smart_academic.db'

SECRET_KEY = os.environ.get('SECRET_KEY', 'academic-planning-secret-key-2024')
DEBUG = True
HOST = '0.0.0.0'
PORT = int(os.environ.get('PORT', '5005'))

# Dev reloader restarts the process when files change. Set FLASK_USE_RELOADER=0 if the
# server appears to restart endlessly (IDE touching files, SQLite quirks, etc.).
FLASK_USE_RELOADER = os.environ.get('FLASK_USE_RELOADER', 'true').lower() in ('1', 'true', 'yes')

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
ADVISOR_USE_OPENAI = os.environ.get('ADVISOR_USE_OPENAI', 'true').lower() in ('1', 'true', 'yes')

DATA_DIR = BASE_DIR / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
PREREQUISITES_FILE = DATA_DIR / 'prerequisites.csv'
ML_MODELS_DIR = BASE_DIR / 'ml' / 'models'

GRADE_POINTS = {
    'A+': 4.3, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D+': 1.3, 'D': 1.0, 'D-': 0.7,
    'F': 0.0, 'W': 0.0, 'I': 0.0
}

STRATEGIES = ['easy', 'balanced', 'fast']

MIN_CREDITS = 12
MAX_CREDITS = 18
DEFAULT_CREDITS = 15
