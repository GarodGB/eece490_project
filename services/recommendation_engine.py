
from typing import List, Dict
from database.db import get_db
from database.models import Course, Student
from services.prerequisite_service import get_unlocked_courses
from services.ml_service import predict_course_difficulty, predict_semester_workload
from services.course_cache import get_course_by_code, get_course_difficulty

def recommend_courses(student_id: int, target_credits: int = 15, max_courses: int = 6, term: str = None) -> List[Dict]:
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return []
        
        from database.models import StudentCourse
        from services.course_cache import get_course_by_code
        completed_rows = db.query(Course.course_code).join(
            StudentCourse, Course.id == StudentCourse.course_id
        ).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).all()
        completed_course_codes = {row[0] for row in completed_rows if row[0]}
        
        unlocked = get_unlocked_courses(student_id, filter_by_major=True)
        
        valid_courses = []
        for c in unlocked[:100]:
            course_code = c.get('course_code', '')
            credit_hours = float(c.get('credit_hours', 0) or 0)
            
            if not course_code or course_code in completed_course_codes:
                continue
            if credit_hours <= 0:
                continue
            
            valid_courses.append(c)
        
        if not valid_courses:
            return []
        
        major_courses = [c for c in valid_courses if c.get('is_major_course', True)]
        other_courses = [c for c in valid_courses if not c.get('is_major_course', True)]
        
        scored_courses = []
        courses_to_process = (major_courses[:50] + other_courses[:30])[:max_courses * 3]
        for course_data in courses_to_process:
            course_code = course_data.get('course_code', '')
            if not course_code:
                continue
            
            cache_course = get_course_by_code(course_code)
            if not cache_course:
                continue
            
            difficulty_score, category = get_course_difficulty(course_code)
            
            original_category = category
            
            if student.gpa < 2.5:
                if category != 'Hard':
                    difficulty_score = min(1.0, difficulty_score + 0.10)
            elif student.gpa > 3.5:
                if category != 'Hard':
                    difficulty_score = max(0.0, difficulty_score - 0.08)
            
            difficulty_score = min(1.0, max(0.0, difficulty_score))
            
            if original_category == 'Hard':
                category = 'Hard'
            elif difficulty_score < 0.4:
                category = 'Easy'
            elif difficulty_score < 0.7:
                category = 'Medium'
            else:
                category = 'Hard'
            
            base_score = 1.0 - difficulty_score
            major_bonus = 0.3 if course_data.get('is_major_course', True) else 0.0
            unlocks_count = int(cache_course.get('unlocks_count', 0) or 0)
            
            if student.strategy == 'easy':
                score = base_score * 1.5 + major_bonus
            elif student.strategy == 'fast':
                unlocks_bonus = min(unlocks_count / 10.0, 0.5)
                score = base_score + unlocks_bonus + major_bonus
            else:
                score = base_score + major_bonus
            
            
            scored_courses.append({
                **course_data,
                'id': 0,
                'difficulty_score': difficulty_score,
                'difficulty_category': category,
                'recommendation_score': score,
                'term': term
            })
        
        scored_courses.sort(key=lambda x: x['recommendation_score'], reverse=True)

        selected: List[Dict] = []
        selected_codes = set()
        total_credits = 0.0

        def try_add(course: Dict) -> bool:
            nonlocal total_credits
            code = course.get('course_code', '')
            if not code or code in selected_codes:
                return False
            credit_hours = float(course.get('credit_hours', 0) or 0)
            if credit_hours <= 0:
                return False
            if total_credits + credit_hours > target_credits + 3:
                return False
            selected.append(course)
            selected_codes.add(code)
            total_credits += credit_hours
            return True

        buckets = {'Easy': [], 'Medium': [], 'Hard': []}
        for c in scored_courses:
            buckets.get(c.get('difficulty_category', 'Medium'), buckets['Medium']).append(c)

        non_empty = [k for k in ['Easy', 'Medium', 'Hard'] if buckets[k]]

        if max_courses >= len(non_empty) and non_empty:
            for cat in non_empty:
                for c in buckets[cat]:
                    if try_add(c):
                        break

        while len(selected) < max_courses and any(buckets[k] for k in ['Easy', 'Medium', 'Hard']):
            made_progress = False
            for cat in ['Easy', 'Medium', 'Hard']:
                if len(selected) >= max_courses:
                    break
                for c in buckets[cat]:
                    if try_add(c):
                        made_progress = True
                        break
            if not made_progress:
                break

        if len(selected) < max_courses:
            top_candidates = scored_courses[:max_courses * 4]
            for c in top_candidates:
                if len(selected) >= max_courses:
                    break
                try_add(c)

        return selected
    finally:
        db.close()


def optimize_semester_plan(student_id: int, course_ids: List[int]) -> Dict:
    
    workload = predict_semester_workload(student_id, course_ids)
    
    if not workload:
        return None
    
    difficulty = workload['semester_difficulty']
    if difficulty < 0.33:
        difficulty_category = 'Easy'
    elif difficulty < 0.67:
        difficulty_category = 'Moderate'
    else:
        difficulty_category = 'Challenging'
    
    risk = workload['overload_risk']
    if risk < 0.3:
        risk_category = 'Low'
    elif risk < 0.6:
        risk_category = 'Medium'
    else:
        risk_category = 'High'
    
    return {
        **workload,
        'difficulty_category': difficulty_category,
        'risk_category': risk_category
    }
