
from typing import Dict, List
from database.db import get_db
from database.models import Student, Course, StudentCourse
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
        print("[WARNING] OpenAI library not installed. AI advisor will use rule-based responses only.")


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
        print(f"[ERROR] calculate_future_projection: {e}")
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
        grade_points_map = {'A': 4.0, 'B': 3.0, 'C': 2.0, 'D': 1.0, 'F': 0.0}
        
        if action == 'take' and grade:
            new_points = grade_points_map.get(grade.upper(), 3.0) * course_credits
            new_gpa = (total_points + new_points) / (total_credits + course_credits) if (total_credits + course_credits) > 0 else student.gpa
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
            new_gpa = (total_points + new_points) / (total_credits + course_credits) if (total_credits + course_credits) > 0 else student.gpa
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
        print(f"[ERROR] analyze_what_if_scenario: {e}")
        return {}
    finally:
        db.close()


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
        
        if any(word in question_lower for word in ['recommend', 'suggest', 'what should i take', 'next semester', 'what courses']):
            strategy_desc = {'easy': 'easier courses', 'balanced': 'a balanced mix', 'fast': 'accelerated progress'}[student.strategy]
            return f"Based on your {student.strategy} strategy, I recommend {strategy_desc}. Check the Recommendations tab for personalized suggestions. You've completed {completed_count} courses with a GPA of {student.gpa:.2f}. {'Given your strong performance, you can handle challenging courses.' if student.gpa >= 3.5 else 'Focus on maintaining or improving your GPA.' if student.gpa >= 2.5 else 'Consider taking easier courses to rebuild your GPA.'}"
        
        if any(word in question_lower for word in ['difficulty', 'hard', 'easy', 'challenging', 'how hard']):
            return f"I can predict course difficulty based on your GPA ({student.gpa:.2f}) and workload tolerance ({student.workload_tolerance:.1f}). {'Your strong GPA suggests you can handle challenging courses.' if student.gpa >= 3.5 else 'Consider courses that match your current performance level.'} Click the difficulty button on any course for personalized predictions!"
        
        if any(word in question_lower for word in ['prerequisite', 'prereq', 'locked', 'unlock', 'what can i take']):
            return f"Some courses require prerequisites. Check the 'Unlocked Courses' tab to see what's available based on your {completed_count} completed courses. Complete prerequisites to unlock more courses!"
        
        if any(word in question_lower for word in ['semester', 'workload', 'load', 'plan', 'how many credits']):
            return f"I can analyze your semester workload. Your workload tolerance is {student.workload_tolerance:.1f}/1.0. {'You can handle a heavier course load.' if student.workload_tolerance >= 0.7 else 'Consider a moderate course load.'} Use the Semester Planner tab to select courses and get a detailed analysis!"
        
        if any(word in question_lower for word in ['bottleneck', 'priority', 'important', 'which course first']):
            return f"Bottleneck courses unlock many others. Check the 'Bottlenecks' tab to see which courses to prioritize! These courses are critical for your academic progress."
        
        if any(word in question_lower for word in ['progress', 'how am i doing', 'status', 'am i on track']):
            progress_msg = "excellent" if student.gpa >= 3.5 else "good" if student.gpa >= 3.0 else "fair" if student.gpa >= 2.5 else "needs improvement"
            return f"You're making {progress_msg} progress! You've completed {completed_count} courses ({total_credits:.1f} credits) with a GPA of {student.gpa:.2f}. You're in semester {student.current_semester} of your {student.major} major. {'Keep up the excellent work!' if student.gpa >= 3.5 else 'Keep working hard!' if student.gpa >= 2.5 else 'Focus on improving your grades. Consider seeking academic support.'}"
        
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
            return "I can analyze what-if scenarios! Try asking: 'What if I take CS101?', 'What if I fail MATH201?', or 'What if I get a B in ECE301?'"
        
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
                
                context = f
                
                client = OpenAI(api_key=OPENAI_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": context},
                        {"role": "user", "content": question}
                    ],
                    max_tokens=400,
                    temperature=0.8,
                    timeout=20
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
        
        return f"I understand you're asking about something related to your academics. As a {student.major} major with {completed_count} completed course(s) and a GPA of {student.gpa:.2f}, I can help with:\n\n• Future projections (where you'll be in 2 years, graduation timeline)\n• What-if scenarios (if I take/fail a course, GPA impact)\n• Projects and capstones (senior projects, thesis, design courses)\n• GPA analysis and grade tracking\n• Course recommendations\n• Prerequisites and unlocked courses\n• Semester planning\n• Failed courses and retaking advice\n\nTry asking:\n- 'Where will I be in 2 years?'\n- 'What if I take CS101?'\n- 'What if I fail MATH201?'\n- 'What projects can I take?'\n- 'What's my GPA?'"
    
    except Exception as e:
        import traceback
        print(f"[ERROR] chatbot_response error: {e}\n{traceback.format_exc()}")
        return f"I encountered an error processing your question. Please try again or rephrase your question. Error: {str(e)}"
    finally:
        db.close()


def get_bottleneck_courses(student_id: int) -> List[Dict]:
    
    from services.course_cache import get_all_courses, get_prerequisites
    from services.prerequisite_service import get_completed_courses
    
    completed_courses = get_completed_courses(student_id)
    
    all_courses = get_all_courses()
    
    unlocked_courses = []
    locked_courses = []
    
    for course_data in all_courses:
        course_code = course_data.get('course_code', '')
        if not course_code:
            continue
        
        if course_code in completed_courses:
            continue
        
        prereqs = get_prerequisites(course_code)
        if not prereqs:
            unlocked_courses.append({
                'course_code': course_code,
                'name': course_data.get('name', ''),
                'unlocks_count': int(course_data.get('unlocks_count', 0)),
                'is_unlocked': True,
                'missing_prerequisites': [],
                'credit_hours': course_data.get('credit_hours', 0),
                'course_level': course_data.get('course_level', 100),
                'prerequisites': []
            })
        else:
            missing = [p for p in prereqs if p not in completed_courses]
            if not missing:
                unlocked_courses.append({
                    'course_code': course_code,
                    'name': course_data.get('name', ''),
                    'unlocks_count': int(course_data.get('unlocks_count', 0)),
                    'is_unlocked': True,
                    'missing_prerequisites': [],
                    'credit_hours': course_data.get('credit_hours', 0),
                    'course_level': course_data.get('course_level', 100),
                    'prerequisites': prereqs
                })
            else:
                unlocks_count = int(course_data.get('unlocks_count', 0))
                if unlocks_count > 5:
                    locked_courses.append({
                        'course_code': course_code,
                        'name': course_data.get('name', ''),
                        'unlocks_count': unlocks_count,
                        'is_unlocked': False,
                        'missing_prerequisites': missing,
                        'credit_hours': course_data.get('credit_hours', 0),
                        'course_level': course_data.get('course_level', 100),
                        'prerequisites': prereqs
                    })
    
    unlocked_courses.sort(key=lambda x: x.get('unlocks_count', 0), reverse=True)
    
    locked_courses.sort(key=lambda x: x.get('unlocks_count', 0), reverse=True)
    
    bottlenecks = unlocked_courses[:12] + locked_courses[:12]
    
    return bottlenecks
