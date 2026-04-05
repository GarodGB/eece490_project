
import pandas as pd
import numpy as np
from pathlib import Path
import random

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
PREREQUISITES_FILE = DATA_DIR / 'prerequisites.csv'
OUTPUT_DIR = DATA_DIR / 'synthetic'
OUTPUT_DIR.mkdir(exist_ok=True)

GRADE_DISTRIBUTION = {
    'A': 0.25, 'A-': 0.10, 'B+': 0.12, 'B': 0.15, 'B-': 0.08,
    'C+': 0.08, 'C': 0.10, 'C-': 0.04, 'D+': 0.03, 'D': 0.03, 'F': 0.02
}

GRADE_POINTS = {
    'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D+': 1.3, 'D': 1.0, 'F': 0.0
}


def load_courses_and_prerequisites():
    
    print("Loading courses and prerequisites...")
    courses_df = pd.read_csv(COURSES_FILE)
    prerequisites_df = pd.read_csv(PREREQUISITES_FILE)
    
    prereq_dict = {}
    for _, row in prerequisites_df.iterrows():
        course = row['course']
        prereq = row['prerequisite']
        if course not in prereq_dict:
            prereq_dict[course] = []
        prereq_dict[course].append(prereq)
    
    return courses_df, prereq_dict


def generate_student_profile(student_id, courses_df, prereq_dict):
    
    academic_ability = np.random.beta(2, 2)
    
    workload_tolerance = np.random.beta(2, 2)
    
    strategy = np.random.choice(['easy', 'balanced', 'fast'], p=[0.3, 0.5, 0.2])
    
    current_semester = np.random.randint(1, 9)
    
    completed_courses = []
    completed_course_codes = set()
    
    courses_sorted = courses_df.sort_values(['course_level', 'prerequisite_depth', 'prerequisite_count'])
    
    courses_per_semester = np.random.poisson(4) + 2
    total_courses_taken = min(current_semester * courses_per_semester, len(courses_sorted))
    
    semester = 1
    courses_this_semester = 0
    target_courses_per_sem = np.random.randint(3, 6)
    
    for idx, course_row in courses_sorted.iterrows():
        if len(completed_course_codes) >= total_courses_taken:
            break
        
        course_code = course_row['course_code']
        
        if course_code in completed_course_codes:
            continue
        
        has_prereqs = course_code in prereq_dict
        if has_prereqs:
            prereqs = prereq_dict[course_code]
            if not all(p in completed_course_codes for p in prereqs):
                continue
        
        course_level = course_row['course_level']
        level_factor = {100: 0.9, 200: 0.7, 300: 0.5, 400: 0.3, 500: 0.1}.get(course_level, 0.5)
        
        take_probability = level_factor * (0.5 + academic_ability * 0.5)
        
        if np.random.random() < take_probability:
            course_difficulty = (
                course_row['prerequisite_count'] * 0.1 +
                course_row['prerequisite_depth'] * 0.1 +
                (course_row['course_level'] / 500) * 0.3 +
                (1 - course_row['graph_centrality']) * 0.1
            )
            
            grade_probability = academic_ability - course_difficulty * 0.3 + np.random.normal(0, 0.1)
            grade_probability = np.clip(grade_probability, 0, 1)
            
            if grade_probability >= 0.9:
                grade = np.random.choice(['A', 'A-'], p=[0.7, 0.3])
            elif grade_probability >= 0.75:
                grade = np.random.choice(['A-', 'B+', 'B'], p=[0.2, 0.4, 0.4])
            elif grade_probability >= 0.6:
                grade = np.random.choice(['B+', 'B', 'B-'], p=[0.3, 0.4, 0.3])
            elif grade_probability >= 0.45:
                grade = np.random.choice(['B-', 'C+', 'C'], p=[0.3, 0.4, 0.3])
            elif grade_probability >= 0.3:
                grade = np.random.choice(['C+', 'C', 'C-'], p=[0.3, 0.4, 0.3])
            elif grade_probability >= 0.15:
                grade = np.random.choice(['C-', 'D+', 'D'], p=[0.3, 0.4, 0.3])
            else:
                grade = np.random.choice(['D', 'F'], p=[0.6, 0.4])
            
            completed_courses.append({
                'student_id': student_id,
                'course_code': course_code,
                'grade': grade,
                'grade_points': GRADE_POINTS[grade],
                'semester_taken': semester,
                'course_level': course_level,
                'prerequisite_count': course_row['prerequisite_count'],
                'prerequisite_depth': course_row['prerequisite_depth'],
                'credit_hours': course_row['credit_hours'],
                'is_lab': course_row['is_lab'],
                'graph_centrality': course_row['graph_centrality']
            })
            
            completed_course_codes.add(course_code)
            courses_this_semester += 1
            
            if courses_this_semester >= target_courses_per_sem:
                semester += 1
                courses_this_semester = 0
                target_courses_per_sem = np.random.randint(3, 6)
                if semester > current_semester:
                    break
    
    if completed_courses:
        total_points = sum(c['grade_points'] * c['credit_hours'] for c in completed_courses)
        total_credits = sum(c['credit_hours'] for c in completed_courses)
        gpa = total_points / total_credits if total_credits > 0 else 0.0
    else:
        gpa = 0.0
    
    student_profile = {
        'student_id': student_id,
        'academic_ability': academic_ability,
        'workload_tolerance': workload_tolerance,
        'strategy': strategy,
        'current_semester': current_semester,
        'gpa': gpa,
        'total_courses_completed': len(completed_courses),
        'total_credits': sum(c['credit_hours'] for c in completed_courses)
    }
    
    return student_profile, completed_courses


def generate_training_data(num_students=5000):
    
    print("=" * 60)
    print("GENERATING SYNTHETIC STUDENT DATA")
    print("=" * 60)
    
    courses_df, prereq_dict = load_courses_and_prerequisites()
    print(f"Loaded {len(courses_df)} courses and {len(prereq_dict)} courses with prerequisites")
    
    print(f"\nGenerating {num_students} student profiles...")
    
    student_profiles = []
    all_completed_courses = []
    
    for student_id in range(1, num_students + 1):
        if student_id % 500 == 0:
            print(f"  Generated {student_id}/{num_students} students...")
        
        profile, courses = generate_student_profile(student_id, courses_df, prereq_dict)
        student_profiles.append(profile)
        all_completed_courses.extend(courses)
    
    students_df = pd.DataFrame(student_profiles)
    student_courses_df = pd.DataFrame(all_completed_courses)
    
    students_file = OUTPUT_DIR / 'synthetic_students.csv'
    courses_file = OUTPUT_DIR / 'synthetic_student_courses.csv'
    
    students_df.to_csv(students_file, index=False)
    student_courses_df.to_csv(courses_file, index=False)
    
    print(f"\n[OK] Generated {len(students_df)} student profiles")
    print(f"[OK] Generated {len(student_courses_df)} course completion records")
    print(f"\nSaved to:")
    print(f"  - {students_file}")
    print(f"  - {courses_file}")
    
    print(f"\nStatistics:")
    print(f"  Average GPA: {students_df['gpa'].mean():.2f}")
    print(f"  Average courses completed: {students_df['total_courses_completed'].mean():.1f}")
    print(f"  Average credits: {students_df['total_credits'].mean():.1f}")
    print(f"  Strategy distribution:")
    print(students_df['strategy'].value_counts().to_string())
    
    return students_df, student_courses_df


if __name__ == '__main__':
    generate_training_data(num_students=5000)
