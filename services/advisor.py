import logging
from typing import Dict, List
from database.db import get_db

logger = logging.getLogger(__name__)
from database.models import Student, Course, StudentCourse, SemesterPlan, SemesterPlanCourse
from services.prerequisite_service import is_course_unlocked
from services.ml_service import predict_course_difficulty, predict_semester_workload
import os

from config import OPENAI_API_KEY, DEBUG

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    try:
        import openai
        OPENAI_AVAILABLE = True
    except ImportError:
        OPENAI_AVAILABLE = False
        logger.warning("OpenAI library not installed. AI advisor will use rule-based responses only.")


def explain_course_lock(student_id: int, course_code: str) -> str:

    is_unlocked, missing = is_course_unlocked(student_id, course_code)

    if is_unlocked:
        return "This course is unlocked and available for you to take."

    if not missing:
        return "This course requires prerequisites that you haven't completed yet."

    missing_str = ", ".join(missing)
    return f"This course is locked because you haven't completed the following prerequisites: {missing_str}. Please complete these courses first to unlock this course."


def explain_semester_difficulty(student_id: int, course_ids: List[int]) -> str:

    try:
        workload = predict_semester_workload(student_id, course_ids)

        if not workload:
            return f"Basic analysis: {len(course_ids)} courses selected. Unable to predict detailed workload."

        total_credits = workload.get('total_credits', 0)
        num_courses = workload.get('num_courses', len(course_ids))
        num_labs = workload.get('num_labs', 0)
        semester_difficulty = workload.get('semester_difficulty', 0.5)
        overload_risk = workload.get('overload_risk', 0.5)

        difficulty_category = workload.get('difficulty_category', 'Moderate')
        if not difficulty_category:
            if semester_difficulty < 0.33:
                difficulty_category = 'Easy'
            elif semester_difficulty < 0.67:
                difficulty_category = 'Moderate'
            else:
                difficulty_category = 'Challenging'

        risk_category = workload.get('risk_category', 'Medium')
        if not risk_category:
            if overload_risk < 0.3:
                risk_category = 'Low'
            elif overload_risk < 0.6:
                risk_category = 'Medium'
            else:
                risk_category = 'High'

        explanation = f"Semester Analysis:\n"
        explanation += f"- Total Credits: {total_credits:.1f}\n"
        explanation += f"- Number of Courses: {num_courses}\n"
        if num_labs > 0:
            explanation += f"- Lab Courses: {num_labs}\n"
        explanation += f"- Predicted Difficulty: {difficulty_category} ({semester_difficulty:.2f})\n"
        explanation += f"- Overload Risk: {risk_category} ({overload_risk:.2f})\n"

        if overload_risk > 0.6:
            explanation += "\n⚠️ Warning: High overload risk detected. Consider reducing course load."
        elif semester_difficulty > 0.7:
            explanation += "\n⚠️ This semester will be challenging. Make sure you have adequate time and support."
        else:
            explanation += "\n✓ This semester looks manageable based on your academic profile."

        return explanation
    except Exception as e:
        import traceback
        print(f"[WARNING] explain_semester_difficulty failed: {e}\n{traceback.format_exc()}")
        return f"Basic analysis: {len(course_ids)} courses selected. Detailed analysis temporarily unavailable."


def calculate_future_projection(student_id: int, years_ahead: int = 2) -> Dict:

    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        completed_courses = db.query(StudentCourse, Course).join(
            Course, StudentCourse.course_id == Course.id
        ).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).all()

        total_credits = sum(course.credit_hours or 0 for _, course in completed_courses)
        total_points = sum((sc.grade_points or 0) * (course.credit_hours or 0) for sc, course in completed_courses)

        from services.prerequisite_service import get_unlocked_courses
        unlocked = get_unlocked_courses(student_id, limit=200)

        semesters_ahead = years_ahead * 2
        avg_credits_per_semester = 15
        projected_credits = total_credits + (semesters_ahead * avg_credits_per_semester)

        avg_gpa_estimate = student.gpa if student.gpa > 0 else 3.0
        projected_points = total_points + (semesters_ahead * avg_credits_per_semester * avg_gpa_estimate)
        projected_gpa = projected_points / projected_credits if projected_credits > 0 else student.gpa

        graduation_semester = student.current_semester + semesters_ahead

        return {
            'current_credits': total_credits,
            'projected_credits': projected_credits,
            'current_gpa': student.gpa,
            'projected_gpa': projected_gpa,
            'graduation_semester': graduation_semester,
            'years_to_graduation': years_ahead,
            'available_courses': len(unlocked)
        }
    except Exception as e:
        logger.exception("calculate_future_projection failed")
        return {}
    finally:
        db.close()


