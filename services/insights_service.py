
from typing import Any, Dict, List

from database.db import get_db
from database.models import Course, Student, StudentCourse
from services.course_cache import get_course_by_code, get_courses_by_subject
from services.advisor import get_bottleneck_courses
from services.prerequisite_service import get_locked_courses, get_unlocked_courses


def get_student_insights(student_id: int) -> Dict[str, Any]:

    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        locked = get_locked_courses(student_id)
        unlocked = get_unlocked_courses(student_id, limit=200)

        locked_high_impact: List[Dict] = []
        for item in locked:
            code = item.get('course_code', '')
            meta = get_course_by_code(code) or {}
            cnt = int(meta.get('unlocks_count', 0) or 0)
            if cnt >= 2:
                locked_high_impact.append({
                    'course_code': code,
                    'name': item.get('name', ''),
                    'missing_prerequisites': item.get('missing_prerequisites', []),
                    'unlocks_count': cnt,
                    'course_level': item.get('course_level', 100),
                })
        locked_high_impact.sort(key=lambda x: (-x['unlocks_count'], -int(x.get('course_level') or 0)))
        locked_high_impact = locked_high_impact[:12]

        advanced_locked: List[Dict] = []
        for item in locked:
            lvl = int(item.get('course_level', 100) or 100)
            if lvl >= 300:
                advanced_locked.append({
                    'course_code': item.get('course_code', ''),
                    'name': item.get('name', ''),
                    'course_level': lvl,
                    'missing_prerequisites': item.get('missing_prerequisites', []),
                })
        advanced_locked.sort(key=lambda x: -x['course_level'])
        advanced_locked = advanced_locked[:10]

        bottlenecks = get_bottleneck_courses(student_id)
        bottleneck_warnings: List[Dict] = []
        for b in bottlenecks[:8]:
            bottleneck_warnings.append({
                'course_code': b.get('course_code', ''),
                'name': b.get('name', ''),
                'unlocks_count': int(b.get('unlocks_count', 0) or 0),
                'is_unlocked': bool(b.get('is_unlocked')),
                'missing_prerequisites': b.get('missing_prerequisites') or [],
            })

        suggestions: List[str] = []
        for b in bottlenecks:
            if b.get('is_unlocked') and int(b.get('unlocks_count', 0) or 0) >= 3:
                suggestions.append(
                    f"Consider taking {b.get('course_code')} soon — it directly unlocks many later courses."
                )
            elif not b.get('is_unlocked') and int(b.get('unlocks_count', 0) or 0) >= 5:
                miss = b.get('missing_prerequisites') or []
                if miss:
                    suggestions.append(
                        f"Prioritize prerequisites {', '.join(miss[:4])} to reach high-impact course {b.get('course_code')}."
                    )
        suggestions = suggestions[:8]

        next_semester_focus = []
        for u in unlocked[:15]:
            uc = get_course_by_code(u.get('course_code', ''))
            cnt = int((uc or {}).get('unlocks_count', 0) or 0)
            next_semester_focus.append({
                'course_code': u.get('course_code', ''),
                'name': u.get('name', ''),
                'unlocks_count': cnt,
                'credit_hours': u.get('credit_hours', 3),
            })
        next_semester_focus.sort(key=lambda x: -x['unlocks_count'])

        completed_rows = (
            db.query(Course.course_code)
            .join(StudentCourse, StudentCourse.course_id == Course.id)
            .filter(StudentCourse.student_id == student_id, StudentCourse.status == 'completed')
            .all()
        )
        completed_codes = {(r[0] or '').strip().upper() for r in completed_rows if r and r[0]}

        timeline = get_semester_timeline(student_id)
        sem_list = timeline.get('semesters') or []
        total_cr = sum(float(s.get('total_credits') or 0) for s in sem_list)

        warnings: List[str] = []
        gpa = float(student.gpa or 0.0)
        if gpa > 0 and gpa < 2.0:
            warnings.append('GPA is under 2.0 — degree progress may be at risk; prioritize required courses and support resources.')
        elif gpa > 0 and gpa < 2.5:
            warnings.append('GPA is below 2.5 — balance your schedule and consider easier electives until grades recover.')

        if len(locked) > 40 and student.current_semester and student.current_semester >= 2:
            warnings.append(f'You have {len(locked)} locked courses — many paths still need prerequisites; focus on bottleneck courses (see Bottlenecks tab).')

        delayed_foundations: List[Dict[str, Any]] = []
        maj = (student.major or '').strip().upper()
        if maj:
            for mc in get_courses_by_subject(maj):
                code = (mc.get('course_code') or '').strip().upper()
                if not code or code in completed_codes:
                    continue
                try:
                    lvl = int(mc.get('course_level', 100) or 100)
                except (TypeError, ValueError):
                    lvl = 100
                if 100 <= lvl <= 250:
                    delayed_foundations.append({
                        'course_code': code,
                        'name': mc.get('name', ''),
                        'course_level': lvl,
                    })
            delayed_foundations.sort(key=lambda x: (x['course_level'], x['course_code']))
            cur = int(student.current_semester or 1)
            if cur >= 4:
                delayed_foundations = [d for d in delayed_foundations if d['course_level'] <= 200][:12]
            else:
                delayed_foundations = delayed_foundations[:12]

        recommendation_preview: List[Dict[str, Any]] = []
        try:
            from services.recommendation_engine import recommend_courses
            reco = recommend_courses(student_id, target_credits=15, max_courses=8, term=None)
            recs = reco.get('recommendations', []) if isinstance(reco, dict) else []
            for r in (recs or [])[:8]:
                recommendation_preview.append({
                    'course_code': r.get('course_code', ''),
                    'name': r.get('name', ''),
                    'credit_hours': r.get('credit_hours', 3),
                    'difficulty_category': r.get('difficulty_category', ''),
                })
        except Exception:
            pass

        prereq_risks: List[Dict[str, Any]] = []
        for item in locked[:25]:
            miss = item.get('missing_prerequisites') or []
            if len(miss) >= 2:
                prereq_risks.append({
                    'course_code': item.get('course_code', ''),
                    'name': item.get('name', ''),
                    'missing_count': len(miss),
                    'missing_prerequisites': miss[:6],
                })
        prereq_risks.sort(key=lambda x: -x['missing_count'])
        prereq_risks = prereq_risks[:8]

        return {
            'major': student.major,
            'current_semester': student.current_semester,
            'gpa': gpa,
            'unlocked_count': len(unlocked),
            'locked_count': len(locked),
            'locked_high_impact': locked_high_impact,
            'advanced_locked': advanced_locked,
            'bottleneck_courses': bottleneck_warnings,
            'suggestions': suggestions,
            'next_semester_candidates': next_semester_focus[:12],
            'warnings': warnings,
            'delayed_foundations': delayed_foundations,
            'prerequisite_risks': prereq_risks,
            'recommendation_preview': recommendation_preview,
            'stats': {
                'semesters_recorded': len(sem_list),
                'total_credits_completed': round(total_cr, 1),
                'avg_credits_per_semester': round(total_cr / len(sem_list), 1) if sem_list else 0.0,
            },
        }
    finally:
        db.close()


def get_semester_timeline(student_id: int) -> Dict[str, Any]:

    db = get_db()
    try:
        rows = (
            db.query(StudentCourse, Course)
            .join(Course, StudentCourse.course_id == Course.id)
            .filter(StudentCourse.student_id == student_id, StudentCourse.status == 'completed')
            .order_by(StudentCourse.semester_taken.asc(), Course.course_code.asc())
            .all()
        )
        by_sem: Dict[int, List[Dict]] = {}
        for sc, course in rows:
            sem = int(sc.semester_taken or 1)
            if sem not in by_sem:
                by_sem[sem] = []
            by_sem[sem].append({
                'course_code': course.course_code,
                'name': course.name or '',
                'credit_hours': float(course.credit_hours or 0),
                'grade': sc.grade or '',
                'grade_points': float(sc.grade_points or 0),
            })
        semesters_sorted = sorted(by_sem.keys())
        return {
            'semesters': [
                {'semester': s, 'courses': by_sem[s], 'total_credits': sum(c['credit_hours'] for c in by_sem[s])}
                for s in semesters_sorted
            ]
        }
    finally:
        db.close()
