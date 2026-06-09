
"""
Synthetic data generator for AcademicPath.

This generator is intentionally designed for an ML course project:
- Outcomes are synthetic, but features mimic what would be known BEFORE registration.
- Student strengths/weaknesses vary by academic area, so recommendations can react to them.
- A+ exists as 4.3 quality points, while cumulative GPA is capped at 4.0.
"""
import json
import math
import random
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
PREREQUISITES_FILE = DATA_DIR / 'prerequisites.csv'
OUTPUT_DIR = DATA_DIR / 'synthetic'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR = Path(__file__).parent.parent / 'reports' / 'ml'
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

GRADE_POINTS = {
    'A+': 4.3, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D+': 1.3, 'D': 1.0, 'F': 0.0
}
ORDERED_GRADES = ['F','D','D+','C-','C','C+','B-','B','B+','A-','A','A+']
POINT_TO_GRADE = sorted([(v,k) for k,v in GRADE_POINTS.items()])

AREA_NAMES = [
    'math', 'physics', 'chem_bio', 'computing', 'circuits', 'signals',
    'systems_control', 'communication', 'lab_project', 'humanities_business'
]

MAJOR_AREAS = {
    'CCE': {'computing', 'communication', 'signals', 'circuits', 'math'},
    'ECE': {'circuits', 'signals', 'systems_control', 'communication', 'physics', 'math'},
    'CSE': {'computing', 'math', 'signals', 'systems_control'},
}

MAJORS = ['CCE', 'ECE', 'CSE']