def analyze_what_if_scenario(student_id: int, course_code: str, grade: str = None, action: str = 'take') -> Dict:

    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {}

        from services.course_cache import get_course_by_code
        course_data = get_course_by_code(course_code)
        if not course_data:
            return {'error': f'Course {course_code} not found'}

        completed_courses = db.query(StudentCourse, Course).join(
            Course, StudentCourse.course_id == Course.id
        ).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).all()

        total_credits = sum(course.credit_hours or 0 for _, course in completed_courses)
        total_points = sum((sc.grade_points or 0) * (course.credit_hours or 0) for sc, course in completed_courses)

        course_credits = float(course_data.get('credit_hours', 3.0))
        grade_points_map = {'A+': 4.3, 'A': 4.0, 'A-': 3.7, 'B+': 3.3, 'B': 3.0, 'B-': 2.7, 'C+': 2.3, 'C': 2.0, 'C-': 1.7, 'D+': 1.3, 'D': 1.0, 'D-': 0.7, 'F': 0.0}

        if action == 'take' and grade:
            new_points = grade_points_map.get(grade.upper(), 3.0) * course_credits
            new_gpa = min(4.0, (total_points + new_points) / (total_credits + course_credits)) if (total_credits + course_credits) > 0 else student.gpa
            return {
                'action': 'take',
                'course': course_code,
                'grade': grade,
                'current_gpa': student.gpa,
                'new_gpa': new_gpa,
                'gpa_change': new_gpa - student.gpa,
                'credits_added': course_credits
            }
        elif action == 'fail':
            new_points = 0.0
            new_gpa = min(4.0, (total_points + new_points) / (total_credits + course_credits)) if (total_credits + course_credits) > 0 else student.gpa
            return {
                'action': 'fail',
                'course': course_code,
                'current_gpa': student.gpa,
                'new_gpa': new_gpa,
                'gpa_change': new_gpa - student.gpa,
                'credits_added': course_credits,
                'warning': 'Failing this course will lower your GPA'
            }
        elif action == 'take':
            course = db.query(Course).filter(Course.course_code == course_code).first()
            if course:
                difficulty = predict_course_difficulty(student_id, course.id)
                return {
                    'action': 'take',
                    'course': course_code,
                    'course_name': course_data.get('name', ''),
                    'credits': course_credits,
                    'difficulty': difficulty.get('difficulty_category', 'Unknown') if difficulty else 'Unknown',
                    'unlocks_count': course_data.get('unlocks_count', 0)
                }

        return {}
    except Exception as e:
        logger.exception("analyze_what_if_scenario failed")
        return {}
    finally:
        db.close()


def _semester_timeline_text(student_id: int) -> str:
    from services.insights_service import get_semester_timeline
    data = get_semester_timeline(student_id)
    lines: List[str] = []
    for block in data.get('semesters') or []:
        sem = block.get('semester', 0)
        courses = block.get('courses') or []
        parts = [f"{c.get('course_code', '')} ({c.get('grade', '—')})" for c in courses]
        cr = float(block.get('total_credits') or 0)
        lines.append(f"  Semester {sem}: {', '.join(parts)} — {cr:.1f} cr total")
    return "\n".join(lines) if lines else "  (none yet — add completed courses under My Courses)"


