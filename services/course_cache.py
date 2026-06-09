import logging
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

GEN_ED_ELECTIVE_SUBJECTS = frozenset({
    'ECON', 'PSYC', 'BUS', 'SOC', 'POL', 'PHIL', 'HIST', 'BIO',
    'ART', 'LAW', 'MED', 'MUS',
    'ANTH', 'COMM', 'GEOG', 'REL', 'SPAN', 'CHIN', 'CINE', 'DANC', 'NUTR', 'EDUC', 'LING',
    'FREN', 'GER', 'ITAL', 'JAP', 'KORE', 'ARAB', 'PORT', 'RUSS', 'HEBR', 'LATN', 'GREK', 'SWAH',
    'THEA', 'WGSS', 'JOUR', 'RTVF', 'CLAS', 'URST', 'CRIM', 'SWRK', 'DESN', 'ARCH', 'GAME', 'DATA',
    'HLTH', 'PHED', 'RECR', 'EVSC', 'SUST', 'ENVS', 'FORS', 'INTD', 'NURS',
})

MAJOR_BROWSE_EXTRA_SUBJECTS = {
    'ENGR': frozenset({'ECE', 'CS', 'CSE'}),
}

STRICT_SUPPORT_SUBJECTS = frozenset({'MATH', 'PHYS', 'CHEM', 'STAT', 'ENGL', 'ENG'})

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_CSV = DATA_DIR / 'merged_courses.csv'
COURSES_JSON_FALLBACK = DATA_DIR / 'courses_index.json'
PREREQ_CSV = DATA_DIR / 'prerequisites_index.csv'
PREREQ_JSON = DATA_DIR / 'prerequisites_index.json'

_courses_cache = None
_prereq_cache = None


def _to_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() == 'true'
    return bool(value)


def include_in_elective_catalog(course: Dict) -> bool:
    subj = str(course.get('subject', '')).upper()
    return subj in GEN_ED_ELECTIVE_SUBJECTS


def catalog_tag(subject: str, major: Optional[str]) -> str:
    s = (subject or '').upper()
    m = (major or '').upper()

    if m and s == m:
        return 'major'
    if s in STRICT_SUPPORT_SUBJECTS:
        return 'support'
    if s in GEN_ED_ELECTIVE_SUBJECTS:
        return 'elective'
    return 'support'


def get_browse_catalog(major: Optional[str]) -> List[Dict]:
    courses = load_courses_cache()
    if not major:
        return get_all_courses()

    major_u = major.upper()
    extra_major_subjects = MAJOR_BROWSE_EXTRA_SUBJECTS.get(major_u, frozenset())

    def is_major_row(subj: str) -> bool:
        return subj == major_u or subj in extra_major_subjects

    out: List[Dict] = []
    seen = set()

    for code, c in courses.items():
        row = {**c, 'course_code': code}
        subj = str(c.get('subject', '')).upper()
        if is_major_row(subj):
            out.append(row)
            seen.add(code)

    for code, c in courses.items():
        if code in seen:
            continue
        row = {**c, 'course_code': code}
        if include_in_elective_catalog(row):
            out.append(row)

    out.sort(key=lambda r: (
        str(r.get('subject', '')).upper() not in (major_u, *extra_major_subjects),
        int(r.get('course_level', 100) or 100),
        str(r.get('course_code', '')),
    ))
    return out