def _safe_float(x, default=0.0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def _safe_int(x, default=0):
    try:
        if pd.isna(x):
            return default
        return int(float(x))
    except Exception:
        return default


def _course_area(subject, name='', description=''):
    subj = str(subject or '').upper()
    text = f"{name or ''} {description or ''}".lower()
    if subj in {'MATH', 'STAT'}:
        return 'math'
    if subj == 'PHYS':
        return 'physics'
    if subj in {'CHEM', 'BIOL'}:
        return 'chem_bio'
    if subj in {'ENGL', 'FEAA', 'INDE'}:
        return 'humanities_business'
    if 'lab' in text or 'project' in text:
        return 'lab_project'
    if subj == 'CMPS' or any(k in text for k in ['program', 'algorithm', 'data structure', 'software', 'computer', 'network', 'database']):
        return 'computing'
    if any(k in text for k in ['circuit', 'electronics', 'electric', 'power', 'device', 'microelectronic']):
        return 'circuits'
    if any(k in text for k in ['signal', 'image', 'speech', 'digital processing', 'probability']):
        return 'signals'
    if any(k in text for k in ['control', 'robot', 'system', 'embedded', 'automation']):
        return 'systems_control'
    if any(k in text for k in ['communication', 'wireless', 'antenna', 'telecom', 'radio']):
        return 'communication'
    if subj == 'EECE':
        return 'circuits'
    return 'humanities_business'


def _grade_from_points(points):
    p = max(0.0, min(4.3, float(points)))
    # nearest official AUB quality point bucket
    return min(POINT_TO_GRADE, key=lambda x: abs(x[0] - p))[1]


def _base_course_pressure(course):
    level = _safe_float(course.get('course_level', 100), 100) / 500.0
    prereq_count = _safe_float(course.get('prerequisite_count', 0), 0) / 10.0
    prereq_depth = _safe_float(course.get('prerequisite_depth', 0), 0) / 10.0
    credit = _safe_float(course.get('credit_hours', 3), 3) / 4.0
    lab = 1.0 if str(course.get('is_lab', '')).lower() in {'1','true','yes'} else 0.0
    centrality = _safe_float(course.get('graph_centrality', 0), 0)
    # keep pressure in a useful range, not compressed.
    return float(np.clip(0.18 + 0.34*level + 0.18*prereq_count + 0.14*prereq_depth + 0.11*credit + 0.10*lab + 0.05*centrality, 0.12, 0.95))


def load_courses_and_prerequisites():
    courses_df = pd.read_csv(COURSES_FILE)
    # normalize columns
    for col in ['description','name','subject','course_type']:
        if col not in courses_df.columns:
            courses_df[col] = ''
    courses_df['course_area'] = courses_df.apply(lambda r: _course_area(r.get('subject'), r.get('name'), r.get('description')), axis=1)
    courses_df['course_pressure'] = courses_df.apply(_base_course_pressure, axis=1)
    prereq_df = pd.read_csv(PREREQUISITES_FILE)
    prereq_dict = defaultdict(list)
    for _, r in prereq_df.iterrows():
        prereq_dict[str(r['course'])].append(str(r['prerequisite']))
    return courses_df, prereq_dict


def _student_area_vector(major, general_ability):
    # Start around ability, then add meaningful area-specific noise.
    strengths = {}
    for area in AREA_NAMES:
        strengths[area] = float(np.clip(np.random.normal(general_ability, 0.16), 0.05, 0.98))
    # Major-related areas are not always strengths; make them slightly more variable.
    for area in MAJOR_AREAS.get(major, set()):
        strengths[area] = float(np.clip(np.random.normal(general_ability + 0.04, 0.20), 0.05, 0.98))
    return strengths


def _topological_candidate_order(courses_df, prereq_dict, major):
    # Major path first, but include supports/electives. Lower level first.
    df = courses_df.copy()
    def major_bonus(r):
        subj = str(r.get('subject','')).upper()
        area = r.get('course_area','')
        ctype = str(r.get('course_type','')).lower()
        if ctype == 'core' or subj == 'EECE':
            return 0
        if area in MAJOR_AREAS.get(major, set()):
            return 1
        if ctype == 'support':
            return 2
        return 3
    df['major_sort'] = df.apply(major_bonus, axis=1)
    return df.sort_values(['major_sort','course_level','prerequisite_depth','prerequisite_count','course_code']).to_dict('records')


def generate_student_profile(student_id, courses_df, prereq_dict):
    major = random.choice(MAJORS)
    general_ability = float(np.clip(np.random.beta(4.3, 2.8), 0.05, 0.98))
    workload_tolerance = float(np.clip(np.random.beta(3.0, 2.7), 0.05, 0.98))
    strategy = random.choices(['gpa_protective','balanced','major_progress'], weights=[0.30, 0.52, 0.18])[0]
    current_semester = random.randint(2, 8)
    area_strengths = _student_area_vector(major, general_ability)

    completed = []
    completed_codes = set()
    grades_by_area = defaultdict(list)
    grades_by_subject = defaultdict(list)
    grades_all = []
    credits_all = 0.0

    ordered = _topological_candidate_order(courses_df, prereq_dict, major)
    term = 1
    max_terms = current_semester
    target_load_by_term = {t: random.choice([12, 13, 14, 15, 16, 17]) for t in range(1, max_terms+1)}
    term_credits = 0.0

    for course in ordered:
        if term > max_terms:
            break
        code = str(course['course_code'])
        if code in completed_codes:
            continue
        prereqs = prereq_dict.get(code, [])
        if not all(p in completed_codes for p in prereqs):
            # sometimes students take course without full prerequisite coverage, but rarely.
            if random.random() > 0.035:
                continue
        credits = _safe_float(course.get('credit_hours', 3), 3)
        if term_credits + credits > target_load_by_term[term] + 1:
            term += 1
            term_credits = 0.0
            if term > max_terms:
                break
        area = course.get('course_area') or _course_area(course.get('subject'), course.get('name'), course.get('description'))
        subject = str(course.get('subject','')).upper()
        ctype = str(course.get('course_type','')).lower()
        is_major_area = area in MAJOR_AREAS.get(major, set()) or subject == 'EECE'
        # Course-taking probability depends on degree role.
        if ctype == 'core' or subject == 'EECE':
            take_prob = 0.72
        elif ctype == 'support':
            take_prob = 0.62
        elif is_major_area:
            take_prob = 0.43
        else:
            take_prob = 0.25 if strategy != 'gpa_protective' else 0.38
        if random.random() > take_prob:
            continue

        prior_gpa = min(4.0, (sum(g*cr for g,cr in grades_all) / credits_all) if credits_all else np.random.normal(2.9,0.35))
        recent = [g for g,_ in grades_all[-8:]]
        recent_avg = float(np.mean(recent)) if recent else prior_gpa
        prereq_grades = []
        for p in prereqs:
            for row in completed:
                if row['course_code'] == p:
                    prereq_grades.append(row['grade_points'])
        prereq_avg = float(np.mean(prereq_grades)) if prereq_grades else prior_gpa
        prereq_ratio = sum(1 for p in prereqs if p in completed_codes)/max(1,len(prereqs)) if prereqs else 1.0
        area_avg = float(np.mean(grades_by_area[area])) if grades_by_area[area] else prior_gpa
        subject_avg = float(np.mean(grades_by_subject[subject])) if grades_by_subject[subject] else prior_gpa

        pressure = _base_course_pressure(course)
        level = _safe_int(course.get('course_level',100),100)
        lab = 1 if str(course.get('is_lab','')).lower() in {'1','true','yes'} else 0
        term_load = target_load_by_term[term]
        term_pressure = max(0, (term_load - 12)/6.0)
        latent_strength = area_strengths.get(area, general_ability)
        # Outcome uses pre-attempt factors + noise. No leakage features.
        grade_mu = (
            1.34
            + 1.18*general_ability
            + 1.05*latent_strength
            + 0.34*(prior_gpa/4.0)
            + 0.24*(recent_avg/4.0)
            + 0.22*(prereq_avg/4.0)
            + 0.16*workload_tolerance
            - 1.12*pressure
            - 0.26*term_pressure
            - 0.22*(1.0 - prereq_ratio)
            - 0.12*lab
        ) * 1.10
        # Major courses tend to be more demanding, especially in weak area.
        if subject == 'EECE' or ctype == 'core':
            grade_mu -= 0.18 + 0.22*max(0, 0.50-latent_strength)
        # Electives in strong non-major areas can genuinely help GPA.
        if ctype in {'general_elective','major_elective'} and latent_strength > 0.70:
            grade_mu += 0.18
        grade_points = float(np.clip(np.random.normal(grade_mu, 0.42), 0.0, 4.3))
        grade = _grade_from_points(grade_points)
        grade_points = GRADE_POINTS[grade]

        completed.append({
            'student_id': student_id,
            'major': major,
            'course_code': code,
            'subject': subject,
            'course_area': area,
            'course_type': ctype,
            'grade': grade,
            'grade_points': grade_points,
            'semester_taken': term,
            'course_level': _safe_int(course.get('course_level',100),100),
            'prerequisite_count': _safe_int(course.get('prerequisite_count',0),0),
            'prerequisite_depth': _safe_int(course.get('prerequisite_depth',0),0),
            'credit_hours': credits,
            'is_lab': lab,
            'graph_centrality': _safe_float(course.get('graph_centrality',0),0),
            'prior_gpa': round(float(prior_gpa),3),
            'recent_grade_avg_before': round(float(recent_avg),3),
            'prereq_avg_before': round(float(prereq_avg),3),
            'subject_avg_before': round(float(subject_avg),3),
            'area_strength_before': round(float(area_avg),3),
            'weak_area_flag': int(area_avg < 2.3 and len(grades_by_area[area]) >= 1),
            'strong_area_flag': int(area_avg >= 3.3 and len(grades_by_area[area]) >= 1),
            'prior_credits': round(float(credits_all),2),
            'completed_courses_before': len(completed),
            'term_credit_load': float(term_load),
            'prerequisite_completed_ratio': round(float(prereq_ratio),3),
            'course_pressure': round(float(pressure),4),
            'latent_area_strength': round(float(latent_strength),3),
        })
        completed_codes.add(code)
        grades_by_area[area].append(grade_points)
        grades_by_subject[subject].append(grade_points)
        grades_all.append((grade_points, credits))
        credits_all += credits
        term_credits += credits

    if credits_all:
        gpa_raw = sum(g*cr for g,cr in grades_all) / credits_all
        gpa = min(4.0, gpa_raw)
    else:
        gpa = 0.0
    profile = {
        'student_id': student_id,
        'major': major,
        'academic_ability': general_ability,
        'workload_tolerance': workload_tolerance,
        'strategy': strategy,
        'current_semester': current_semester,
        'gpa': round(float(gpa),3),
        'total_courses_completed': len(completed),
        'total_credits': round(float(credits_all),2),
    }
    for area in AREA_NAMES:
        profile[f'latent_strength_{area}'] = round(float(area_strengths.get(area, general_ability)),3)
    return profile, completed


def generate_training_data(num_students=1800):
    print('='*70)
    print('GENERATING SYNTHETIC STUDENT DATA - STRENGTH/WEAKNESS VERSION')
    print('='*70)
    courses_df, prereq_dict = load_courses_and_prerequisites()
    print(f'Loaded {len(courses_df)} courses and {len(prereq_dict)} prerequisite course entries')
    students=[]; attempts=[]
    for sid in range(1, num_students+1):
        if sid % 500 == 0:
            print(f'  Generated {sid}/{num_students} students...')
        p, cs = generate_student_profile(sid, courses_df, prereq_dict)
        students.append(p); attempts.extend(cs)
    students_df=pd.DataFrame(students)
    attempts_df=pd.DataFrame(attempts)
    students_file=OUTPUT_DIR/'synthetic_students.csv'
    attempts_file=OUTPUT_DIR/'synthetic_student_courses.csv'
    students_df.to_csv(students_file,index=False)
    attempts_df.to_csv(attempts_file,index=False)
    summary={
        'students': int(len(students_df)),
        'attempts': int(len(attempts_df)),
        'mean_gpa_capped_4': float(students_df['gpa'].mean()),
        'median_gpa_capped_4': float(students_df['gpa'].median()),
        'grade_distribution': attempts_df['grade'].value_counts(normalize=True).round(4).to_dict() if len(attempts_df) else {},
        'area_distribution': attempts_df['course_area'].value_counts(normalize=True).round(4).to_dict() if len(attempts_df) else {},
        'note': 'Synthetic outcomes only. Features ending with _before are pre-attempt features for ML training.'
    }
    (REPORTS_DIR/'synthetic_data_strength_weakness_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(f'[OK] students={len(students_df)} attempts={len(attempts_df)}')
    print(f"Average GPA: {students_df['gpa'].mean():.2f}, median={students_df['gpa'].median():.2f}")
    print('Grade distribution:')
    print(attempts_df['grade'].value_counts(normalize=True).sort_index().to_string())
    return students_df, attempts_df

if __name__ == '__main__':
    generate_training_data(num_students=1800)
