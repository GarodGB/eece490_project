import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict
from database.db import get_db
from database.models import Course, Student, StudentCourse
from config import ML_MODELS_DIR, GRADE_POINTS

MODEL1_FILE = ML_MODELS_DIR / 'model1_xgboost.pkl'
MODEL2_FILE = ML_MODELS_DIR / 'model2_gradient_boosting.pkl'
MODEL3_FILE = ML_MODELS_DIR / 'model3_xgboost_risk.pkl'

MODEL1_INFO_FILE = ML_MODELS_DIR / 'model1_info.pkl'
MODEL2_INFO_FILE = ML_MODELS_DIR / 'model2_info.pkl'
MODEL3_INFO_FILE = ML_MODELS_DIR / 'model3_info.pkl'
MODEL2_SCALER_FILE = ML_MODELS_DIR / 'model2_scaler.pkl'

_model1 = None
_model2 = None
_model3 = None
_model1_info = None
_model2_info = None
_model3_info = None
_model2_scaler = None

def load_models():
    
    global _model1, _model2, _model3
    global _model1_info, _model2_info, _model3_info, _model2_scaler
    
    try:
        if _model1 is None and MODEL1_FILE.exists():
            with open(MODEL1_FILE, 'rb') as f:
                _model1 = pickle.load(f)
        elif _model1 is None:
            print(f"[WARNING] Model file not found: {MODEL1_FILE}")
            _model1 = None
    
        if _model2 is None and MODEL2_FILE.exists():
            with open(MODEL2_FILE, 'rb') as f:
                _model2 = pickle.load(f)
        elif _model2 is None:
            print(f"[WARNING] Model file not found: {MODEL2_FILE}")
            _model2 = None
        
        if _model3 is None and MODEL3_FILE.exists():
            with open(MODEL3_FILE, 'rb') as f:
                _model3 = pickle.load(f)

        if _model1_info is None and MODEL1_INFO_FILE.exists():
            with open(MODEL1_INFO_FILE, 'rb') as f:
                _model1_info = pickle.load(f)
        elif _model1_info is None:
            _model1_info = {}
    
        if _model2_info is None and MODEL2_INFO_FILE.exists():
            with open(MODEL2_INFO_FILE, 'rb') as f:
                _model2_info = pickle.load(f)
        elif _model2_info is None:
            _model2_info = {}
        
        if _model3_info is None and MODEL3_INFO_FILE.exists():
            with open(MODEL3_INFO_FILE, 'rb') as f:
                _model3_info = pickle.load(f)

        if _model2_scaler is None and _model2_info.get('uses_scaler', False) and MODEL2_SCALER_FILE.exists():
            with open(MODEL2_SCALER_FILE, 'rb') as f:
                _model2_scaler = pickle.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to load ML models: {e}")
        _model1 = None
        _model2 = None
        _model3 = None