def chatbot_response(student_id: int, question: str) -> str:

    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return "I couldn't find your student profile. Please make sure you're logged in."

        question_lower = question.lower()

        completed_courses = db.query(StudentCourse, Course).join(
            Course, StudentCourse.course_id == Course.id
        ).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == 'completed'
        ).all()

        completed_count = len(completed_courses)

        failed_courses = []
        passed_courses = []
        course_grades = []
        total_credits = 0
        total_points = 0

        for sc, course in completed_courses:
            grade = sc.grade or 'N/A'
            credits = course.credit_hours or 0
            grade_points = sc.grade_points or 0
            total_credits += credits
            total_points += grade_points * credits

            course_info = {
                'code': course.course_code,
                'name': course.name,
                'grade': grade,
                'credits': credits,
                'grade_points': grade_points
            }
            course_grades.append(course_info)

            if grade and grade.upper() in ['F', 'W', 'I']:
                failed_courses.append(course_info)
            else:
                passed_courses.append(course_info)

        if any(word in question_lower for word in ['hello', 'hi', 'hey']):
            return f"Hello! I'm your AI academic advisor. You're a {student.major} major in semester {student.current_semester} with a GPA of {student.gpa:.2f}. I have access to all your academic data including {completed_count} completed courses. I can help you with:\n\n• Future projections (where you'll be in 2 years)\n• What-if scenarios (if I take/fail a course)\n• Project and capstone questions\n• Course recommendations and planning\n• GPA analysis and improvements\n\nHow can I help you today?"

        if any(word in question_lower for word in ['gpa', 'grade point average', 'what is my gpa']):
            failed_count = len(failed_courses)
            if failed_count > 0:
                failed_list = ', '.join([f"{c['code']} ({c['grade']})" for c in failed_courses[:5]])
                return f"Your current GPA is {student.gpa:.2f} based on {completed_count} completed courses ({total_credits:.1f} credits). You have {failed_count} failed course(s): {failed_list}. {'To improve your GPA, consider retaking failed courses or focusing on easier courses next semester.' if student.gpa < 2.5 else 'Your GPA is good! Keep up the excellent work.'}"
            return f"Your current GPA is {student.gpa:.2f} based on {completed_count} completed courses ({total_credits:.1f} credits). {'Excellent work! Your GPA is strong.' if student.gpa >= 3.5 else 'Good progress! Keep working hard.' if student.gpa >= 3.0 else 'You can improve by focusing on your studies and seeking help when needed.'}"

        if any(word in question_lower for word in ['fail', 'failed', 'f grade', 'what did i fail', 'retake']):
            if failed_courses:
                failed_list = ', '.join([f"{c['code']} - {c['name']} (Grade: {c['grade']})" for c in failed_courses])
                return f"You have {len(failed_courses)} failed course(s): {failed_list}. I recommend retaking these courses to improve your GPA. Check the 'Unlocked Courses' tab to see if they're available again."
            return f"Great news! You haven't failed any courses. Your GPA of {student.gpa:.2f} shows consistent performance. Keep up the excellent work!"

        if any(word in question_lower for word in ['what grades', 'my grades', 'show me my grades', 'course grades']):
            if course_grades:
                recent_grades = course_grades[-10:]
                grades_text = '\n'.join([f"- {c['code']}: {c['grade']} ({c['credits']} credits)" for c in recent_grades])
                return f"Here are your recent course grades:\n{grades_text}\n\nYour overall GPA is {student.gpa:.2f}. {'You can view all your courses in the My Courses tab.' if completed_count > 10 else ''}"
            return f"You haven't completed any courses yet. Add your completed courses in the 'My Courses' tab to see your grades and GPA."

        if any(
            phrase in question_lower
            for phrase in [
                'what did i take',
                'courses each semester',
                'semester by semester',
                'by semester',
                'course history',
                'what courses did i take',
                'list my semesters',
            ]
        ):
            tl = _semester_timeline_text(student_id)
            return f"Here is what the app has recorded for you (semester number = the semester field you entered when adding each course):\n\n{tl}\n\nYou can edit semester numbers under My Courses → Edit on any row."

        if any(word in question_lower for word in ['2 years', 'two years', 'future', 'where will i be', 'graduation', 'graduate', 'in 2 years', 'projection']):
            projection = calculate_future_projection(student_id, years_ahead=2)
            if projection:
                return f"Based on your current progress, here's a 2-year projection:\n\n• Current GPA: {projection['current_gpa']:.2f}\n• Projected GPA (2 years): {projection['projected_gpa']:.2f}\n• Current Credits: {projection['current_credits']:.1f}\n• Projected Credits: {projection['projected_credits']:.1f}\n• Estimated Graduation: Semester {projection['graduation_semester']}\n• Available Courses: {projection['available_courses']} courses unlocked\n\nThis projection assumes an average of 15 credits per semester. Your actual path may vary based on course availability and your choices."
            return f"I can project your academic future! Based on your current GPA of {student.gpa:.2f} and {completed_count} completed courses, if you maintain your current performance, you'll likely graduate around semester {student.current_semester + 4} (2 years from now)."

        if any(phrase in question_lower for phrase in ['what if i take', 'what if i fail', 'if i take', 'if i fail', 'what happens if', 'what if i get']):
            import re
            course_match = re.search(r'\b([A-Z]{2,4}\s?\d{3,4})\b', question.upper())
            if course_match:
                course_code = course_match.group(1).replace(' ', '')
                if 'fail' in question_lower:
                    scenario = analyze_what_if_scenario(student_id, course_code, action='fail')
                    if scenario and 'new_gpa' in scenario:
                        return f"If you fail {course_code}:\n\n• Current GPA: {scenario['current_gpa']:.2f}\n• New GPA: {scenario['new_gpa']:.2f}\n• GPA Change: {scenario['gpa_change']:.2f}\n• Credits: {scenario['credits_added']:.1f}\n\n⚠️ Warning: Failing this course will lower your GPA. Consider retaking it to improve your GPA."
                elif any(grade in question_lower for grade in ['a', 'b', 'c', 'd']):
                    grade_match = re.search(r'\b([A-D])\b', question.upper())
                    if grade_match:
                        grade = grade_match.group(1)
                        scenario = analyze_what_if_scenario(student_id, course_code, grade=grade, action='take')
                        if scenario and 'new_gpa' in scenario:
                            return f"If you take {course_code} and get a {grade}:\n\n• Current GPA: {scenario['current_gpa']:.2f}\n• New GPA: {scenario['new_gpa']:.2f}\n• GPA Change: {scenario['gpa_change']:+.2f}\n• Credits: {scenario['credits_added']:.1f}\n\n{'Great! This will improve your GPA.' if scenario['gpa_change'] > 0 else 'This will lower your GPA slightly.' if scenario['gpa_change'] < 0 else 'This will maintain your GPA.'}"
                else:
                    scenario = analyze_what_if_scenario(student_id, course_code, action='take')
                    if scenario and 'difficulty' in scenario:
                        return f"If you take {course_code} ({scenario.get('course_name', '')}):\n\n• Credits: {scenario['credits']:.1f}\n• Predicted Difficulty: {scenario['difficulty']}\n• Unlocks: {scenario['unlocks_count']} other courses\n\nThis course will help you progress in your {student.major} major."
            return "I can analyze what-if scenarios! Try asking: 'Is EECE210 unlocked?', 'Which failed courses should I repair?', or 'How difficult is EECE310 for me?'"

        if any(word in question_lower for word in ['project', 'capstone', 'thesis', 'senior project', 'final project', 'graduation project']):
            from services.prerequisite_service import get_unlocked_courses
            unlocked = get_unlocked_courses(student_id, limit=200)
            project_courses = [c for c in unlocked if any(word in c.get('name', '').lower() for word in ['project', 'capstone', 'thesis', 'senior', 'design'])]
            if project_courses:
                project_list = '\n'.join([f"• {c.get('course_code', '')} - {c.get('name', '')}" for c in project_courses[:5]])
                eligibility_msg = "You're getting close to capstone eligibility!" if student.current_semester >= 6 else "Focus on completing prerequisites first."
                return f"Based on your {student.major} major and {completed_count} completed courses, here are project/capstone courses you can consider:\n\n{project_list}\n\nYou're in semester {student.current_semester}. {eligibility_msg} Check the Unlocked Courses tab for more details."
            track_msg = "you're on track!" if student.current_semester >= 6 else "focus on building your foundation first."
            return f"As a {student.major} major in semester {student.current_semester}, you'll typically take your capstone/senior project in your final year (semesters 7-8). With {completed_count} completed courses, {track_msg} I can help you plan the prerequisites needed for your capstone project."

        if OPENAI_AVAILABLE and OPENAI_API_KEY and OPENAI_API_KEY.strip():
            try:
                print(f"[DEBUG] Attempting OpenAI API call for question: {question[:50]}...")
                recent_courses = ', '.join([f"{c['code']} ({c['grade']})" for c in course_grades[-10:]])
                failed_list = ', '.join([c['code'] for c in failed_courses]) if failed_courses else 'None'

                from services.prerequisite_service import get_unlocked_courses
                unlocked = get_unlocked_courses(student_id, limit=100)
                unlocked_count = len(unlocked)

                projection = calculate_future_projection(student_id, years_ahead=2)
                projection_text = ""
                if projection:
                    projection_text = f"\nFUTURE PROJECTION (2 years):\n- Projected GPA: {projection['projected_gpa']:.2f}\n- Projected Credits: {projection['projected_credits']:.1f}\n- Estimated Graduation: Semester {projection['graduation_semester']}"

                project_courses = [c.get('course_code', '') for c in unlocked if any(word in c.get('name', '').lower() for word in ['project', 'capstone', 'thesis', 'senior', 'design'])]
                project_text = f"\nProject/Capstone Courses Available: {', '.join(project_courses[:5])}" if project_courses else "\nProject/Capstone Courses: None available yet"

                from services.recommendation_engine import recommend_courses
                try:
                    reco = recommend_courses(student_id, target_credits=15, max_courses=8, term=None)
                    recs = reco.get('recommendations', []) if isinstance(reco, dict) else (reco or [])
                except Exception:
                    recs = []
                rec_lines = "\n".join(
                    [f"- {r.get('course_code', '')}: {r.get('name', '')}" for r in (recs or [])[:12]]
                ) or "(none)"

                bn = get_bottleneck_courses(student_id)[:10]
                bn_lines = "\n".join([
                    f"- {b.get('course_code', '')} ({b.get('name', '')[:40]}): unlocks_count={b.get('unlocks_count', 0)}, "
                    f"{'can take now' if b.get('is_unlocked') else 'locked — missing: ' + ','.join(b.get('missing_prerequisites') or [])}"
                    for b in bn
                ]) or "(none)"

                all_codes_str = ", ".join([c["code"] for c in course_grades])
                target_sem = getattr(student, "target_semester_gpa", None)
                target_line = f"\nTarget GPA (next semester): {target_sem:.2f}" if target_sem is not None else ""

                plan_text = "No semester plan saved in the app."
                try:
                    plan = db.query(SemesterPlan).filter(
                        SemesterPlan.student_id == student_id
                    ).order_by(SemesterPlan.created_at.desc()).first()
                    if plan:
                        pcs = db.query(SemesterPlanCourse, Course).join(
                            Course, SemesterPlanCourse.course_id == Course.id
                        ).filter(SemesterPlanCourse.semester_plan_id == plan.id).all()
                        codes = [c.course_code for _, c in pcs[:20]]
                        plan_text = f"Semester {plan.semester_number} plan: " + (", ".join(codes) if codes else "(empty)")
                except Exception:
                    pass

                timeline_txt = _semester_timeline_text(student_id)

                context = f"""You are the Smart Academic Planning advisor. Use ONLY the data below (it is the student's real record from this website). If something is not in the data, say you don't have it. Reference specific course codes and semester numbers. Be helpful and concrete.

STUDENT PROFILE:
- Major: {student.major}
- Current semester (profile): {student.current_semester}
- Cumulative GPA: {student.gpa:.2f}
- Strategy: {student.strategy}
- Workload tolerance (0–1): {student.workload_tolerance:.2f}{target_line}

COMPLETED COURSES BY SEMESTER (each row is what they logged; semester = number they chose when adding the course):
{timeline_txt}

ALL COMPLETED COURSE CODES ({completed_count}): {all_codes_str}
RECENT GRADES (up to 10): {recent_courses}
FAILED / WITHDRAWN: {failed_list}
UNLOCKED COURSES COUNT (prerequisites satisfied, can add now): {unlocked_count}
{projection_text}
{project_text}

TOP APP RECOMMENDATIONS (same engine as Recommendations tab):
{rec_lines}

BOTTLENECK / HIGH-IMPACT COURSES:
{bn_lines}

LAST SAVED SEMESTER PLAN:
{plan_text}
"""

                client = OpenAI(api_key=OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": context},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=650,
                    temperature=0.45,
                    timeout=25
                )
                ai_response = response.choices[0].message.content
                if ai_response and ai_response.strip():
                    print(f"[DEBUG] OpenAI response received: {ai_response[:100]}...")
                    return ai_response.strip()
                else:
                    print("[WARNING] OpenAI returned empty response")
            except Exception as e:
                import traceback
                error_details = str(e)
                print(f"[WARNING] OpenAI API error: {error_details}")
                if DEBUG:
                    print(f"[DEBUG] Full traceback:\n{traceback.format_exc()}")
        else:
            if not OPENAI_AVAILABLE:
                print("[DEBUG] OpenAI library not available")
            elif not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
                print("[DEBUG] OpenAI API key not set")

        if any(word in question_lower for word in ['recommend', 'suggest', 'what should i take', 'next semester', 'what courses']):
            strategy_desc = {'easy': 'easier courses', 'balanced': 'a balanced mix', 'fast': 'accelerated progress'}.get(student.strategy, 'a balanced mix')
            tl_hint = _semester_timeline_text(student_id)[:500]
            return f"Based on your {student.strategy} strategy, aim for {strategy_desc}. The Recommendations tab lists courses scored for you. Completed: {completed_count} courses, GPA {student.gpa:.2f}.\n\nRecorded by semester:\n{tl_hint}"

        if any(word in question_lower for word in ['difficulty', 'hard', 'easy', 'challenging', 'how hard']):
            return f"Difficulty uses your GPA ({student.gpa:.2f}) and workload tolerance ({student.workload_tolerance:.1f}). Use the Difficulty button on courses in Unlocked / Available. {('Your GPA suggests you can handle harder courses.' if student.gpa >= 3.5 else 'Pick difficulty that matches your recent performance.')}"

        if any(word in question_lower for word in ['prerequisite', 'prereq', 'locked', 'unlock', 'what can i take']):
            return f"With {completed_count} completed courses, see Unlocked Courses for what you can add next. Bottlenecks tab shows high-impact courses. Complete missing prerequisites listed there."

        if any(word in question_lower for word in ['semester', 'workload', 'load', 'plan', 'how many credits']) and 'semester by' not in question_lower:
            return f"Workload tolerance: {student.workload_tolerance:.1f}/1.0. Use Semester Planner to build a schedule and run Analyze Semester.\n\nYour completed history by semester:\n{_semester_timeline_text(student_id)}"

        if any(word in question_lower for word in ['bottleneck', 'priority', 'important', 'which course first']):
            return f"Bottlenecks tab lists courses that unlock many others. Prioritize prerequisites for those codes when planning."

        if any(word in question_lower for word in ['progress', 'how am i doing', 'status', 'am i on track']):
            progress_msg = "excellent" if student.gpa >= 3.5 else "good" if student.gpa >= 3.0 else "fair" if student.gpa >= 2.5 else "needs improvement"
            return f"Progress: {progress_msg}. {completed_count} courses ({total_credits:.1f} cr), GPA {student.gpa:.2f}, profile semester {student.current_semester}, major {student.major}.\n\nBy semester:\n{_semester_timeline_text(student_id)}"

        question_words = question_lower.split()

        if any(qw in question_lower for qw in ['what', 'how', 'why', 'when', 'where', 'can', 'should', 'will', 'tell me', 'explain']):
            if completed_count == 0:
                return f"As a {student.major} major starting your academic journey, I recommend beginning with foundational courses. Check the 'Unlocked Courses' tab to see what's available. You can also explore the Recommendations tab for personalized suggestions based on your {student.strategy} strategy."
            elif completed_count < 5:
                return f"You're just getting started! With {completed_count} completed course(s) and a GPA of {student.gpa:.2f}, you're building a strong foundation. Check the Recommendations tab for courses that match your {student.strategy} strategy and will help you progress in your {student.major} major."
            else:
                return f"Great progress! With {completed_count} completed courses and a GPA of {student.gpa:.2f}, you're doing well in your {student.major} major. {'Your excellent GPA shows you can handle challenging courses!' if student.gpa >= 3.5 else 'Keep up the good work!'} Check the Recommendations tab for your next steps."

        if len(question_words) <= 2:
            return f"I'd be happy to help! You're a {student.major} major with {completed_count} completed course(s) and a GPA of {student.gpa:.2f}. Could you ask me something more specific? For example:\n- 'What's my GPA?'\n- 'What courses should I take next?'\n- 'How am I doing?'\n- 'What courses did I fail?'"

        return f"I understand you're asking about something related to your academics. As a {student.major} major with {completed_count} completed course(s) and a GPA of {student.gpa:.2f}, I can help with:\n\n• Future projections (where you'll be in 2 years, graduation timeline)\n• What-if scenarios (if I take/fail a course, GPA impact)\n• Recommendations and GPA planning (senior projects, thesis, design courses)\n• GPA analysis and grade tracking\n• Course recommendations\n• Prerequisites and unlocked courses\n• Semester planning\n• Failed courses and retaking advice\n\nTry asking:\n- 'Can I reach my target GPA?'\n- 'Is EECE210 unlocked?'\n- 'Which failed courses should I repair?'\n- 'What should I take next semester?'\n- 'What's my GPA?'"

    except Exception as e:
        logger.exception("chatbot_response failed")
        return f"I encountered an error processing your question. Please try again or rephrase your question. Error: {str(e)}"
    finally:
        db.close()