def load_courses_cache():
    global _courses_cache

    if _courses_cache is not None:
        return _courses_cache

    try:
        if COURSES_CSV.exists():
            df = pd.read_csv(COURSES_CSV)
            _courses_cache = {}

            for _, row in df.iterrows():
                course_code = str(row.get('course_code', '')).strip().upper()
                if not course_code:
                    continue

                row_dict = row.to_dict()
                row_dict['course_code'] = course_code
                row_dict['subject'] = str(row_dict.get('subject', '') or '').strip().upper()
                row_dict['name'] = str(row_dict.get('name', '') or '')
                row_dict['description'] = str(row_dict.get('description', '') or '')
                row_dict['credit_hours'] = float(row_dict.get('credit_hours', 3.0) or 3.0)
                row_dict['course_level'] = int(row_dict.get('course_level', 100) or 100)
                row_dict['prerequisite_count'] = int(row_dict.get('prerequisite_count', 0) or 0)
                row_dict['prerequisite_depth'] = int(row_dict.get('prerequisite_depth', 0) or 0)
                row_dict['graph_centrality'] = float(row_dict.get('graph_centrality', 0.0) or 0.0)
                row_dict['unlocks_count'] = int(row_dict.get('unlocks_count', 0) or 0)
                row_dict['is_lab'] = _to_bool(row_dict.get('is_lab', False))
                row_dict['is_major_course'] = _to_bool(row_dict.get('is_major_course', False))
                row_dict['course_type'] = str(row_dict.get('course_type', '') or '').strip().lower()
                row_dict['difficulty_score'] = float(row_dict.get('difficulty_score', 0.5) or 0.5)
                row_dict['difficulty_category'] = str(row_dict.get('difficulty_category', 'Medium') or 'Medium')

                _courses_cache[course_code] = row_dict

            return _courses_cache
    except Exception as e:
        logger.warning("Failed to load merged_courses CSV: %s", e)

    try:
        if COURSES_JSON_FALLBACK.exists():
            with open(COURSES_JSON_FALLBACK, 'r', encoding='utf-8') as f:
                courses_list = json.load(f)

            _courses_cache = {}
            for c in courses_list:
                code = str(c.get('course_code', '')).strip().upper()
                if not code:
                    continue

                c['course_code'] = code
                c['subject'] = str(c.get('subject', '') or '').strip().upper()
                c['course_type'] = str(c.get('course_type', '') or '').strip().lower()
                c['is_lab'] = _to_bool(c.get('is_lab', False))
                c['is_major_course'] = _to_bool(c.get('is_major_course', False))
                _courses_cache[code] = c

            return _courses_cache
    except Exception as e:
        logger.warning("Failed to load JSON fallback: %s", e)

    logger.error("No course cache files found")
    _courses_cache = {}
    return _courses_cache