def predict_course_difficulty(student_id: int, course_id: int) -> dict:
    
    load_models()
    
    if _model1 is None:
        return {
            'difficulty_score': 0.5,
            'difficulty_category': 'Medium',
            'confidence': 0.0
        }
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        
        if not student or not course:
            return None
        
        prereq_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).all()
        
        prereq_grades = [sc.grade_points for sc in prereq_courses if sc.grade_points]
        avg_prereq_grade = np.mean(prereq_grades) if prereq_grades else 3.0
        min_prereq_grade = np.min(prereq_grades) if prereq_grades else 3.0
        
        features = np.array([[
            course.course_level / 500.0,
            course.prerequisite_count / 10.0,
            course.prerequisite_depth / 10.0,
            course.graph_centrality,
            course.credit_hours / 4.0,
            1 if course.is_lab else 0,
            student.gpa / 4.0,
            student.workload_tolerance,
            student.workload_tolerance,
            len(prereq_courses) / 50.0,
            avg_prereq_grade / 4.0,
            min_prereq_grade / 4.0,
            len(prereq_grades) / 10.0
        ]])
        
        difficulty_score = _model1.predict(features)[0]
        difficulty_score = max(0.0, min(1.0, difficulty_score))
        
        course_subject = course.subject.upper() if course.subject else ''
        
        hard_subjects = ['MATH', 'PHYS', 'CHEM', 'ENGR', 'CS', 'ECE', 'CSE']
        if course_subject in hard_subjects:
            difficulty_score = min(1.0, difficulty_score + 0.20)
        
        if course.course_level >= 400:
            difficulty_score = min(1.0, difficulty_score + 0.45)
        elif course.course_level >= 300:
            difficulty_score = min(1.0, difficulty_score + 0.35)
        elif course.course_level >= 200:
            difficulty_score = min(1.0, difficulty_score + 0.20)
        
        if course.is_lab:
            difficulty_score = min(1.0, difficulty_score + 0.15)
        
        if course.prerequisite_count >= 4:
            difficulty_score = min(1.0, difficulty_score + 0.25)
        elif course.prerequisite_count >= 3:
            difficulty_score = min(1.0, difficulty_score + 0.18)
        elif course.prerequisite_count >= 2:
            difficulty_score = min(1.0, difficulty_score + 0.10)
        elif course.prerequisite_count >= 1:
            difficulty_score = min(1.0, difficulty_score + 0.05)
        
        if student.gpa < 2.5:
            difficulty_score = min(1.0, difficulty_score + 0.10)
        elif student.gpa > 3.5:
            difficulty_score = max(0.0, difficulty_score - 0.08)
        
        if course_subject in ['MATH', 'PHYS']:
            if course.course_level >= 300:
                difficulty_score = max(0.75, difficulty_score)
            elif course.course_level >= 200:
                difficulty_score = max(0.50, difficulty_score)
        
        if course_subject in ['ECE', 'CSE', 'CS', 'ENGR']:
            if course.course_level >= 400:
                difficulty_score = max(0.80, difficulty_score)
            elif course.course_level >= 300:
                difficulty_score = max(0.72, difficulty_score)
        
        if difficulty_score < 0.4:
            category = 'Easy'
        elif difficulty_score < 0.7:
            category = 'Medium'
        else:
            category = 'Hard'
        
        return {
            'difficulty_score': float(difficulty_score),
            'difficulty_category': category,
            'confidence': 0.85
        }
    finally:
        db.close()


def predict_semester_workload(student_id: int, course_ids: List[int]) -> dict:
    
    load_models()
    
    if _model2 is None:
        total_credits = 0
        num_labs = 0
        for cid in course_ids:
            course = db.query(Course).filter(Course.id == cid).first()
            if course:
                total_credits += course.credit_hours or 0
                if course.is_lab:
                    num_labs += 1
        
        if total_credits < 12:
            overload_risk = 0.2
        elif total_credits <= 18:
            overload_risk = 0.3
        elif total_credits <= 24:
            overload_risk = 0.5
        else:
            overload_risk = min(1.0, 0.7 + (total_credits - 24) / 20.0)
        
        return {
            'semester_difficulty': 0.5,
            'overload_risk': float(overload_risk),
            'total_credits': total_credits,
            'num_courses': len(course_ids),
            'num_labs': num_labs
        }
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None
        
        course_difficulties = []
        total_credits = 0
        num_labs = 0
        
        for course_id in course_ids:
            course = db.query(Course).filter(Course.id == course_id).first()
            if not course:
                continue
            
            difficulty = predict_course_difficulty(student_id, course_id)
            if difficulty:
                course_difficulties.append(difficulty['difficulty_score'])
            
            total_credits += course.credit_hours
            if course.is_lab:
                num_labs += 1
        
        if not course_difficulties:
            if total_credits < 12:
                overload_risk = 0.2
            elif total_credits <= 18:
                overload_risk = 0.3
            elif total_credits <= 24:
                overload_risk = 0.5
            else:
                overload_risk = min(1.0, 0.7 + (total_credits - 24) / 20.0)
            
            return {
                'semester_difficulty': 0.5,
                'overload_risk': float(overload_risk),
                'total_credits': total_credits,
                'num_courses': len(course_ids),
                'num_labs': num_labs
            }
        
        avg_difficulty = np.mean(course_difficulties)
        max_difficulty = np.max(course_difficulties)
        difficulty_variance = np.var(course_difficulties) if len(course_difficulties) > 1 else 0.0
        
        features = np.array([[
            avg_difficulty,
            max_difficulty,
            difficulty_variance,
            total_credits / 18.0,
            len(course_ids) / 6.0,
            num_labs / 3.0,
            student.gpa / 4.0,
            student.workload_tolerance,
            student.workload_tolerance,
            len(course_ids) / 50.0
        ]])
        
        if _model2_scaler:
            features = _model2_scaler.transform(features)
        
        semester_difficulty = _model2.predict(features)[0]
        semester_difficulty = max(0.0, min(1.0, semester_difficulty))
        
        base_risk = 0.0
        
        if total_credits < 12:
            base_risk = 0.2
        elif total_credits <= 18:
            base_risk = 0.3 + (avg_difficulty * 0.2)
        elif total_credits <= 24:
            base_risk = 0.5 + (avg_difficulty * 0.3)
        else:
            base_risk = min(1.0, 0.7 + (avg_difficulty * 0.3))
        
        workload_adjustment = (1.0 - student.workload_tolerance) * 0.2
        overload_risk = base_risk + workload_adjustment
        
        if len(course_ids) > 6:
            overload_risk = min(1.0, overload_risk + 0.15)
        elif len(course_ids) > 5:
            overload_risk = min(1.0, overload_risk + 0.1)
        
        if num_labs >= 2:
            overload_risk = min(1.0, overload_risk + 0.10)
        elif num_labs >= 1:
            overload_risk = min(1.0, overload_risk + 0.05)
        
        overload_risk = min(1.0, max(0.0, overload_risk))
        
        return {
            'semester_difficulty': float(semester_difficulty),
            'overload_risk': float(overload_risk),
            'total_credits': float(total_credits),
            'num_courses': len(course_ids),
            'num_labs': num_labs
        }
    finally:
        db.close()