def get_bottleneck_courses(student_id: int) -> List[Dict]:

    from services.course_cache import get_all_courses, get_prerequisites
    from services.prerequisite_service import (
        get_completed_courses,
        is_course_unlocked,
        get_unlocked_courses,
    )

    completed_courses = get_completed_courses(student_id)
    # Same pool as "Unlocked Courses" / recommendations — avoids showing "available" for codes we hide elsewhere
    allowed_codes = {
        c['course_code']
        for c in get_unlocked_courses(student_id, filter_by_major=True, limit=500)
    }

    all_courses = get_all_courses()

    unlocked_courses = []
    locked_courses = []

    for course_data in all_courses:
        course_code = course_data.get('course_code', '')
        if not course_code:
            continue

        if course_code in completed_courses:
            continue

        # Must match get_unlocked_courses / add-completed validation (transitive prereqs + DB edges)
        ok, missing = is_course_unlocked(student_id, course_code)
        prereqs = get_prerequisites(course_code)
        unlocks_count = int(course_data.get('unlocks_count', 0))

        row = {
            'course_code': course_code,
            'name': course_data.get('name', ''),
            'unlocks_count': unlocks_count,
            'is_unlocked': ok,
            'missing_prerequisites': missing,
            'credit_hours': course_data.get('credit_hours', 0),
            'course_level': course_data.get('course_level', 100),
            'prerequisites': prereqs,
        }

        if ok:
            if course_code in allowed_codes:
                unlocked_courses.append(row)
        elif unlocks_count > 5:
            locked_courses.append(row)

    unlocked_courses.sort(key=lambda x: x.get('unlocks_count', 0), reverse=True)

    locked_courses.sort(key=lambda x: x.get('unlocks_count', 0), reverse=True)

    bottlenecks = unlocked_courses[:12] + locked_courses[:12]

    return bottlenecks


