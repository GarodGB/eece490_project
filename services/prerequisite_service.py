from database.db import get_db
from database.models import Student, StudentCourse, Course, Prerequisite
from services.course_cache import (
    get_course_by_code,
    get_prerequisites,
    get_courses_by_subject,
    get_all_courses,
    include_in_elective_catalog,
)
from typing import List, Set, Dict, Tuple

STRICT_SUPPORT_SUBJECTS = {'MATH', 'PHYS', 'CHEM', 'STAT', 'ENGL', 'ENG'}
_ENGINEERING_MAJOR_CODES = {'ECE', 'CCE', 'CSE'}
_ENGINEERING_MAJOR_SUBJECTS = {'EECE', 'ECE'}


def _subjects_for_major(major: str) -> Set[str]:
    maj = (major or '').strip().upper()

    if maj in _ENGINEERING_MAJOR_CODES:
        return set(_ENGINEERING_MAJOR_SUBJECTS)

    return {maj} if maj else set()


def _is_major_related_subject(subject: str, major: str) -> bool:
    subj = (subject or '').strip().upper()
    return subj in _subjects_for_major(major)

def _normalize_course_type(raw_course_type: str, subject: str, major: str) -> str:
    raw = str(raw_course_type or '').strip().lower()
    subj = str(subject or '').strip().upper()
    maj = str(major or '').strip().upper()

    # Engineering majors use EECE courses as their major-path courses.
    # Previous versions only compared the subject to ECE/CCE/CSE directly,
    # which caused EECE courses to be misclassified as general electives.
    if _is_major_related_subject(subj, maj):
        return 'major_elective' if raw == 'major_elective' else 'core'

    # Math/science/english style support subjects
    if subj in STRICT_SUPPORT_SUBJECTS:
        return 'support'

    # Everything else is elective
    return 'general_elective'


def get_prerequisite_codes_merged(course_code: str) -> List[str]:
    course_code = (course_code or '').strip().upper()
    if not course_code:
        return []

    seen: Set[str] = set()
    ordered: List[str] = []

    for c in get_prerequisites(course_code):
        c = (c or '').strip().upper()
        if c and c not in seen:
            seen.add(c)
            ordered.append(c)

    db = get_db()
    try:
        row = db.query(Course).filter(Course.course_code == course_code).first()
        if not row:
            return ordered

        q = (
            db.query(Course.course_code)
            .join(Prerequisite, Prerequisite.prerequisite_id == Course.id)
            .filter(Prerequisite.course_id == row.id)
        )

        for (cc,) in q.all():
            cc = (cc or '').strip().upper()
            if cc and cc not in seen:
                seen.add(cc)
                ordered.append(cc)
    finally:
        db.close()

    return ordered


def get_transitive_prerequisite_codes(course_code: str) -> Set[str]:
    course_code = (course_code or '').strip().upper()
    result: Set[str] = set()
    stack: List[str] = list(get_prerequisite_codes_merged(course_code))

    while stack:
        p = (stack.pop() or '').strip().upper()
        if not p or p in result:
            continue
        result.add(p)
        for q in get_prerequisite_codes_merged(p):
            q = (q or '').strip().upper()
            if q and q not in result:
                stack.append(q)

    return result


def get_completed_courses(student_id: int) -> Set[str]:
    # Courses that count as completed for prerequisite unlocking.
    # Failed courses remain visible in student history but should not unlock
    # future courses and should be allowed as retake recommendations.
    db = get_db()
    try:
        rows = (
            db.query(Course.course_code, StudentCourse.grade_points)
            .join(StudentCourse, Course.id == StudentCourse.course_id)
            .filter(StudentCourse.student_id == student_id, StudentCourse.status == 'completed')
            .all()
        )
        passed = set()
        for code, grade_points in rows:
            try:
                gp = float(grade_points or 0.0)
            except Exception:
                gp = 0.0
            if code and gp >= 1.0:
                passed.add((code or '').strip().upper())
        return passed
    finally:
        db.close()


def get_prerequisites_for_course(course_code: str) -> List[str]:
    return get_prerequisite_codes_merged(course_code)


def is_course_unlocked(student_id: int, course_code: str, completed_courses: Set[str] = None) -> Tuple[bool, List[str]]:
    course_code = (course_code or '').strip().upper()
    if not course_code:
        return False, []

    if completed_courses is None:
        completed_courses = get_completed_courses(student_id)
    else:
        completed_courses = {(c or '').strip().upper() for c in completed_courses}

    required = get_transitive_prerequisite_codes(course_code)
    if not required:
        return True, []

    missing = sorted([p for p in required if p not in completed_courses])
    return (len(missing) == 0, missing)