def predict_academic_risk(student_id: int) -> dict:
    load_models()
    
    if _model3 is None:
        return {
            'risk_score': 0.3,
            'risk_category': 'Medium',
            'risk_factors': [],
            'recommendations': []
        }
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None
        
        completed_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).order_by(StudentCourse.semester_taken.desc()).limit(10).all()
        
        if len(completed_courses) < 3:
            return {
                'risk_score': 0.2,
                'risk_category': 'Low',
                'risk_factors': [],
                'recommendations': []
            }
        
        recent_grades = [sc.grade_points for sc in completed_courses if sc.grade_points]
        avg_recent_grade = np.mean(recent_grades) if recent_grades else 3.0
        min_recent_grade = np.min(recent_grades) if recent_grades else 3.0
        
        failed_count = len([g for g in recent_grades if g < 1.0])
        low_grade_count = len([g for g in recent_grades if g < 2.0])
        
        gpa_trend = []
        for i in range(3, len(completed_courses)):
            window = completed_courses[max(0, i-3):i+1]
            window_gpa = np.mean([sc.grade_points for sc in window if sc.grade_points])
            gpa_trend.append(window_gpa)
        
        gpa_trend_slope = np.polyfit(range(len(gpa_trend)), gpa_trend, 1)[0] if len(gpa_trend) > 1 else 0.0
        
        course_difficulties = []
        for sc in completed_courses:
            if sc.course:
                diff = predict_course_difficulty(student_id, sc.course.id)
                if diff:
                    course_difficulties.append(diff['difficulty_score'])
        
        avg_difficulty = np.mean(course_difficulties) if course_difficulties else 0.5
        difficulty_variance = np.var(course_difficulties) if len(course_difficulties) > 1 else 0.0
        
        features = np.array([[
            student.gpa / 4.0,
            gpa_trend_slope,
            np.mean([sc.grade_points for sc in completed_courses if sc.grade_points]) / 4.0,
            avg_recent_grade / 4.0,
            min_recent_grade / 4.0,
            failed_count / 10.0,
            low_grade_count / 10.0,
            avg_difficulty,
            difficulty_variance,
            (avg_recent_grade / 4.0) - avg_difficulty,
            student.workload_tolerance,
            student.workload_tolerance,
            len(completed_courses) / 50.0
        ]])
        
        risk_level = _model3.predict(features)[0]
        risk_proba = _model3.predict_proba(features)[0]

        risk_levels = (_model3_info or {}).get('risk_levels', {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Critical'})
        risk_category = risk_levels.get(int(risk_level), 'Medium')
        risk_score = float(risk_proba[int(risk_level)])
        
        risk_factors = []
        if student.gpa < 2.5:
            risk_factors.append('Low GPA')
        if failed_count > 0:
            risk_factors.append(f'{failed_count} failed course(s)')
        if gpa_trend_slope < -0.1:
            risk_factors.append('Declining GPA trend')
        
        recommendations = []
        if risk_category in ['High', 'Critical']:
            recommendations.append('Consider reducing course load')
            recommendations.append('Meet with academic advisor')
            if failed_count > 0:
                recommendations.append('Retake failed courses')
        
        return {
            'risk_score': risk_score,
            'risk_category': risk_category,
            'risk_factors': risk_factors,
            'recommendations': recommendations
        }
    finally:
        db.close()