# ============================================================
# Final OpenAI-grounded advisor override
# ============================================================
# This final advisor keeps the ML recommender as the source of truth.
# OpenAI, when configured, is used only to explain loaded student data,
# prerequisite status, GPA feasibility, and current ML recommendation outputs.
# If OPENAI_API_KEY is missing/invalid, the same grounded answer is returned
# locally so the project remains reproducible for grading.

import json
import re
from typing import Any


def _final_grade_status(gp: float) -> str:
    try:
        gp = float(gp or 0.0)
    except Exception:
        gp = 0.0
    if gp <= 0.01:
        return "failed"
    if gp < 2.0:
        return "weak pass"
    if gp < 2.7:
        return "acceptable pass"
    if gp < 3.3:
        return "good"
    return "strong"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _final_student_snapshot(db, student_id: int) -> Dict:
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        return {}

    rows = db.query(StudentCourse, Course).join(
        Course, StudentCourse.course_id == Course.id
    ).filter(
        StudentCourse.student_id == student_id,
        StudentCourse.status == "completed"
    ).order_by(StudentCourse.semester_taken.asc(), StudentCourse.id.asc()).all()

    try:
        from services.recommendation_engine import _infer_course_area, _AREA_LABELS
    except Exception:
        _infer_course_area = None
        _AREA_LABELS = {}

    courses, failed, weak = [], [], []
    total_credits = 0.0
    total_points = 0.0
    area_points, area_credits = {}, {}

    for sc, course in rows:
        credits = _safe_float(course.credit_hours, 0.0)
        gp_raw = _safe_float(sc.grade_points, 0.0)
        # A+ may be 4.3 at course level; cumulative GPA is capped later at 4.0.
        gp = min(4.3, max(0.0, gp_raw))
        total_credits += credits
        total_points += gp * credits

        if _infer_course_area:
            try:
                area = _infer_course_area(course)
            except Exception:
                area = str(course.subject or "general").lower()
        else:
            area = str(course.subject or "general").lower()
        label = _AREA_LABELS.get(area, area.replace("_", "/").title())

        item = {
            "code": course.course_code,
            "name": course.name or "",
            "grade": sc.grade or "",
            "grade_points": gp,
            "credits": credits,
            "semester": sc.semester_taken,
            "area": area,
            "area_label": label,
            "status": _final_grade_status(gp),
        }
        courses.append(item)

        is_failed = gp <= 0.01 or str(sc.grade or "").upper() in {"F", "W", "I"}
        if is_failed:
            failed.append(item)
        elif gp < 2.0:
            weak.append(item)

        # Do not count true failures as strength/weakness averages, but do keep weak passes.
        if credits > 0 and gp > 0:
            area_points[area] = area_points.get(area, 0.0) + gp * credits
            area_credits[area] = area_credits.get(area, 0.0) + credits

    calculated_gpa = min(4.0, total_points / total_credits) if total_credits else _safe_float(student.gpa, 0.0)
    area_avgs = {
        area: area_points[area] / area_credits[area]
        for area in area_points
        if area_credits.get(area, 0.0) > 0
    }
    weak_areas = sorted([(a, v) for a, v in area_avgs.items() if v < 2.3], key=lambda x: x[1])
    strong_areas = sorted([(a, v) for a, v in area_avgs.items() if v >= 3.3], key=lambda x: -x[1])

    return {
        "student": student,
        "courses": courses,
        "failed": failed,
        "weak": weak,
        "total_credits": total_credits,
        "gpa": calculated_gpa,
        "area_avgs": area_avgs,
        "weak_areas": weak_areas,
        "strong_areas": strong_areas,
    }