def get_unlocked_courses(
    student_id: int,
    filter_by_major: bool = True,
    limit: int = 150,
    sort_mode: str = 'major_first',
) -> List[Dict]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []

        completed_courses = get_completed_courses(student_id)
        major_u = (student.major or '').upper()

        if filter_by_major and student.major:
            major_courses = []
            for subj in _subjects_for_major(major_u):
                major_courses.extend(get_courses_by_subject(subj))
            allowed_support_subjects = set(STRICT_SUPPORT_SUBJECTS)

            prereq_codes = set()
            for course in major_courses:
                course_code = course.get('course_code', '')
                if course_code:
                    prereq_codes.update(get_prerequisite_codes_merged(course_code))

            prereq_courses = []
            for code in prereq_codes:
                if not code:
                    continue
                course = get_course_by_code(code)
                if not course:
                    continue
                subj = str(course.get('subject', '')).upper()
                if subj in allowed_support_subjects or subj == major_u:
                    prereq_courses.append({**course, 'course_code': code})

            all_courses_dict = {}

            for course in major_courses:
                course_code = course.get('course_code', '')
                if course_code:
                    all_courses_dict[course_code] = course

            for course in prereq_courses:
                course_code = course.get('course_code', '')
                if course_code and course_code not in all_courses_dict:
                    all_courses_dict[course_code] = course

            for course in get_all_courses():
                course_code = course.get('course_code', '')
                if not course_code or course_code in all_courses_dict:
                    continue
                if include_in_elective_catalog(course):
                    all_courses_dict[course_code] = course

            all_courses = list(all_courses_dict.values())
        else:
            all_courses = get_all_courses()

        all_courses.sort(
            key=lambda c: (
                str(c.get('subject', '')).upper() != major_u if major_u else False,
                int(c.get('course_level', 100) or 100),
                str(c.get('course_code', '')),
            )
        )

        unlocked: List[Dict] = []
        seen_codes = set()

        for course_data in all_courses:
            course_code = course_data.get('course_code', '')
            if not course_code or course_code in seen_codes:
                continue
            seen_codes.add(course_code)

            if course_code in completed_courses:
                continue

            try:
                ok, _miss = is_course_unlocked(student_id, course_code, completed_courses)
                if not ok:
                    continue

                normalized_type = _normalize_course_type(
                    course_data.get('course_type', ''),
                    course_data.get('subject', ''),
                    student.major,
                )

                unlocked.append({
                    'course_code': course_code,
                    'name': str(course_data.get('name', '')),
                    'subject': str(course_data.get('subject', '')),
                    'credit_hours': float(course_data.get('credit_hours', 3.0)),
                    'course_level': int(course_data.get('course_level', 100)),
                    'is_lab': bool(course_data.get('is_lab', False)),
                    'prerequisite_count': int(course_data.get('prerequisite_count', 0)),
                    'course_type': normalized_type,
                    'is_major_course': normalized_type in ('core', 'major_elective'),
                })
            except Exception as e:
                print(f"[WARNING] Error processing course {course_code}: {e}")
                continue

        if sort_mode == 'balanced' and major_u:
            def _balanced_key(u: Dict) -> Tuple[int, int, str]:
                s = str(u.get('subject', '')).upper()
                if s == major_u:
                    tier = 0
                elif s in STRICT_SUPPORT_SUBJECTS:
                    tier = 1
                else:
                    tier = 2
                return (u['course_level'] // 100, tier, u['course_code'])

            unlocked.sort(key=_balanced_key)
        else:
            unlocked.sort(key=lambda u: (
                str(u.get('subject', '')).upper() != major_u if major_u else False,
                u['course_level'],
                u['course_code'],
            ))

        if limit:
            unlocked = unlocked[:limit]

        return unlocked
    finally:
        db.close()


def get_locked_courses(student_id: int) -> List[Dict]:
    all_courses = get_all_courses()
    locked = []

    for course_data in all_courses:
        course_code = course_data.get('course_code', '')
        if not course_code:
            continue

        is_unlocked, missing = is_course_unlocked(student_id, course_code)
        if not is_unlocked:
            locked.append({
                'course_code': course_code,
                'name': course_data.get('name', ''),
                'credit_hours': float(course_data.get('credit_hours', 3.0)),
                'course_level': int(course_data.get('course_level', 100)),
                'missing_prerequisites': missing
            })

    return locked
