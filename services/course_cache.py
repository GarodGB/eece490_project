import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DATA_DIR_NEW = Path(__file__).parent.parent / 'Data'
DATA_DIR_OLD = Path(__file__).parent.parent / 'static' / 'data'

_has_course_index = (
    (DATA_DIR_NEW / 'courses_index.csv').exists()
    or (DATA_DIR_NEW / 'courses_index.json').exists()
)
if _has_course_index:
    DATA_DIR = DATA_DIR_NEW
else:
    DATA_DIR = DATA_DIR_OLD

COURSES_CSV = DATA_DIR / 'courses_index.csv'
COURSES_JSON = DATA_DIR / 'courses_index.json'
PREREQ_CSV = DATA_DIR / 'prerequisites_index.csv'
PREREQ_JSON = DATA_DIR / 'prerequisites_index.json'

_courses_cache = None
_prereq_cache = None

def load_courses_cache():
    
    global _courses_cache
    
    if _courses_cache is not None:
        return _courses_cache
    
    try:
        if COURSES_JSON.exists():
            with open(COURSES_JSON, 'r', encoding='utf-8') as f:
                courses_list = json.load(f)
            _courses_cache = {c['course_code']: c for c in courses_list if 'course_code' in c}
            return _courses_cache
    except Exception as e:
        print(f"[WARNING] Failed to load JSON cache: {e}")
        pass
    
    try:
        if COURSES_CSV.exists():
            df = pd.read_csv(COURSES_CSV)
            _courses_cache = {}
            for _, row in df.iterrows():
                course_code = str(row.get('course_code', '')).strip()
                if course_code:
                    _courses_cache[course_code] = row.to_dict()
            return _courses_cache
    except Exception as e:
        print(f"[WARNING] Failed to load CSV cache: {e}")
        pass
    
    print("[ERROR] No course cache files found!")
    return {}


def load_prerequisites_cache():
    
    global _prereq_cache
    
    if _prereq_cache is not None:
        return _prereq_cache
    
    try:
        if PREREQ_JSON.exists():
            with open(PREREQ_JSON, 'r', encoding='utf-8') as f:
                _prereq_cache = json.load(f)
            return _prereq_cache
    except Exception as e:
        print(f"[WARNING] Failed to load prerequisites JSON: {e}")
        pass
    
    try:
        if PREREQ_CSV.exists():
            df = pd.read_csv(PREREQ_CSV)
            _prereq_cache = {}
            for _, row in df.iterrows():
                course = str(row.get('course', '')).strip()
                prereq = str(row.get('prerequisite', '')).strip()
                if course and prereq:
                    if course not in _prereq_cache:
                        _prereq_cache[course] = []
                    _prereq_cache[course].append(prereq)
            return _prereq_cache
    except Exception as e:
        print(f"[WARNING] Failed to load prerequisites CSV: {e}")
        pass
    
    print("[WARNING] No prerequisites cache found, returning empty dict")
    return {}


def get_course_by_code(course_code: str) -> Optional[Dict]:
    
    courses = load_courses_cache()
    return courses.get(course_code)


def get_course_difficulty(course_code: str) -> Tuple[float, str]:
    
    course = get_course_by_code(course_code)
    if not course:
        return 0.5, 'Medium'
    
    difficulty_score = float(course.get('difficulty_score', 0.5) or 0.5)
    difficulty_category = str(course.get('difficulty_category', 'Medium') or 'Medium')
    
    difficulty_score = max(0.0, min(1.0, difficulty_score))
    if difficulty_category not in ['Easy', 'Medium', 'Hard']:
        if difficulty_score < 0.4:
            difficulty_category = 'Easy'
        elif difficulty_score < 0.7:
            difficulty_category = 'Medium'
        else:
            difficulty_category = 'Hard'
    
    return difficulty_score, difficulty_category


def get_courses_by_subject(subject: str) -> List[Dict]:
    
    courses = load_courses_cache()
    result = []
    for code, c in courses.items():
        course_subject = str(c.get('subject', '')).upper()
        if course_subject == subject.upper():
            result.append({**c, 'course_code': code})
    return result


def get_prerequisites(course_code: str) -> List[str]:
    
    prereqs = load_prerequisites_cache()
    return prereqs.get(course_code, [])


def search_courses(query: str, limit: int = 50) -> List[Dict]:
    
    courses = load_courses_cache()
    query_lower = query.lower()
    
    results = []
    for code, course in courses.items():
        if (query_lower in code.lower() or 
            query_lower in str(course.get('name', '')).lower()):
            results.append({**course, 'course_code': code})
            if len(results) >= limit:
                break
    
    return results


def get_all_courses() -> List[Dict]:
    
    courses = load_courses_cache()
    result = []
    for code, c in courses.items():
        if code:
            result.append({**c, 'course_code': code})
    return result