def _final_format_courses(items: List[Dict], max_n: int = 8) -> str:
    if not items:
        return "None recorded."
    lines = []
    for c in items[:max_n]:
        lines.append(
            f"- {c.get('code')}: {c.get('name','')} — {c.get('grade','')} "
            f"({_safe_float(c.get('grade_points')):.1f}), {_safe_float(c.get('credits')):.1f} cr, semester {c.get('semester')}"
        )
    if len(items) > max_n:
        lines.append(f"- ...and {len(items) - max_n} more.")
    return "\n".join(lines)


def _reco_list(reco: Dict) -> List[Dict]:
    if not isinstance(reco, dict):
        return []
    recs = reco.get("recommendations") or []
    return recs if isinstance(recs, list) else []


def _final_format_recommendations(reco: Dict, max_n: int = 6) -> str:
    recs = _reco_list(reco)
    if not recs:
        return "No valid recommendations were produced yet. Add completed courses, check prerequisites, or lower constraints."
    lines = []
    for r in recs[:max_n]:
        code = r.get("course_code", "")
        name = r.get("name", "")
        credits = _safe_float(r.get("credit_hours"), 0.0)
        fit = r.get("ml_fit_score")
        success = r.get("success_probability")
        grade = r.get("expected_grade_points")
        diff = r.get("difficulty_score")
        role = r.get("role_label") or r.get("catalog_bucket") or r.get("role") or "course"
        parts = [f"{code}: {name}", f"{credits:.1f} cr", str(role)]
        if fit is not None:
            parts.append(f"fit {_safe_float(fit)*100:.0f}%")
        if success is not None:
            parts.append(f"success {_safe_float(success)*100:.0f}%")
        if grade is not None:
            parts.append(f"expected grade {_safe_float(grade):.2f}/4.3")
        if diff is not None:
            parts.append(f"difficulty {_safe_float(diff)*100:.0f}%")
        reason = r.get("reason") or r.get("ai_reason") or r.get("recommendation_reason") or ""
        line = "- " + " | ".join(parts)
        if reason:
            reason_one_line = str(reason).replace("\n", " ").strip()
            if len(reason_one_line) > 220:
                reason_one_line = reason_one_line[:217].rstrip() + "..."
            line += f"\n  Why: {reason_one_line}"
        lines.append(line)
    return "\n".join(lines)


def _final_feasibility_text(reco: Dict, snapshot: Dict) -> str:
    params = reco.get("planning_params", {}) if isinstance(reco, dict) else {}
    target = params.get("target_semester_gpa")
    expected = params.get("expected_semester_gpa")
    feasibility = params.get("target_feasibility", {}) or {}
    notes = []
    if target is not None:
        notes.append(f"Target semester GPA: {_safe_float(target):.2f}/4.0.")
    if expected is not None:
        notes.append(f"ML-estimated GPA for the recommended plan: {_safe_float(expected):.2f}/4.0.")
    if params.get("target_reachable_with_current_plan") is False:
        gap = params.get("target_gap_after_plan")
        gap_txt = f" by about {_safe_float(gap):.2f} grade points" if gap is not None else ""
        notes.append(f"Flag: the current recommended plan is below the selected target{gap_txt}.")
    if feasibility.get("cumulative_target_reachable_in_one_semester") is False:
        best = feasibility.get("best_possible_cumulative_after_plan")
        needed = feasibility.get("needed_semester_gpa_to_raise_cumulative_to_target")
        if best is not None:
            notes.append(
                f"Mathematical flag: even a 4.0 semester would only raise cumulative GPA to about {_safe_float(best):.2f}, "
                f"so this cumulative target is not reachable in one semester."
            )
        elif needed is not None:
            notes.append(f"Mathematical flag: you would need {_safe_float(needed):.2f}/4.0 this semester, which exceeds the GPA cap.")
    cw = params.get("credit_warning")
    if cw:
        notes.append(f"Credit warning: {cw}")
    if not notes:
        notes.append("No target-GPA feasibility warning was generated for the current plan.")
    return "\n".join(notes)