def load_prerequisites_cache():
    global _prereq_cache

    if _prereq_cache is not None:
        return _prereq_cache

    try:
        if PREREQ_JSON.exists():
            with open(PREREQ_JSON, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            _prereq_cache = {
                str(k).strip().upper(): [str(x).strip().upper() for x in v]
                for k, v in raw.items()
            }
            return _prereq_cache
    except Exception as e:
        logger.warning("Failed to load prerequisites JSON: %s", e)

    try:
        if PREREQ_CSV.exists():
            df = pd.read_csv(PREREQ_CSV)
            _prereq_cache = {}
            for _, row in df.iterrows():
                course = str(row.get('course', '')).strip().upper()
                prereq = str(row.get('prerequisite', '')).strip().upper()
                if course and prereq:
                    if course not in _prereq_cache:
                        _prereq_cache[course] = []
                    _prereq_cache[course].append(prereq)
            return _prereq_cache
    except Exception as e:
        logger.warning("Failed to load prerequisites CSV: %s", e)

    logger.warning("No prerequisites cache found, returning empty dict")
    _prereq_cache = {}
    return _prereq_cache


def get_course_by_code(course_code: str) -> Optional[Dict]:
    courses = load_courses_cache()
    return courses.get(str(course_code or '').strip().upper())



def _heuristic_difficulty_from_course(course: Dict) -> Tuple[float, str]:
    """
    Deterministic course-profile fallback used when the catalog CSV has no trained
    difficulty column. This prevents the UI from showing every available course
    as the same 50-60% difficulty. It uses pre-course information only: level,
    credits, lab/project/title keywords, prerequisites, and subject area.
    """
    subj = str(course.get('subject', '') or '').upper()
    name = str(course.get('name', '') or '').lower()
    desc = str(course.get('description', '') or '').lower()
    text = f"{name} {desc}"
    level = int(course.get('course_level', 100) or 100)
    credits = float(course.get('credit_hours', 3.0) or 3.0)
    prereq_count = int(course.get('prerequisite_count', 0) or 0)
    prereq_depth = int(course.get('prerequisite_depth', 0) or 0)
    unlocks = int(course.get('unlocks_count', 0) or 0)
    is_lab = _to_bool(course.get('is_lab', False))

    # Base by level. 200-level support courses should not all collapse to 0.60.
    score = 0.18 + max(0, min(level, 500) - 100) / 400.0 * 0.42

    # Subject pressure. Major/STEM theory courses are usually more demanding than
    # general education at the same level.
    if subj in {'EECE', 'ECE', 'CSE', 'CS', 'CMPS'}:
        score += 0.10
    elif subj in {'MATH', 'STAT', 'PHYS'}:
        score += 0.08
    elif subj in {'CHEM', 'BIOL'}:
        score += 0.05
    elif subj in GEN_ED_ELECTIVE_SUBJECTS:
        score -= 0.06

    if credits >= 4:
        score += 0.06
    elif credits <= 1.5:
        score -= 0.06
    if is_lab or 'lab' in text or 'laboratory' in text:
        score += 0.08
    if any(k in text for k in ['project', 'design', 'capstone', 'senior']):
        score += 0.10
    if any(k in text for k in ['circuit', 'electronics', 'signals', 'systems', 'control', 'communication', 'algorithm', 'data structures', 'probability', 'differential']):
        score += 0.07
    if any(k in text for k in ['introductory', 'elementary', 'communication', 'english', 'economics', 'arabic']):
        score -= 0.04

    score += min(0.12, 0.025 * prereq_count + 0.025 * prereq_depth)
    score += min(0.06, 0.012 * unlocks)
    score = max(0.12, min(0.92, score))

    if score < 0.38:
        cat = 'Easy'
    elif score < 0.68:
        cat = 'Medium'
    else:
        cat = 'Hard'
    return score, cat


def get_course_difficulty(course_code: str) -> Tuple[float, str]:
    course = get_course_by_code(course_code)
    if not course:
        return 0.5, 'Medium'

    raw_score = course.get('difficulty_score', None)
    raw_cat = course.get('difficulty_category', None)

    # If the CSV does not contain a real difficulty column, loaded rows default to
    # 0.5/Medium. Use a course-profile heuristic instead so available courses are
    # differentiated in the UI.
    try:
        difficulty_score = float(raw_score)
    except Exception:
        difficulty_score = 0.5
    difficulty_category = str(raw_cat or 'Medium')

    if abs(difficulty_score - 0.5) < 1e-9 and difficulty_category == 'Medium':
        difficulty_score, difficulty_category = _heuristic_difficulty_from_course(course)
    else:
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
    subj_u = str(subject or '').upper()
    return [{**c, 'course_code': code} for code, c in courses.items() if str(c.get('subject', '')).upper() == subj_u]


def get_prerequisites(course_code: str) -> List[str]:
    prereqs = load_prerequisites_cache()
    key = str(course_code or '').strip().upper()
    if not key:
        return []
    if key in prereqs:
        return prereqs[key]
    for k, v in prereqs.items():
        if str(k).strip().upper() == key:
            return v
    return []


def search_courses(query: str, limit: int = 50) -> List[Dict]:
    courses = load_courses_cache()
    query_lower = query.lower()
    results = []

    for code, course in courses.items():
        if query_lower in code.lower() or query_lower in str(course.get('name', '')).lower():
            results.append({**course, 'course_code': code})
            if len(results) >= limit:
                break

    return results


def get_all_courses() -> List[Dict]:
    courses = load_courses_cache()
    return [{**c, 'course_code': code} for code, c in courses.items() if code]
