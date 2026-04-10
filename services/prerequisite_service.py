
from database.db import get_db
from database.models import Student, StudentCourse, Course
from services.course_cache import get_course_by_code, get_prerequisites, get_courses_by_subject, get_all_courses
from typing import List, Set, Dict, Tuple

def get_completed_courses(student_id: int) -> Set[str]:
    
    db = get_db()
    try:
        rows = (
            db.query(Course.course_code)
            .join(StudentCourse, Course.id == StudentCourse.course_id)
            .filter(StudentCourse.student_id == student_id, StudentCourse.status == 'completed')
            .all()
        )
        return {r[0] for r in rows if r and r[0]}
    finally:
        db.close()


def get_prerequisites_for_course(course_code: str) -> List[str]:
    
    return get_prerequisites(course_code)


def is_course_unlocked(student_id: int, course_code: str, completed_courses: Set[str] = None) -> Tuple[bool, List[str]]:
    
    if completed_courses is None:
        completed_courses = get_completed_courses(student_id)
    
    prereq_codes = get_prerequisites(course_code)
    if not prereq_codes:
        return True, []
    
    missing = [p for p in prereq_codes if p not in completed_courses]
    is_unlocked = len(missing) == 0
    
    return is_unlocked, missing


def get_unlocked_courses(student_id: int, filter_by_major: bool = True, limit: int = 150) -> List[Dict]:
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []
        
        completed_courses = get_completed_courses(student_id)
        
        if filter_by_major and student.major:
            major_subject = student.major.upper()
            major_courses = get_courses_by_subject(major_subject)
            
            allowed_prereq_subjects = ['MATH', 'PHYS', 'CHEM', 'ENG', 'ENGL', 'CS', 'ECE', 'CSE', 'STAT']
            if major_subject not in allowed_prereq_subjects:
                allowed_prereq_subjects.append(major_subject)
            
            prereq_codes = set()
            for course in major_courses:
                course_code = course.get('course_code', '')
                if course_code:
                    prereqs = get_prerequisites(course_code)
                    prereq_codes.update(prereqs)
            
            prereq_courses = []
            for code in prereq_codes:
                if code:
                    course = get_course_by_code(code)
                    if course:
                        course_subject = str(course.get('subject', '')).upper()
                        if course_subject in allowed_prereq_subjects:
                            prereq_courses.append({**course, 'course_code': code, 'is_major_course': False})
            
            for course in major_courses:
                course['is_major_course'] = True
            
            all_courses_dict = {}
            for course in major_courses:
                course_code = course.get('course_code', '')
                if course_code:
                    all_courses_dict[course_code] = course
            
            for course in prereq_courses:
                course_code = course.get('course_code', '')
                if course_code and course_code not in all_courses_dict:
                    all_courses_dict[course_code] = course
            
            all_courses = list(all_courses_dict.values())
        else:
            all_courses = get_all_courses()
        
        all_courses.sort(
            key=lambda c: (
                str(c.get('subject', '')).upper() != (student.major.upper() if student.major else ''),
                int(c.get('course_level', 100) or 100),
                str(c.get('course_code', '')),
            )
        )

        unlocked: List[Dict] = []
        seen_codes = set()
        for course_data in all_courses:
            course_code = course_data.get('course_code', '')
            if not course_code:
                continue
            
            if course_code in seen_codes:
                continue
            seen_codes.add(course_code)
            
            if course_code in completed_courses:
                continue
            
            try:
                prereq_codes = get_prerequisites(course_code)
                if prereq_codes and any(p not in completed_courses for p in prereq_codes):
                    continue

                unlocked.append({
                    'course_code': course_code,
                    'name': str(course_data.get('name', '')),
                    'subject': str(course_data.get('subject', '')),
                    'credit_hours': float(course_data.get('credit_hours', 3.0)),
                    'course_level': int(course_data.get('course_level', 100)),
                    'is_lab': bool(course_data.get('is_lab', False)),
                    'prerequisite_count': int(course_data.get('prerequisite_count', 0)),
                    'is_major_course': str(course_data.get('subject', '')).upper() == student.major.upper() if student.major else True
                })
                if limit and len(unlocked) >= limit:
                    break
            except Exception as e:
                print(f"[WARNING] Error processing course {course_code}: {e}")
                continue
        
        return unlocked
    finally:
        db.close()


def get_locked_courses(student_id: int) -> List[Dict]:
    
    completed_courses = get_completed_courses(student_id)
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