def _recommendation_context(student_id: int, student) -> Dict:
    try:
        from services.recommendation_engine import recommend_courses
        return recommend_courses(
            student_id,
            target_credits=15,
            max_courses=6,
            override_target_gpa=getattr(student, "target_semester_gpa", None),
            override_tolerance=float(getattr(student, "workload_tolerance", 0.5) or 0.5),
            include_electives=True,
        )
    except Exception as e:
        return {"recommendations": [], "planning_params": {"advisor_error": str(e)}}


def _course_context(db, student_id: int, question: str) -> str:
    m = re.search(r"\b([A-Z]{2,5})\s?(\d{3,4}[A-Z]?)\b", (question or "").upper())
    if not m:
        return ""
    course_code = f"{m.group(1)}{m.group(2)}"
    course = db.query(Course).filter(Course.course_code == course_code).first()
    if not course:
        return f"Course lookup: {course_code} was not found in the loaded catalogue."
    try:
        unlocked, missing = is_course_unlocked(student_id, course_code)
    except Exception:
        unlocked, missing = False, []
    try:
        pred = predict_course_difficulty(student_id, course.id)
        diff_txt = f"{pred.get('difficulty_category', 'Unknown')} ({_safe_float(pred.get('difficulty_score'))*100:.0f}%)" if pred else "not available"
    except Exception:
        diff_txt = "not available"
    status = "unlocked" if unlocked else f"locked; missing prerequisites: {', '.join(missing or [])}"
    return (
        f"Course lookup: {course.course_code} — {course.name}; credits={_safe_float(course.credit_hours):.1f}; "
        f"status_for_student={status}; predicted_difficulty={diff_txt}."
    )


