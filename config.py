import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

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
PORT = 5005

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

DATA_DIR = BASE_DIR / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
PREREQUISITES_FILE = DATA_DIR / 'prerequisites.csv'
ML_MODELS_DIR = BASE_DIR / 'ml' / 'models'

GRADE_POINTS = {
    'A+': 4.0, 'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D+': 1.3, 'D': 1.0, 'D-': 0.7,
    'F': 0.0, 'W': 0.0, 'I': 0.0
}

STRATEGIES = ['easy', 'balanced', 'fast']

MIN_CREDITS = 12
MAX_CREDITS = 18
DEFAULT_CREDITS = 15