def _advisor_context_text(snapshot: Dict, reco: Dict, question: str, course_ctx: str = "") -> str:
    student = snapshot["student"]
    weak_areas = [f"{a.replace('_','/').title()} {v:.2f}/4.3" for a, v in snapshot.get("weak_areas", [])[:5]]
    strong_areas = [f"{a.replace('_','/').title()} {v:.2f}/4.3" for a, v in snapshot.get("strong_areas", [])[:5]]
    data = {
        "student": {
            "username": getattr(student, "username", "student"),
            "major": getattr(student, "major", ""),
            "current_gpa_capped_4": round(snapshot.get("gpa", 0.0), 3),
            "completed_credits": round(snapshot.get("total_credits", 0.0), 2),
            "completed_course_count": len(snapshot.get("courses", [])),
            "target_semester_gpa": getattr(student, "target_semester_gpa", None),
            "workload_tolerance": getattr(student, "workload_tolerance", None),
            "strategy": getattr(student, "strategy", None),
        },
        "failed_courses": [c["code"] for c in snapshot.get("failed", [])],
        "weak_passes": [c["code"] for c in snapshot.get("weak", [])[:8]],
        "weak_areas": weak_areas or ["None clearly detected"],
        "strong_areas": strong_areas or ["None clearly detected"],
        "recent_completed_courses": [
            {"code": c["code"], "grade": c["grade"], "points": round(c["grade_points"], 2), "credits": c["credits"], "area": c["area_label"]}
            for c in snapshot.get("courses", [])[-12:]
        ],
        "gpa_feasibility": _final_feasibility_text(reco, snapshot),
        "ml_recommendations": _final_format_recommendations(reco, max_n=6),
        "course_specific_lookup": course_ctx or "No specific course code detected in the question.",
        "important_limits": [
            "Student outcomes are synthetic for this project; do not claim official real-AUB validation.",
            "A+ is 4.3 at course level, but cumulative GPA is capped at 4.0.",
            "Rules filter invalid/locked/already-passed courses; ML ranks valid courses using difficulty, success probability, expected grade, workload, and risk.",
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _local_grounded_answer(question: str, snapshot: Dict, reco: Dict, course_ctx: str) -> str:
    ql = (question or "").lower()
    student = snapshot["student"]

    if any(x in ql for x in ["hello", "hi", "hey"]):
        return (
            f"Hi {student.username}! I can explain your saved academic record and current ML recommendations.\n\n"
            f"Snapshot:\n- Major: {student.major}\n- GPA: {snapshot['gpa']:.2f}/4.0\n"
            f"- Completed credits: {snapshot['total_credits']:.1f}\n- Completed courses: {len(snapshot['courses'])}\n"
            f"- Target semester GPA: {getattr(student, 'target_semester_gpa', None) or 'not set'}\n\n"
            "Ask me: 'Can I reach my target GPA?', 'What should I take next semester?', 'What are my weak areas?', or 'Why was this course recommended?'"
        )

    if any(x in ql for x in ["target", "reach", "possible", "impossible", "feasible", "raise my gpa", "increase my gpa"]):
        return (
            "GPA feasibility check:\n\n"
            f"{_final_feasibility_text(reco, snapshot)}\n\n"
            "If the target is flagged as unrealistic, the safer action is to lower the credit load, retake true failed courses if available, "
            "and choose valid courses from stronger areas while still protecting degree progress."
        )

    if any(x in ql for x in ["recommend", "what should i take", "next semester", "suggest", "why were", "why was", "explain plan", "best plan"]):
        params = reco.get("planning_params", {}) if isinstance(reco, dict) else {}
        return (
            "Recommended next-semester plan:\n\n"
            f"{_final_format_recommendations(reco)}\n\n"
            f"{_final_feasibility_text(reco, snapshot)}\n\n"
            "How to interpret it:\n"
            "- Academic rules remove invalid choices first.\n"
            "- The ML layer ranks the valid courses using predicted difficulty, expected grade, success probability, workload, academic risk, and your strengths/weaknesses.\n"
            f"- Current risk signal: {params.get('academic_risk_level', 'not available')}."
        )

    if any(x in ql for x in ["weak", "weakness", "strength", "strong", "best at", "bad at"]):
        weak_txt = "None clearly detected yet."
        strong_txt = "None clearly detected yet."
        if snapshot["weak_areas"]:
            weak_txt = "\n".join([f"- {a.replace('_','/').title()}: {v:.2f}/4.3 average" for a, v in snapshot["weak_areas"][:5]])
        if snapshot["strong_areas"]:
            strong_txt = "\n".join([f"- {a.replace('_','/').title()}: {v:.2f}/4.3 average" for a, v in snapshot["strong_areas"][:5]])
        return (
            "Your strength/weakness profile based on saved courses:\n\n"
            f"Weaker areas:\n{weak_txt}\n\nStronger areas:\n{strong_txt}\n\n"
            "For GPA protection, the recommender may prefer valid courses from stronger areas when they count toward your degree."
        )

    if any(x in ql for x in ["fail", "failed", "retake", "repair"]):
        return (
            "Failed/repair course check:\n\n"
            f"{_final_format_courses(snapshot['failed'])}\n\n"
            "True failed courses can be recommended again as retakes/repair. Weak passes are warning signals, not automatic retakes."
        )

    if any(x in ql for x in ["gpa", "grade point"]):
        return (
            f"Your current estimated cumulative GPA is {snapshot['gpa']:.2f}/4.0 based on {snapshot['total_credits']:.1f} completed credits.\n\n"
            "A+ counts as 4.3 at the course level, but cumulative GPA is capped at 4.0.\n\n"
            f"{_final_feasibility_text(reco, snapshot)}"
        )

    if course_ctx:
        return (
            f"{course_ctx}\n\n"
            "Use this course only if it supports your degree progress and fits your workload/GPA target."
        )

    if any(x in ql for x in ["history", "what did i take", "completed", "my courses"]):
        return (
            "Your saved completed courses:\n\n"
            f"{_final_format_courses(snapshot['courses'], max_n=12)}\n\n"
            "These records drive GPA, strengths/weaknesses, prerequisite unlocking, and recommendations."
        )

    return (
        "I answer only from your saved profile, loaded catalogue, prerequisite checks, and current ML recommendation output.\n\n"
        "Try: 'Can I reach my target GPA?', 'Why were these courses recommended?', 'What are my weak areas?', "
        "'Which failed courses should I repair?', or 'Is EECE210 unlocked?'"
    )


def _openai_grounded_answer(question: str, snapshot: Dict, reco: Dict, course_ctx: str, local_answer: str) -> str:
    # OpenAI is optional and never required for the project to run.
    try:
        from config import OPENAI_API_KEY as CFG_KEY, OPENAI_MODEL as CFG_MODEL, ADVISOR_USE_OPENAI
    except Exception:
        CFG_KEY, CFG_MODEL, ADVISOR_USE_OPENAI = os.environ.get("OPENAI_API_KEY", ""), os.environ.get("OPENAI_MODEL", "gpt-4o-mini"), True

    if not ADVISOR_USE_OPENAI or not OPENAI_AVAILABLE or not (CFG_KEY or "").strip():
        return local_answer

    try:
        context = _advisor_context_text(snapshot, reco, question, course_ctx)
        system_prompt = (
            "You are AcademicPath's OpenAI-powered academic advisor explanation layer. "
            "You are NOT the recommender model; the local ML system is the source of truth. "
            "Answer using ONLY the supplied context. Do not invent course names, prerequisites, grades, AUB rules, or registration policies. "
            "If the context does not support an answer, say what information is missing. "
            "Be direct, student-friendly, and practical. Mention target-GPA impossibility clearly when flagged. "
            "Do not claim that the synthetic-outcome ML is validated on real AUB student records. "
            "Keep the answer concise: 2 short paragraphs plus bullets when helpful."
        )
        client = OpenAI(api_key=CFG_KEY)
        response = client.chat.completions.create(
            model=CFG_MODEL or "gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Grounded project context:\n{context}\n\nStudent question: {question}"},
            ],
            max_tokens=650,
            temperature=0.15,
            timeout=25,
        )
        out = response.choices[0].message.content
        if out and out.strip():
            return out.strip()
    except Exception as e:
        if DEBUG:
            print(f"[ADVISOR WARNING] OpenAI advisor failed; using local grounded fallback. Error: {e}")
    return local_answer


def chatbot_response(student_id: int, question: str) -> str:
    """Final advisor used by the Flask app.

    The response is grounded in project data. If OpenAI is configured, it rewrites
    and explains that grounded context naturally; otherwise the local deterministic
    advisor returns the same facts.
    """
    db = get_db()
    try:
        snapshot = _final_student_snapshot(db, student_id)
        if not snapshot:
            return "I couldn't find your student profile. Please log in again."

        student = snapshot["student"]
        reco = _recommendation_context(student_id, student)
        course_ctx = _course_context(db, student_id, question or "")
        local_answer = _local_grounded_answer(question or "", snapshot, reco, course_ctx)
        return _openai_grounded_answer(question or "", snapshot, reco, course_ctx, local_answer)
    except Exception as e:
        logger.exception("final chatbot_response failed")
        return "I could not process that question because the advisor context failed to load. Please refresh the page and try again."
    finally:
        db.close()
