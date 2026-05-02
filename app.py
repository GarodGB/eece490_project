from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_cors import CORS
import io
import csv
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, test_connection, engine
from sqlalchemy import inspect, text
from database.models import (
    Base,
    Student, Course, StudentCourse, SemesterPlan, SemesterPlanCourse, CourseRating,
    AcademicCalendarEvent, FinancialRecord, Scholarship, StudySession, StudyGoal,
    Assignment, AcademicGoal, CourseWishlist, StudyNote, LearningResource, CourseDifficultyPrediction
)
from services.prerequisite_service import (
    get_unlocked_courses,
    get_locked_courses,
    is_course_unlocked,
    get_completed_courses as student_completed_course_codes,
    get_prerequisite_codes_merged,
)
from services.ml_service import predict_course_difficulty, predict_semester_workload
from services.recommendation_engine import recommend_courses, optimize_semester_plan
from services.advisor import explain_course_lock, explain_semester_difficulty, chatbot_response, get_bottleneck_courses
from services.prerequisite_graph import build_prerequisite_graph
from config import SECRET_KEY, GRADE_POINTS
from functools import wraps
import json
import logging

if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app_log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)

Base.metadata.create_all(bind=engine)


def _ensure_sqlite_student_columns():
    try:
        insp = inspect(engine)
        if 'students' not in insp.get_table_names():
            return
        cols = {c['name'] for c in insp.get_columns('students')}
        if 'target_semester_gpa' not in cols:
            with engine.begin() as conn:
                conn.execute(text('ALTER TABLE students ADD COLUMN target_semester_gpa FLOAT'))
    except Exception as e:
        print(f"[WARNING] SQLite migration (target_semester_gpa): {e}")


_ensure_sqlite_student_columns()

@app.before_request
def setup():
    if not hasattr(app, 'db_tested'):
        if not test_connection():
            print("[WARNING] Database connection failed. Please check your credentials.")
        app.db_tested = True
    if session.get('is_admin'):
        path = request.path
        if path.startswith('/static/') or path == '/favicon.ico':
            pass
        elif path.startswith('/api/'):
            if not path.startswith('/api/admin') and path != '/api/logout':
                return jsonify({'success': False, 'message': 'Forbidden'}), 403
        elif path not in ('/', '/login', '/register', '/admin') and not path.startswith('/admin/'):
            return redirect(url_for('admin_dashboard'))


def admin_required(f):
    
    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'student_id' not in session:
            if 'application/json' in request.headers.get('Accept', ''):
                return jsonify({'success': False, 'message': 'Not authenticated'}), 403
            return redirect(url_for('login_page'))
        db = get_db()
        try:
            student = db.query(Student).filter(Student.id == session['student_id']).first()
            if not student or not getattr(student, 'is_admin', False):
                if 'application/json' in request.headers.get('Accept', ''):
                    return jsonify({'success': False, 'message': 'Forbidden'}), 403
                return redirect(url_for('dashboard'))
        finally:
            db.close()
        return f(*args, **kwargs)
    return wrapped



@app.route('/')
def index():
    
    return render_template('index.html')


@app.route('/login')
def login_page():
    
    if 'student_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('is_admin') else url_for('dashboard'))
    return render_template('login.html')


@app.route('/register')
def register_page():
    
    if 'student_id' in session:
        return redirect(url_for('admin_dashboard') if session.get('is_admin') else url_for('dashboard'))
    return render_template('register.html')


@app.route('/dashboard')
def dashboard():
    
    if 'student_id' not in session:
        return redirect(url_for('login_page'))
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return render_template('dashboard.html')


@app.route('/profile')
def profile_page():
    
    if 'student_id' not in session:
        return redirect(url_for('login_page'))
    if session.get('is_admin'):
        return redirect(url_for('admin_dashboard'))
    return render_template('profile.html')


@app.route('/admin')
@admin_required
def admin_dashboard():
    
    return render_template('admin/dashboard.html')


@app.route('/admin/courses')
@admin_required
def admin_courses():
    
    return render_template('admin/courses.html')



@app.route('/api/register', methods=['POST'])
def register_api():
    
    data = request.json
    db = get_db()
    
    try:
        existing = db.query(Student).filter(
            (Student.username == data['username']) | (Student.email == data['email'])
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
        
        student = Student(
            username=data['username'],
            email=data['email'],
            password_hash=generate_password_hash(data['password']),
            major=data.get('major', 'ECE').upper(),
            strategy=data.get('strategy', 'balanced'),
            workload_tolerance=float(data.get('workload_tolerance', 0.5))
        )
        
        db.add(student)
        db.commit()
        
        session['student_id'] = student.id
        session['username'] = student.username
        session['is_admin'] = getattr(student, 'is_admin', False)
        
        payload = {
            'success': True,
            'message': 'Registration successful',
            'student_id': student.id,
        }
        if getattr(student, 'is_admin', False):
            payload['redirect_to'] = '/admin'
        return jsonify(payload)
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/login', methods=['POST'])
def login_api():
    
    data = request.json
    db = get_db()
    
    try:
        student = db.query(Student).filter(Student.username == data['username']).first()
        
        if not student or not check_password_hash(student.password_hash, data['password']):
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 401
        
        session['student_id'] = student.id
        session['username'] = student.username
        session['is_admin'] = getattr(student, 'is_admin', False)
        
        payload = {
            'success': True,
            'message': 'Login successful',
            'student_id': student.id,
        }
        if getattr(student, 'is_admin', False):
            payload['redirect_to'] = '/admin'
        return jsonify(payload)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/logout', methods=['POST'])
def logout():
    
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})


@app.route('/api/student/profile', methods=['GET'])
def get_profile():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        return jsonify({
            'success': True,
            'profile': {
                'id': student.id,
                'username': student.username,
                'email': student.email,
                'major': student.major,
                'gpa': student.gpa,
                'current_semester': student.current_semester,
                'strategy': student.strategy,
                'workload_tolerance': student.workload_tolerance,
                'target_semester_gpa': getattr(student, 'target_semester_gpa', None),
                'created_at': student.created_at.isoformat() if student.created_at else None,
                'updated_at': student.updated_at.isoformat() if student.updated_at else None
            }
        })
    finally:
        db.close()


@app.route('/api/student/profile', methods=['PUT', 'POST'])
def update_profile():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            db.close()
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        updated = False
        if 'strategy' in data and data['strategy']:
            student.strategy = str(data['strategy']).strip()
            updated = True
        
        if 'workload_tolerance' in data:
            try:
                tolerance = float(data['workload_tolerance'])
                if 0.0 <= tolerance <= 1.0:
                    student.workload_tolerance = tolerance
                    updated = True
            except (ValueError, TypeError):
                pass
        
        if 'target_semester_gpa' in data:
            try:
                tg = data['target_semester_gpa']
                if tg is None or tg == '':
                    student.target_semester_gpa = None
                    updated = True
                else:
                    tgf = float(tg)
                    if 0.0 <= tgf <= 4.0:
                        student.target_semester_gpa = tgf
                        updated = True
            except (ValueError, TypeError):
                pass
        
        if 'major' in data and data['major']:
            student.major = str(data['major']).upper().strip()
            updated = True
        
        if 'current_semester' in data:
            try:
                semester = int(data['current_semester'])
                if 1 <= semester <= 20:
                    student.current_semester = semester
                    updated = True
            except (ValueError, TypeError):
                pass
        
        if updated:
            db.commit()
            profile_data = {
                'major': student.major,
                'current_semester': student.current_semester,
                'strategy': student.strategy,
                'workload_tolerance': student.workload_tolerance,
                'target_semester_gpa': getattr(student, 'target_semester_gpa', None),
                'gpa': student.gpa
            }
            db.close()
            return jsonify({
                'success': True, 
                'message': 'Profile updated successfully',
                'profile': profile_data
            })
        else:
            db.close()
            return jsonify({'success': False, 'message': 'No valid fields to update'}), 400
            
    except Exception as e:
        db.rollback()
        app_log.exception("Profile update failed")
        db.close()
        return jsonify({'success': False, 'message': f'Update failed: {str(e)}'}), 500


@app.route('/api/courses/completed', methods=['GET'])
def get_completed_courses():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        student_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).order_by(StudentCourse.semester_taken.desc()).all()
        
        courses = []
        for sc in student_courses:
            course = db.query(Course).filter(Course.id == sc.course_id).first()
            if course:
                courses.append({
                    'id': sc.id,
                    'course_id': course.id,
                    'course_code': course.course_code,
                    'name': course.name or 'N/A',
                    'grade': sc.grade,
                    'grade_points': float(sc.grade_points) if sc.grade_points else 0.0,
                    'credit_hours': float(course.credit_hours),
                    'semester_taken': sc.semester_taken
                })
        
        return jsonify({'success': True, 'courses': courses})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/completed', methods=['POST'])
def add_completed_course():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json or {}
    course_code_add = (data.get('course_code') or '').strip().upper()
    if not course_code_add:
        return jsonify({'success': False, 'message': 'course_code is required'}), 400
    
    unlocked, missing_prereqs = is_course_unlocked(session['student_id'], course_code_add)
    if not unlocked:
        completed_set = student_completed_course_codes(session['student_id'])
        direct_codes = get_prerequisite_codes_merged(course_code_add)
        missing_main = [p for p in direct_codes if p not in completed_set]
        if not missing_main:
            missing_main = list(missing_prereqs)
        main_str = ', '.join(missing_main)
        full_str = ', '.join(missing_prereqs)
        user_message = (
            f'The prerequisite course(s) for {course_code_add} are not completed yet. '
            f'Please go to My Courses and add those prerequisite course(s) first (with a grade) before adding {course_code_add}. '
            f'Start with: {main_str}.'
        )
        if full_str != main_str:
            user_message += f' All required courses you still need: {full_str}.'
        return jsonify({
            'success': False,
            'message': user_message,
            'user_message': user_message,
            'course_code': course_code_add,
            'missing_prerequisites': missing_prereqs,
            'missing_direct_prerequisites': missing_main,
            'prerequisite_error': True
        }), 400
    
    db = get_db()
    
    try:
        course = db.query(Course).filter(Course.course_code == course_code_add).first()
        if not course:
            from services.course_cache import get_course_by_code
            course_data = get_course_by_code(course_code_add)
            if not course_data:
                return jsonify({'success': False, 'message': 'Course not found'}), 404
            
            def safe_str(val, default=''):
                if val is None or str(val).lower() == 'nan':
                    return default
                return str(val).strip()
            
            def safe_float(val, default=0.0):
                try:
                    if val is None or str(val).lower() == 'nan':
                        return default
                    return float(val)
                except:
                    return default
            
            def safe_int(val, default=0):
                try:
                    if val is None or str(val).lower() == 'nan':
                        return default
                    return int(float(val))
                except:
                    return default
            
            def safe_bool(val):
                if val is None or str(val).lower() == 'nan':
                    return False
                if isinstance(val, bool):
                    return val
                s = str(val).strip().lower()
                return s in ('1', 'true', 'yes', 'y', 't')
            
            course = Course(
                course_code=safe_str(course_code_add),
                subject=safe_str(course_data.get('subject', '')),
                number=safe_str(course_data.get('number', '')),
                name=safe_str(course_data.get('name', '')),
                description=safe_str(course_data.get('description', '')),
                credit_hours=safe_float(course_data.get('credit_hours', 3.0), 3.0),
                course_level=safe_int(course_data.get('course_level', 100), 100),
                course_type='',
                is_lab=safe_bool(course_data.get('is_lab', False)),
                is_major_course=safe_bool(course_data.get('is_major_course', True)),
                prerequisite_count=safe_int(course_data.get('prerequisite_count', 0), 0),
                prerequisite_depth=safe_int(course_data.get('prerequisite_depth', 0), 0),
                graph_centrality=safe_float(course_data.get('graph_centrality', 0.0), 0.0),
                unlocks_count=safe_int(course_data.get('unlocks_count', 0), 0)
            )
            db.add(course)
            db.commit()
            db.refresh(course)
        
        existing = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.course_id == course.id,
            StudentCourse.status == 'completed'
        ).first()
        
        if existing:
            return jsonify({
                'success': False, 
                'message': f'Course {course_code_add} is already in your completed courses. You can edit it from the "My Courses" tab.',
                'duplicate': True,
                'existing_id': existing.id
            }), 400
        
        grade = data.get('grade', '')
        grade_points = GRADE_POINTS.get(grade, 0.0)
        
        student_course = StudentCourse(
            student_id=session['student_id'],
            course_id=course.id,
            grade=grade,
            grade_points=grade_points,
            semester_taken=data.get('semester_taken', 1),
            status='completed'
        )
        
        db.add(student_course)
        db.flush()
        
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            db.rollback()
            db.close()
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        all_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all()
        
        total_points = 0.0
        total_credits = 0.0
        
        for sc in all_courses:
            course_obj = db.query(Course).filter(Course.id == sc.course_id).first()
            if course_obj and sc.grade_points is not None:
                total_points += sc.grade_points * course_obj.credit_hours
                total_credits += course_obj.credit_hours
        
        student.gpa = total_points / total_credits if total_credits > 0 else 0.0
        if all_courses:
            student.current_semester = max([sc.semester_taken for sc in all_courses if sc.semester_taken] + [1])
        
        db.commit()
        return jsonify({
            'success': True, 
            'message': 'Course added successfully', 
            'gpa': float(student.gpa),
            'current_semester': student.current_semester
        })
    except Exception as e:
        db.rollback()
        app_log.exception("Add course failed")
        return jsonify({'success': False, 'message': f'Failed to add course: {str(e)}'}), 500
    finally:
        db.close()


@app.route('/api/courses/completed/<int:student_course_id>', methods=['PUT'])
def update_completed_course(student_course_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    
    try:
        student_course = db.query(StudentCourse).filter(
            StudentCourse.id == student_course_id,
            StudentCourse.student_id == session['student_id']
        ).first()
        
        if not student_course:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        
        if 'grade' in data:
            student_course.grade = data['grade']
            student_course.grade_points = GRADE_POINTS.get(data['grade'], 0.0)
        
        if 'semester_taken' in data:
            student_course.semester_taken = int(data['semester_taken'])
        
        db.commit()
        
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        all_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all()
        
        total_points = 0.0
        total_credits = 0.0
        
        for sc in all_courses:
            course = db.query(Course).filter(Course.id == sc.course_id).first()
            if course and sc.grade_points is not None:
                total_points += sc.grade_points * course.credit_hours
                total_credits += course.credit_hours
        
        student.gpa = total_points / total_credits if total_credits > 0 else 0.0
        student.current_semester = max([sc.semester_taken for sc in all_courses] + [1])
        
        db.commit()
        return jsonify({'success': True, 'message': 'Course updated', 'gpa': student.gpa})
    except Exception as e:
        db.rollback()
        app_log.exception("Update course failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/completed/<int:student_course_id>', methods=['DELETE'])
def delete_completed_course(student_course_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    
    try:
        student_course = db.query(StudentCourse).filter(
            StudentCourse.id == student_course_id,
            StudentCourse.student_id == session['student_id']
        ).first()
        
        if not student_course:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        
        db.delete(student_course)
        db.commit()
        
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        all_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all()
        
        total_points = 0.0
        total_credits = 0.0
        
        for sc in all_courses:
            course = db.query(Course).filter(Course.id == sc.course_id).first()
            if course and sc.grade_points is not None:
                total_points += sc.grade_points * course.credit_hours
                total_credits += course.credit_hours
        
        student.gpa = total_points / total_credits if total_credits > 0 else 0.0
        if all_courses:
            student.current_semester = max([sc.semester_taken for sc in all_courses])
        else:
            student.current_semester = 1
        
        db.commit()
        return jsonify({'success': True, 'message': 'Course deleted', 'gpa': student.gpa})
    except Exception as e:
        db.rollback()
        app_log.exception("Delete course failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/unlocked', methods=['GET'])
def get_unlocked():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        limit = int(request.args.get('limit', 150))
        limit = max(10, min(limit, 500))
        courses = get_unlocked_courses(
            session['student_id'], filter_by_major=True, limit=limit, sort_mode='balanced'
        )
        return jsonify({'success': True, 'courses': courses})
    except Exception as e:
        app_log.exception("/api/courses/unlocked failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/courses/available', methods=['GET'])
def get_available_courses_with_difficulty():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        limit = int(request.args.get('limit', 150))
        limit = max(10, min(limit, 500))
        unlocked = get_unlocked_courses(
            session['student_id'], filter_by_major=True, limit=limit, sort_mode='balanced'
        )
        
        completed_rows = (
            db.query(Course.course_code)
            .join(StudentCourse, Course.id == StudentCourse.course_id)
            .filter(StudentCourse.student_id == session['student_id'], StudentCourse.status == 'completed')
            .all()
        )
        completed_codes = {r[0] for r in completed_rows if r and r[0]}
        
        available = [c for c in unlocked if c.get('course_code', '') not in completed_codes]
        
        from services.course_cache import get_course_by_code
        courses_with_difficulty = []
        for course_data in available:
            course_code = course_data.get('course_code', '')
            if not course_code:
                continue
            
            cache_course = get_course_by_code(course_code)
            if not cache_course:
                continue
            
            credit_hours = float(cache_course.get('credit_hours', 0) or 0)
            
            if credit_hours <= 0:
                continue
            
            from services.course_cache import get_course_difficulty
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
            
            subject = str(cache_course.get('subject', '')).upper()
            
            courses_with_difficulty.append({
                **course_data,
                'id': 0,
                'difficulty_score': difficulty_score,
                'difficulty_category': category,
                'subject': subject
            })
        
        buckets = {'Easy': [], 'Medium': [], 'Hard': []}
        for c in courses_with_difficulty:
            buckets.get(c.get('difficulty_category', 'Medium'), buckets['Medium']).append(c)
        for k in buckets:
            buckets[k].sort(key=lambda x: (x.get('course_level', 100), x.get('course_code', '')))

        mixed = []
        _mix_guard = 0
        while len(mixed) < len(courses_with_difficulty) and any(buckets[k] for k in ['Easy', 'Medium', 'Hard']):
            _mix_guard += 1
            if _mix_guard > len(courses_with_difficulty) + 10:
                break
            for k in ['Easy', 'Medium', 'Hard']:
                if buckets[k]:
                    mixed.append(buckets[k].pop(0))
        courses_with_difficulty = mixed
        
        return jsonify({'success': True, 'courses': courses_with_difficulty})
    except Exception as e:
        app_log.exception("/api/courses/available failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/locked', methods=['GET'])
def get_locked():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        courses = get_locked_courses(session['student_id'])
        return jsonify({'success': True, 'courses': courses})
    finally:
        pass


@app.route('/api/courses/search', methods=['GET'])
def search_courses():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    query = request.args.get('q', '').strip() or request.args.get('query', '').strip()
    db = get_db()
    
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        from services.course_cache import (
            search_courses as cache_search,
            get_browse_catalog,
            catalog_tag,
        )

        if query:
            all_results = cache_search(query, limit=250)
        else:
            all_results = get_browse_catalog(student.major)

        result = []
        major = student.major
        for course_data in all_results[:800]:
            course_code = course_data.get('course_code', '')
            if not course_code:
                continue

            subj = str(course_data.get('subject', '')).strip()
            tag = catalog_tag(subj, major)
            result.append({
                'course_code': course_code,
                'name': course_data.get('name', ''),
                'subject': subj,
                'credit_hours': float(course_data.get('credit_hours', 3.0)),
                'course_level': int(course_data.get('course_level', 100)),
                'is_major_course': tag == 'major',
                'catalog_tag': tag,
            })
        
        order = {'major': 0, 'elective': 1, 'support': 2}
        result.sort(
            key=lambda x: (
                order.get(x.get('catalog_tag'), 2),
                x['course_level'],
                x['course_code'],
            )
        )
        
        return jsonify({'success': True, 'courses': result})
    except Exception as e:
        app_log.exception("Course search failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/<course_code>/difficulty', methods=['GET'])
def get_course_difficulty(course_code):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        from services.course_cache import get_course_difficulty as get_cache_difficulty
        from database.db import get_db
        from database.models import Student
        
        db = get_db()
        try:
            student = db.query(Student).filter(Student.id == session['student_id']).first()
            if not student:
                return jsonify({'success': False, 'message': 'Student not found'}), 404
            
            difficulty_score, difficulty_category = get_cache_difficulty(course_code)
            
            if student.gpa < 2.5:
                difficulty_score = min(1.0, difficulty_score + 0.10)
            elif student.gpa > 3.5:
                difficulty_score = max(0.0, difficulty_score - 0.08)
            
            difficulty_score = min(1.0, max(0.0, difficulty_score))
            
            if difficulty_score < 0.4:
                difficulty_category = 'Easy'
            elif difficulty_score < 0.7:
                difficulty_category = 'Medium'
            else:
                difficulty_category = 'Hard'
            
            return jsonify({
                'success': True,
                'difficulty': {
                    'difficulty_score': float(difficulty_score),
                    'difficulty_category': difficulty_category,
                    'confidence': 0.85
                }
            })
        finally:
            db.close()
    except Exception as e:
        app_log.exception("Difficulty prediction failed")
        return jsonify({
            'success': True,
            'difficulty': {
                'difficulty_score': 0.5,
                'difficulty_category': 'Medium',
                'confidence': 0.0
            }
        })


@app.route('/api/student/academic-risk', methods=['GET'])
def get_academic_risk():
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        from services.ml_service import predict_academic_risk
        result = predict_academic_risk(session['student_id'])
        if result:
            return jsonify({'success': True, 'data': result})
        return jsonify({'success': False, 'message': 'Prediction failed'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/student/insights', methods=['GET'])
def get_path_insights():
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    try:
        from services.insights_service import get_student_insights
        data = get_student_insights(session['student_id'])
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        app_log.exception("insights failed")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/student/semester-timeline', methods=['GET'])
def get_semester_timeline_api():
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    try:
        from services.insights_service import get_semester_timeline
        data = get_semester_timeline(session['student_id'])
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/recommendations', methods=['GET'])
def get_recommendations():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        target_credits = int(request.args.get('credits', 15))
        max_courses = int(request.args.get('max_courses', 10))
        term = request.args.get('term', 'Fall')

        override_tol = None
        override_tg = None
        if request.args.get('tolerance') is not None and request.args.get('tolerance') != '':
            try:
                override_tol = float(request.args.get('tolerance'))
            except (TypeError, ValueError):
                override_tol = None
        if request.args.get('target_gpa') is not None and request.args.get('target_gpa') != '':
            try:
                override_tg = float(request.args.get('target_gpa'))
            except (TypeError, ValueError):
                override_tg = None

        include_electives = request.args.get('include_electives', '1').lower() not in ('0', 'false', 'no')
        elective_emphasis = (request.args.get('elective_emphasis') or 'balanced').strip().lower()
        if elective_emphasis not in ('major_first', 'balanced', 'include_electives'):
            elective_emphasis = 'balanced'

        override_max_hard = None
        if request.args.get('max_hard') is not None and request.args.get('max_hard') != '':
            try:
                override_max_hard = int(request.args.get('max_hard'))
            except (TypeError, ValueError):
                override_max_hard = None

        result = recommend_courses(
            session['student_id'],
            target_credits,
            max_courses,
            term,
            override_target_gpa=override_tg,
            override_tolerance=override_tol,
            include_electives=include_electives,
            elective_emphasis=elective_emphasis,
            override_max_hard=override_max_hard,
        )
        recommendations = result.get('recommendations', []) if isinstance(result, dict) else result
        
        payload = {
            'success': True,
            'recommendations': recommendations or [],
            'term': term,
        }
        if not recommendations:
            payload['message'] = 'No recommendations available. Complete prerequisites first!'
        if isinstance(result, dict):
            if result.get('semester_workload'):
                payload['semester_workload'] = result['semester_workload']
            if result.get('planning_params'):
                payload['planning_params'] = result['planning_params']
            if result.get('alternatives') is not None:
                payload['alternatives'] = result['alternatives']
        return jsonify(payload)
    except Exception as e:
        app_log.exception("Recommendations failed")
        return jsonify({'success': True, 'recommendations': [], 'message': 'Recommendations temporarily unavailable'})


@app.route('/api/semester/optimize', methods=['POST'])
def optimize_semester():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    course_codes = data.get('course_codes', [])
    if not course_codes or not isinstance(course_codes, list):
        return jsonify({'success': False, 'message': 'No courses provided. Please select courses to analyze.'}), 400
    
    db = get_db()
    try:
        from services.course_cache import get_course_by_code
        
        course_data_list = []
        missing_courses = []
        
        for course_code in course_codes:
            if not course_code or not isinstance(course_code, str):
                continue
            course_code = str(course_code).strip().upper()
            if not course_code:
                continue
            cache_course = get_course_by_code(course_code)
            if not cache_course:
                missing_courses.append(course_code)
                continue
            course_data_list.append((course_code, cache_course))
        
        if missing_courses:
            return jsonify({
                'success': False, 
                'message': f'Courses not found: {", ".join(missing_courses)}'
            }), 404
        
        if not course_data_list:
            return jsonify({'success': False, 'message': 'No valid courses to analyze'}), 400
        
        locked_plan = []
        for course_code, _cache in course_data_list:
            ok, missing = is_course_unlocked(session['student_id'], course_code)
            if not ok:
                locked_plan.append({'course_code': course_code, 'missing_prerequisites': missing})
        if locked_plan:
            return jsonify({
                'success': False,
                'message': 'Cannot analyze a semester with locked courses. Complete prerequisites first: '
                + '; '.join(
                    f"{x['course_code']} (need: {', '.join(x['missing_prerequisites'])})" for x in locked_plan
                ),
                'locked_courses': locked_plan,
                'prerequisite_error': True
            }), 400
        
        def safe_float(val, default=0.0):
            try:
                if val is None or str(val).lower() == 'nan':
                    return default
                return float(val)
            except:
                return default
        
        def safe_int(val, default=0):
            try:
                if val is None or str(val).lower() == 'nan':
                    return default
                return int(float(val))
            except:
                return default
        
        def safe_str(val, default=''):
            if val is None or str(val).lower() == 'nan':
                return default
            return str(val).strip()
        
        def safe_bool(val):
            if val is None or str(val).lower() == 'nan':
                return False
            if isinstance(val, bool):
                return val
            s = str(val).strip().lower()
            return s in ('1', 'true', 'yes', 'y', 't')
        
        course_ids = []
        for course_code, cache_course in course_data_list:
            course = db.query(Course).filter(Course.course_code == course_code).first()
            if not course:
                try:
                    course = Course(
                        course_code=safe_str(course_code),
                        subject=safe_str(cache_course.get('subject', '')),
                        number=safe_str(cache_course.get('number', '')),
                        name=safe_str(cache_course.get('name', '')),
                        description=safe_str(cache_course.get('description', '')),
                        credit_hours=safe_float(cache_course.get('credit_hours', 3.0), 3.0),
                        course_level=safe_int(cache_course.get('course_level', 100), 100),
                        course_type='',
                        is_lab=safe_bool(cache_course.get('is_lab', False)),
                        is_major_course=safe_bool(cache_course.get('is_major_course', True)),
                        prerequisite_count=safe_int(cache_course.get('prerequisite_count', 0), 0),
                        prerequisite_depth=safe_int(cache_course.get('prerequisite_depth', 0), 0),
                        graph_centrality=safe_float(cache_course.get('graph_centrality', 0.0), 0.0),
                        unlocks_count=safe_int(cache_course.get('unlocks_count', 0), 0)
                    )
                    db.add(course)
                    db.commit()
                    db.refresh(course)
                except Exception as e:
                    db.rollback()
                    app_log.exception("Failed to create course %s", course_code)
                    continue
            
            if course:
                course_ids.append(course.id)
        
        if not course_ids:
            return jsonify({'success': False, 'message': 'Failed to get course IDs for analysis'}), 500
        
        try:
            result = optimize_semester_plan(session['student_id'], course_ids)
            if not result:
                total_credits = sum([safe_float(cache_course.get('credit_hours', 3.0), 3.0) for _, cache_course in course_data_list])
                num_labs = sum([1 for _, cache_course in course_data_list if cache_course.get('is_lab', False)])
                result = {
                    'semester_difficulty': 0.5,
                    'overload_risk': min(1.0, total_credits / 18.0),
                    'total_credits': total_credits,
                    'num_courses': len(course_ids),
                    'num_labs': num_labs,
                    'difficulty_category': 'Moderate',
                    'risk_category': 'Medium'
                }
        except Exception as e:
            app_log.exception("ML semester analysis failed")
            total_credits = sum([safe_float(cache_course.get('credit_hours', 3.0), 3.0) for _, cache_course in course_data_list])
            num_labs = sum([1 for _, cache_course in course_data_list if cache_course.get('is_lab', False)])
            result = {
                'semester_difficulty': 0.5,
                'overload_risk': min(1.0, total_credits / 18.0),
                'total_credits': total_credits,
                'num_courses': len(course_ids),
                'num_labs': num_labs,
                'difficulty_category': 'Moderate',
                'risk_category': 'Medium'
            }
        
        if 'total_credits' not in result:
            result['total_credits'] = sum([safe_float(cache_course.get('credit_hours', 3.0), 3.0) for _, cache_course in course_data_list])
        if 'num_courses' not in result:
            result['num_courses'] = len(course_ids)
        if 'num_labs' not in result:
            result['num_labs'] = sum([1 for _, cache_course in course_data_list if cache_course.get('is_lab', False)])
        if 'semester_difficulty' not in result:
            result['semester_difficulty'] = 0.5
        if 'overload_risk' not in result:
            total_credits = result.get('total_credits', 15)
            result['overload_risk'] = min(1.0, total_credits / 18.0)
        if 'difficulty_category' not in result:
            result['difficulty_category'] = 'Moderate'
        if 'risk_category' not in result:
            risk = result.get('overload_risk', 0.5)
            if risk < 0.3:
                result['risk_category'] = 'Low'
            elif risk < 0.6:
                result['risk_category'] = 'Medium'
            else:
                result['risk_category'] = 'High'
        
        try:
            explanation = explain_semester_difficulty(session['student_id'], course_ids)
            result['explanation'] = explanation or f'Selected {len(course_ids)} courses totaling {result.get("total_credits", 0):.1f} credits. Analysis completed successfully.'
        except Exception as e:
            import traceback
            print(f"[WARNING] Explanation failed: {e}\n{traceback.format_exc()}")
            total_credits = result.get('total_credits', 0)
            num_courses = result.get('num_courses', len(course_ids))
            difficulty = result.get('difficulty_category', 'Moderate')
            risk = result.get('risk_category', 'Medium')
            result['explanation'] = f'Semester Analysis:\n- Total Credits: {total_credits:.1f}\n- Number of Courses: {num_courses}\n- Predicted Difficulty: {difficulty}\n- Overload Risk: {risk}\n\nAnalysis completed successfully.'
        
        db.close()
        return jsonify({'success': True, 'analysis': result})
    except Exception as e:
        app_log.exception("Semester optimize failed")
        db.close()
        
        try:
            from services.course_cache import get_course_by_code
            total_credits = 0
            num_courses = len(course_codes) if course_codes else 0
            for code in course_codes:
                if code:
                    course = get_course_by_code(str(code).strip().upper())
                    if course:
                        total_credits += float(course.get('credit_hours', 3.0) or 3.0)
            
            return jsonify({
                'success': True,
                'analysis': {
                    'semester_difficulty': 0.5,
                    'overload_risk': min(1.0, total_credits / 18.0),
                    'total_credits': total_credits,
                    'num_courses': num_courses,
                    'num_labs': 0,
                    'difficulty_category': 'Moderate',
                    'risk_category': 'Medium',
                    'explanation': f'Basic analysis: {num_courses} courses totaling {total_credits:.1f} credits. Full analysis temporarily unavailable.'
                }
            })
        except:
            return jsonify({
                'success': False, 
                'message': f'Error analyzing semester: {str(e)}. Please try again with different courses.'
            }), 500


@app.route('/api/advisor/chat', methods=['POST'])
def chat():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    question = data.get('question', '')
    
    if not question or not question.strip():
        return jsonify({'success': False, 'message': 'Question cannot be empty'}), 400
    
    try:
        response = chatbot_response(session['student_id'], question)
        if not response:
            response = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        app_log.exception("Chatbot error")
        return jsonify({
            'success': True, 
            'response': f"I encountered an error: {str(e)}. Please try again or rephrase your question."
        }), 200


@app.route('/api/advisor/bottlenecks', methods=['GET'])
def get_bottlenecks():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        bottlenecks = get_bottleneck_courses(session['student_id'])
        return jsonify({'success': True, 'bottlenecks': bottlenecks})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/courses/<course_code>/rate', methods=['POST'])
def rate_course(course_code):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    data = request.json or {}
    rating = data.get('rating')
    try:
        rating = int(rating)
        if not (1 <= rating <= 5):
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5'}), 400
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Invalid rating'}), 400
    db = get_db()
    try:
        course = db.query(Course).filter(Course.course_code == course_code.strip().upper()).first()
        if not course:
            from services.course_cache import get_course_by_code
            co = get_course_by_code(course_code.strip().upper())
            if not co:
                return jsonify({'success': False, 'message': 'Course not found'}), 404
            course = Course(
                course_code=course_code.strip().upper(),
                subject=str(co.get('subject', '')),
                number=str(co.get('number', '')),
                name=str(co.get('name', '')),
                credit_hours=float(co.get('credit_hours', 3.0) or 3.0),
                course_level=int(co.get('course_level', 100) or 100),
                is_major_course=bool(co.get('is_major_course', True))
            )
            db.add(course)
            db.commit()
            db.refresh(course)
        existing = db.query(CourseRating).filter(
            CourseRating.student_id == session['student_id'],
            CourseRating.course_id == course.id
        ).first()
        if existing:
            existing.rating = rating
        else:
            db.add(CourseRating(student_id=session['student_id'], course_id=course.id, rating=rating))
        db.commit()
        return jsonify({'success': True, 'message': 'Rating saved', 'rating': rating})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/courses/<course_code>/ratings', methods=['GET'])
def get_course_ratings(course_code):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    db = get_db()
    try:
        course = db.query(Course).filter(Course.course_code == course_code.strip().upper()).first()
        if not course:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        from sqlalchemy import func
        agg = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)).filter(
            CourseRating.course_id == course.id
        ).first()
        user_rating = db.query(CourseRating.rating).filter(
            CourseRating.student_id == session['student_id'],
            CourseRating.course_id == course.id
        ).first()
        average = float(agg[0]) if agg and agg[0] is not None else None
        count = int(agg[1] or 0)
        return jsonify({
            'success': True,
            'average': round(average, 1) if average is not None else None,
            'count': count,
            'user_rating': int(user_rating[0]) if user_rating and user_rating[0] is not None else None
        })
    finally:
        db.close()


@app.route('/api/courses/ratings/batch', methods=['GET'])
def get_course_ratings_batch():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    raw = request.args.get('course_codes', '')
    codes = [x.strip().upper() for x in raw.split(',') if x.strip()][:50]
    if not codes:
        return jsonify({'success': True, 'ratings': {}})
    db = get_db()
    try:
        courses = db.query(Course).filter(Course.course_code.in_(codes)).all()
        cid_to_code = {c.id: c.course_code for c in courses}
        if not cid_to_code:
            return jsonify({'success': True, 'ratings': {}})
        from sqlalchemy import func
        agg = db.query(CourseRating.course_id, func.avg(CourseRating.rating), func.count(CourseRating.id)).filter(
            CourseRating.course_id.in_(cid_to_code.keys())
        ).group_by(CourseRating.course_id).all()
        user_ratings = db.query(CourseRating.course_id, CourseRating.rating).filter(
            CourseRating.student_id == session['student_id'],
            CourseRating.course_id.in_(cid_to_code.keys())
        ).all()
        result = {}
        for cid, avg, cnt in agg:
            code = cid_to_code.get(cid)
            if code:
                result[code] = {'average': round(float(avg), 1), 'count': int(cnt), 'user_rating': None}
        for cid, r in user_ratings:
            code = cid_to_code.get(cid)
            if code and code in result:
                result[code]['user_rating'] = int(r)
        return jsonify({'success': True, 'ratings': result})
    finally:
        db.close()


@app.route('/api/courses/<course_code>/explain', methods=['GET'])
def explain_course(course_code):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    try:
        is_unlocked, missing = is_course_unlocked(session['student_id'], course_code)
        explanation = explain_course_lock(session['student_id'], course_code)
        
        return jsonify({
            'success': True,
            'is_unlocked': is_unlocked,
            'missing_prerequisites': missing,
            'explanation': explanation
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/majors', methods=['GET'])
def get_majors():
    
    import json
    from pathlib import Path
    
    majors_file_data = Path(__file__).parent / 'Data' / 'majors.json'
    majors_file_static = Path(__file__).parent / 'static' / 'majors.json'
    
    majors_file = majors_file_data if majors_file_data.exists() else majors_file_static
    
    try:
        with open(majors_file, 'r') as f:
            majors = json.load(f)
        
        return jsonify({'success': True, 'majors': majors})
    except Exception as e:
        try:
            import pandas as pd
            df = pd.read_csv(Path(__file__).parent / 'Data' / 'merged_courses.csv')
            majors = sorted(df['subject'].dropna().unique())
            majors_list = [{'code': m, 'name': m, 'display': m} for m in majors]
            return jsonify({'success': True, 'majors': majors_list})
        except:
            return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/gpa/what-if', methods=['POST'])
def gpa_what_if():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    data = request.json or {}
    target_gpa = float(data.get('target_gpa', 3.0))
    course_codes = data.get('course_codes', [])
    if not isinstance(course_codes, list):
        course_codes = []
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        from services.course_cache import get_course_by_code
        total_credits_done = 0.0
        total_points_done = 0.0
        for sc in db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all():
            c = db.query(Course).filter(Course.id == sc.course_id).first()
            if c and sc.grade_points is not None:
                total_credits_done += float(c.credit_hours)
                total_points_done += sc.grade_points * float(c.credit_hours)
        semester_credits = 0.0
        for code in course_codes:
            if not code:
                continue
            co = get_course_by_code(str(code).strip().upper())
            if co:
                semester_credits += float(co.get('credit_hours', 3.0) or 3.0)
        if semester_credits <= 0:
            return jsonify({
                'success': True,
                'current_gpa': round(float(student.gpa), 2),
                'current_credits': round(total_credits_done, 1),
                'target_gpa': target_gpa,
                'semester_credits': 0,
                'required_gpa_this_semester': None,
                'message': 'Add courses to your semester plan to see required GPA.'
            })
        needed_points = target_gpa * (total_credits_done + semester_credits) - total_points_done
        required_gpa = needed_points / semester_credits
        achievable = 0.0 <= required_gpa <= 4.0
        return jsonify({
            'success': True,
            'current_gpa': round(float(student.gpa), 2),
            'current_credits': round(total_credits_done, 1),
            'target_gpa': target_gpa,
            'semester_credits': round(semester_credits, 1),
            'required_gpa_this_semester': round(required_gpa, 2) if achievable else None,
            'achievable': achievable,
            'message': f'You need a {required_gpa:.2f} GPA this semester to reach {target_gpa} overall.' if achievable else f'To reach {target_gpa} overall you would need {required_gpa:.2f} this semester (not possible; max 4.0).'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/gpa/simulate', methods=['POST'])
def gpa_simulate():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    data = request.json or {}
    courses = data.get('courses', [])
    if not isinstance(courses, list):
        courses = []
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        total_credits = 0.0
        total_points = 0.0
        for sc in db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all():
            c = db.query(Course).filter(Course.id == sc.course_id).first()
            if c and sc.grade_points is not None:
                total_credits += float(c.credit_hours)
                total_points += sc.grade_points * float(c.credit_hours)
        from services.course_cache import get_course_by_code
        for item in courses:
            code = item.get('course_code') or item.get('courseCode')
            grade = item.get('grade', '')
            if not code:
                continue
            co = get_course_by_code(str(code).strip().upper())
            if not co:
                continue
            cred = float(co.get('credit_hours', 3.0) or 3.0)
            pts = GRADE_POINTS.get(grade, 0.0)
            total_credits += cred
            total_points += pts * cred
        new_gpa = (total_points / total_credits) if total_credits > 0 else 0.0
        return jsonify({
            'success': True,
            'simulated_gpa': round(new_gpa, 2),
            'total_credits': round(total_credits, 1),
            'message': f'With these grades your GPA would be {new_gpa:.2f}.'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    
    db = get_db()
    try:
        from sqlalchemy import func
        total_students = db.query(Student).count()
        total_courses = db.query(Course).count()
        taken = db.query(Course.course_code, func.count(StudentCourse.id).label('cnt')).join(
            StudentCourse, StudentCourse.course_id == Course.id
        ).filter(StudentCourse.status == 'completed').group_by(Course.id).order_by(func.count(StudentCourse.id).desc()).limit(10).all()
        most_taken = [{'course_code': r[0], 'count': r[1]} for r in taken]
        rating_agg = db.query(func.avg(CourseRating.rating), func.count(CourseRating.id)).first()
        avg_rating = float(rating_agg[0]) if rating_agg and rating_agg[0] else None
        total_ratings = int(rating_agg[1] or 0)
        return jsonify({
            'success': True,
            'total_students': total_students,
            'total_courses': total_courses,
            'most_taken_courses': most_taken,
            'average_difficulty_rating': round(avg_rating, 1) if avg_rating is not None else None,
            'total_ratings': total_ratings
        })
    finally:
        db.close()


@app.route('/api/admin/courses', methods=['GET'])
@admin_required
def admin_courses_list():
    
    page = max(1, int(request.args.get('page', 1)))
    per_page = min(50, max(5, int(request.args.get('per_page', 20))))
    q = (request.args.get('q') or '').strip()
    db = get_db()
    try:
        query = db.query(Course)
        if q:
            query = query.filter(
                (Course.course_code.ilike('%' + q + '%')) |
                (Course.name.ilike('%' + q + '%')) |
                (Course.subject.ilike('%' + q + '%'))
            )
        total = query.count()
        courses = query.order_by(Course.course_code).offset((page - 1) * per_page).limit(per_page).all()
        items = [{
            'id': c.id,
            'course_code': c.course_code,
            'subject': c.subject,
            'number': c.number,
            'name': c.name or '',
            'credit_hours': float(c.credit_hours or 0),
            'course_level': c.course_level,
            'is_major_course': bool(c.is_major_course),
        } for c in courses]
        return jsonify({'success': True, 'courses': items, 'total': total, 'page': page, 'per_page': per_page})
    finally:
        db.close()


@app.route('/api/admin/courses/<int:course_id>', methods=['PUT'])
@admin_required
def admin_course_update(course_id):
    
    data = request.json or {}
    db = get_db()
    try:
        course = db.query(Course).filter(Course.id == course_id).first()
        if not course:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        if 'name' in data and data['name'] is not None:
            course.name = str(data['name']).strip()[:200]
        if 'credit_hours' in data and data['credit_hours'] is not None:
            try:
                course.credit_hours = float(data['credit_hours'])
            except (TypeError, ValueError):
                pass
        if 'course_level' in data and data['course_level'] is not None:
            try:
                course.course_level = int(data['course_level'])
            except (TypeError, ValueError):
                pass
        if 'is_major_course' in data:
            course.is_major_course = bool(data['is_major_course'])
        db.commit()
        return jsonify({'success': True, 'message': 'Course updated'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/admin/majors', methods=['GET'])
@admin_required
def admin_majors_list():
    
    from pathlib import Path
    majors_file = Path(__file__).parent / 'Data' / 'majors.json'
    if not majors_file.exists():
        majors_file = Path(__file__).parent / 'static' / 'majors.json'
    try:
        with open(majors_file, 'r') as f:
            majors = json.load(f)
        return jsonify({'success': True, 'majors': majors})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/prerequisite-graph', methods=['GET'])
def prerequisite_graph_api():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        major = student.major if student else None
        priority_codes = set()
        raw = request.args.get('plan_codes', '') or ''
        for part in raw.replace(';', ',').split(','):
            p = part.strip().upper()
            if p:
                priority_codes.add(p)
        data = build_prerequisite_graph(
            session['student_id'],
            major=major,
            priority_course_codes=priority_codes if priority_codes else None,
        )
        return jsonify({'success': True, 'graph': data})
    except Exception as e:
        app_log.exception("Prerequisite graph failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


def _get_plan_courses_for_export(student_id, course_codes):
    
    from services.course_cache import get_course_by_code, get_course_difficulty
    rows = []
    for code in (course_codes or []):
        if not code:
            continue
        code = str(code).strip().upper()
        co = get_course_by_code(code)
        if not co:
            continue
        cred = float(co.get('credit_hours', 3.0) or 3.0)
        diff_score, diff_cat = get_course_difficulty(code)
        rows.append({
            'course_code': code,
            'name': (co.get('name') or code),
            'credit_hours': cred,
            'difficulty': diff_cat,
        })
    return rows


@app.route('/api/export/plan/csv', methods=['GET', 'POST'])
def export_plan_csv():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    if request.method == 'POST' and request.json:
        course_codes = request.json.get('course_codes', [])
    else:
        raw = request.args.get('course_codes', '')
        course_codes = [x.strip() for x in raw.split(',') if x.strip()]
    courses = _get_plan_courses_for_export(session['student_id'], course_codes)
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        username = (student.username or 'Student') if student else 'Student'
    finally:
        db.close()
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(['Smart Academic Planning - Semester Plan Export'])
    w.writerow(['Student', username])
    w.writerow([])
    w.writerow(['Course Code', 'Course Name', 'Credits', 'Difficulty'])
    for r in courses:
        w.writerow([r['course_code'], r['name'], r['credit_hours'], r['difficulty']])
    w.writerow([])
    w.writerow(['Total Credits', sum(c['credit_hours'] for c in courses)])
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='semester_plan.csv'
    )


@app.route('/api/export/plan/pdf', methods=['GET', 'POST'])
def export_plan_pdf():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    if request.method == 'POST' and request.json:
        course_codes = request.json.get('course_codes', [])
    else:
        raw = request.args.get('course_codes', '')
        course_codes = [x.strip() for x in raw.split(',') if x.strip()]
    courses = _get_plan_courses_for_export(session['student_id'], course_codes)
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        username = (student.username or 'Student') if student else 'Student'
        gpa = float(student.gpa) if student else 0.0
    finally:
        db.close()
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
        styles = getSampleStyleSheet()
        story = []
        story.append(Paragraph('Smart Academic Planning - Semester Plan', styles['Title']))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f'Student: {username} &nbsp;&nbsp; GPA: {gpa:.2f}', styles['Normal']))
        story.append(Spacer(1, 20))
        if not courses:
            story.append(Paragraph('No courses in plan.', styles['Normal']))
        else:
            data = [['Course Code', 'Course Name', 'Credits', 'Difficulty']]
            for r in courses:
                data.append([r['course_code'], r['name'][:50], str(r['credit_hours']), r['difficulty']])
            data.append(['', 'Total', str(round(sum(c["credit_hours"] for c in courses), 1)), ''])
            t = Table(data, colWidths=[1.2*inch, 3.5*inch, 0.8*inch, 1*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E7E6E6')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            story.append(t)
        doc.build(story)
        buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name='semester_plan.pdf')
    except ImportError:
        return jsonify({'success': False, 'message': 'PDF export requires reportlab. Install: pip install reportlab'}), 501



@app.route('/api/calendar/events', methods=['GET'])
def get_calendar_events():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = db.query(AcademicCalendarEvent).filter(
            AcademicCalendarEvent.student_id == session['student_id']
        )
        
        if start_date:
            try:
                from datetime import datetime
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(AcademicCalendarEvent.start_date >= start)
            except:
                pass
        
        if end_date:
            try:
                from datetime import datetime
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(AcademicCalendarEvent.start_date <= end)
            except:
                pass
        
        events = query.order_by(AcademicCalendarEvent.start_date).all()
        
        return jsonify({
            'success': True,
            'events': [{
                'id': e.id,
                'title': e.title,
                'description': e.description,
                'event_type': e.event_type,
                'start_date': e.start_date.isoformat() if e.start_date else None,
                'end_date': e.end_date.isoformat() if e.end_date else None,
                'is_all_day': e.is_all_day,
                'color': e.color,
                'reminder_days': e.reminder_days,
                'is_completed': e.is_completed
            } for e in events]
        })
    except Exception as e:
        app_log.exception("Get calendar events failed")
        return jsonify({'success': False, 'message': f'Failed to load calendar events: {str(e)}'}), 500
    finally:
        db.close()


@app.route('/api/calendar/events', methods=['POST'])
def create_calendar_event():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        
        start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')) if data.get('start_date') else datetime.utcnow()
        end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')) if data.get('end_date') else None
        
        event = AcademicCalendarEvent(
            student_id=session['student_id'],
            title=data.get('title', 'Untitled Event'),
            description=data.get('description'),
            event_type=data.get('event_type', 'other'),
            start_date=start_date,
            end_date=end_date,
            is_all_day=data.get('is_all_day', True),
            color=data.get('color', '#3788d8'),
            reminder_days=data.get('reminder_days', 0),
            is_completed=data.get('is_completed', False)
        )
        
        db.add(event)
        db.commit()
        db.refresh(event)
        
        return jsonify({
            'success': True,
            'message': 'Event created successfully',
            'event': {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'event_type': event.event_type,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'end_date': event.end_date.isoformat() if event.end_date else None,
                'is_all_day': event.is_all_day,
                'color': event.color,
                'reminder_days': event.reminder_days,
                'is_completed': event.is_completed
            }
        })
    except Exception as e:
        db.rollback()
        app_log.exception("Create calendar event failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/calendar/events/<int:event_id>', methods=['PUT'])
def update_calendar_event(event_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    
    try:
        event = db.query(AcademicCalendarEvent).filter(
            AcademicCalendarEvent.id == event_id,
            AcademicCalendarEvent.student_id == session['student_id']
        ).first()
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        from datetime import datetime
        
        if 'title' in data:
            event.title = data['title']
        if 'description' in data:
            event.description = data['description']
        if 'event_type' in data:
            event.event_type = data['event_type']
        if 'start_date' in data:
            event.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
        if 'end_date' in data:
            event.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')) if data['end_date'] else None
        if 'is_all_day' in data:
            event.is_all_day = data['is_all_day']
        if 'color' in data:
            event.color = data['color']
        if 'reminder_days' in data:
            event.reminder_days = data['reminder_days']
        if 'is_completed' in data:
            event.is_completed = data['is_completed']
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Event updated successfully',
            'event': {
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'event_type': event.event_type,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'end_date': event.end_date.isoformat() if event.end_date else None,
                'is_all_day': event.is_all_day,
                'color': event.color,
                'reminder_days': event.reminder_days,
                'is_completed': event.is_completed
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/calendar/events/<int:event_id>', methods=['DELETE'])
def delete_calendar_event(event_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    
    try:
        event = db.query(AcademicCalendarEvent).filter(
            AcademicCalendarEvent.id == event_id,
            AcademicCalendarEvent.student_id == session['student_id']
        ).first()
        
        if not event:
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        db.delete(event)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Event deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()



@app.route('/api/financial/records', methods=['GET'])
def get_financial_records():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        semester = request.args.get('semester')
        
        query = db.query(FinancialRecord).filter(
            FinancialRecord.student_id == session['student_id']
        )
        
        if semester:
            query = query.filter(FinancialRecord.semester == semester)
        
        records = query.order_by(FinancialRecord.due_date.desc() if FinancialRecord.due_date else FinancialRecord.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'records': [{
                'id': r.id,
                'record_type': r.record_type,
                'title': r.title,
                'description': r.description,
                'amount': float(r.amount),
                'semester': r.semester,
                'due_date': r.due_date.isoformat() if r.due_date else None,
                'is_paid': r.is_paid,
                'paid_date': r.paid_date.isoformat() if r.paid_date else None,
                'category': r.category
            } for r in records]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/records', methods=['POST'])
def create_financial_record():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        
        due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')) if data.get('due_date') else None
        paid_date = datetime.fromisoformat(data['paid_date'].replace('Z', '+00:00')) if data.get('paid_date') else None
        
        record = FinancialRecord(
            student_id=session['student_id'],
            record_type=data.get('record_type', 'expense'),
            title=data.get('title', 'Untitled'),
            description=data.get('description'),
            amount=float(data.get('amount', 0)),
            semester=data.get('semester'),
            due_date=due_date,
            is_paid=data.get('is_paid', False),
            paid_date=paid_date,
            category=data.get('category', 'other')
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return jsonify({
            'success': True,
            'message': 'Financial record created successfully',
            'record': {
                'id': record.id,
                'record_type': record.record_type,
                'title': record.title,
                'description': record.description,
                'amount': float(record.amount),
                'semester': record.semester,
                'due_date': record.due_date.isoformat() if record.due_date else None,
                'is_paid': record.is_paid,
                'paid_date': record.paid_date.isoformat() if record.paid_date else None,
                'category': record.category
            }
        })
    except Exception as e:
        db.rollback()
        app_log.exception("Create financial record failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/records/<int:record_id>', methods=['PUT'])
def update_financial_record(record_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    
    try:
        record = db.query(FinancialRecord).filter(
            FinancialRecord.id == record_id,
            FinancialRecord.student_id == session['student_id']
        ).first()
        
        if not record:
            return jsonify({'success': False, 'message': 'Record not found'}), 404
        
        from datetime import datetime
        
        if 'record_type' in data:
            record.record_type = data['record_type']
        if 'title' in data:
            record.title = data['title']
        if 'description' in data:
            record.description = data['description']
        if 'amount' in data:
            record.amount = float(data['amount'])
        if 'semester' in data:
            record.semester = data['semester']
        if 'due_date' in data:
            record.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')) if data['due_date'] else None
        if 'is_paid' in data:
            record.is_paid = data['is_paid']
            if data['is_paid'] and not record.paid_date:
                record.paid_date = datetime.utcnow()
        if 'paid_date' in data:
            record.paid_date = datetime.fromisoformat(data['paid_date'].replace('Z', '+00:00')) if data['paid_date'] else None
        if 'category' in data:
            record.category = data['category']
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Record updated successfully',
            'record': {
                'id': record.id,
                'record_type': record.record_type,
                'title': record.title,
                'description': record.description,
                'amount': float(record.amount),
                'semester': record.semester,
                'due_date': record.due_date.isoformat() if record.due_date else None,
                'is_paid': record.is_paid,
                'paid_date': record.paid_date.isoformat() if record.paid_date else None,
                'category': record.category
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/records/<int:record_id>', methods=['DELETE'])
def delete_financial_record(record_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    
    try:
        record = db.query(FinancialRecord).filter(
            FinancialRecord.id == record_id,
            FinancialRecord.student_id == session['student_id']
        ).first()
        
        if not record:
            return jsonify({'success': False, 'message': 'Record not found'}), 404
        
        db.delete(record)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Record deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/summary', methods=['GET'])
def get_financial_summary():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        semester = request.args.get('semester')
        
        query = db.query(FinancialRecord).filter(
            FinancialRecord.student_id == session['student_id']
        )
        
        if semester:
            query = query.filter(FinancialRecord.semester == semester)
        
        records = query.all()
        
        total_income = sum([r.amount for r in records if r.amount > 0])
        total_expenses = sum([abs(r.amount) for r in records if r.amount < 0])
        net_balance = total_income - total_expenses
        
        unpaid_expenses = sum([abs(r.amount) for r in records if r.amount < 0 and not r.is_paid])
        
        category_totals = {}
        for r in records:
            cat = r.category or 'other'
            if cat not in category_totals:
                category_totals[cat] = {'income': 0, 'expenses': 0}
            if r.amount > 0:
                category_totals[cat]['income'] += r.amount
            else:
                category_totals[cat]['expenses'] += abs(r.amount)
        
        return jsonify({
            'success': True,
            'summary': {
                'total_income': float(total_income),
                'total_expenses': float(total_expenses),
                'net_balance': float(net_balance),
                'unpaid_expenses': float(unpaid_expenses),
                'category_totals': category_totals
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/tuition-calculator', methods=['POST'])
def calculate_tuition():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        credits = float(data.get('credits', 0))
        cost_per_credit = float(data.get('cost_per_credit', 500))
        semester = data.get('semester', 'Fall 2024')
        
        base_tuition = credits * cost_per_credit
        fees = float(data.get('fees', 500))
        total = base_tuition + fees
        
        if data.get('save_record', False):
            from datetime import datetime
            record = FinancialRecord(
                student_id=session['student_id'],
                record_type='tuition',
                title=f'Tuition - {semester}',
                description=f'{credits} credits @ ${cost_per_credit}/credit + ${fees} fees',
                amount=-total,
                semester=semester,
                category='tuition',
                is_paid=False
            )
            db.add(record)
            db.commit()
        
        return jsonify({
            'success': True,
            'calculation': {
                'credits': credits,
                'cost_per_credit': cost_per_credit,
                'base_tuition': float(base_tuition),
                'fees': fees,
                'total': float(total),
                'semester': semester
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/scholarships', methods=['GET'])
def get_scholarships():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        scholarships = db.query(Scholarship).filter(
            Scholarship.student_id == session['student_id']
        ).order_by(Scholarship.application_deadline.desc()).all()
        
        return jsonify({
            'success': True,
            'scholarships': [{
                'id': s.id,
                'name': s.name,
                'description': s.description,
                'amount': float(s.amount),
                'eligibility_gpa_min': float(s.eligibility_gpa_min) if s.eligibility_gpa_min else None,
                'eligibility_credits_min': s.eligibility_credits_min,
                'eligibility_major': s.eligibility_major,
                'application_deadline': s.application_deadline.isoformat() if s.application_deadline else None,
                'is_applied': s.is_applied,
                'is_awarded': s.is_awarded,
                'awarded_date': s.awarded_date.isoformat() if s.awarded_date else None,
                'renewal_required': s.renewal_required,
                'renewal_gpa_min': float(s.renewal_gpa_min) if s.renewal_gpa_min else None
            } for s in scholarships]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/scholarships', methods=['POST'])
def create_scholarship():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        
        application_deadline = datetime.fromisoformat(data['application_deadline'].replace('Z', '+00:00')) if data.get('application_deadline') else None
        awarded_date = datetime.fromisoformat(data['awarded_date'].replace('Z', '+00:00')) if data.get('awarded_date') else None
        
        scholarship = Scholarship(
            student_id=session['student_id'],
            name=data.get('name', 'Untitled Scholarship'),
            description=data.get('description'),
            amount=float(data.get('amount', 0)),
            eligibility_gpa_min=float(data['eligibility_gpa_min']) if data.get('eligibility_gpa_min') else None,
            eligibility_credits_min=int(data['eligibility_credits_min']) if data.get('eligibility_credits_min') else None,
            eligibility_major=data.get('eligibility_major'),
            application_deadline=application_deadline,
            is_applied=data.get('is_applied', False),
            is_awarded=data.get('is_awarded', False),
            awarded_date=awarded_date,
            renewal_required=data.get('renewal_required', False),
            renewal_gpa_min=float(data['renewal_gpa_min']) if data.get('renewal_gpa_min') else None
        )
        
        db.add(scholarship)
        db.commit()
        db.refresh(scholarship)
        
        return jsonify({
            'success': True,
            'message': 'Scholarship created successfully',
            'scholarship': {
                'id': scholarship.id,
                'name': scholarship.name,
                'description': scholarship.description,
                'amount': float(scholarship.amount),
                'eligibility_gpa_min': float(scholarship.eligibility_gpa_min) if scholarship.eligibility_gpa_min else None,
                'eligibility_credits_min': scholarship.eligibility_credits_min,
                'eligibility_major': scholarship.eligibility_major,
                'application_deadline': scholarship.application_deadline.isoformat() if scholarship.application_deadline else None,
                'is_applied': scholarship.is_applied,
                'is_awarded': scholarship.is_awarded,
                'awarded_date': scholarship.awarded_date.isoformat() if scholarship.awarded_date else None,
                'renewal_required': scholarship.renewal_required,
                'renewal_gpa_min': float(scholarship.renewal_gpa_min) if scholarship.renewal_gpa_min else None
            }
        })
    except Exception as e:
        db.rollback()
        app_log.exception("Create scholarship failed")
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/scholarships/<int:scholarship_id>', methods=['PUT'])
def update_scholarship(scholarship_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    
    try:
        scholarship = db.query(Scholarship).filter(
            Scholarship.id == scholarship_id,
            Scholarship.student_id == session['student_id']
        ).first()
        
        if not scholarship:
            return jsonify({'success': False, 'message': 'Scholarship not found'}), 404
        
        from datetime import datetime
        
        if 'name' in data:
            scholarship.name = data['name']
        if 'description' in data:
            scholarship.description = data['description']
        if 'amount' in data:
            scholarship.amount = float(data['amount'])
        if 'eligibility_gpa_min' in data:
            scholarship.eligibility_gpa_min = float(data['eligibility_gpa_min']) if data['eligibility_gpa_min'] else None
        if 'eligibility_credits_min' in data:
            scholarship.eligibility_credits_min = int(data['eligibility_credits_min']) if data.get('eligibility_credits_min') else None
        if 'eligibility_major' in data:
            scholarship.eligibility_major = data['eligibility_major']
        if 'application_deadline' in data:
            scholarship.application_deadline = datetime.fromisoformat(data['application_deadline'].replace('Z', '+00:00')) if data['application_deadline'] else None
        if 'is_applied' in data:
            scholarship.is_applied = data['is_applied']
        if 'is_awarded' in data:
            scholarship.is_awarded = data['is_awarded']
            if data['is_awarded'] and not scholarship.awarded_date:
                scholarship.awarded_date = datetime.utcnow()
        if 'awarded_date' in data:
            scholarship.awarded_date = datetime.fromisoformat(data['awarded_date'].replace('Z', '+00:00')) if data['awarded_date'] else None
        if 'renewal_required' in data:
            scholarship.renewal_required = data['renewal_required']
        if 'renewal_gpa_min' in data:
            scholarship.renewal_gpa_min = float(data['renewal_gpa_min']) if data.get('renewal_gpa_min') else None
        
        db.commit()
        
        return jsonify({
            'success': True,
            'message': 'Scholarship updated successfully',
            'scholarship': {
                'id': scholarship.id,
                'name': scholarship.name,
                'description': scholarship.description,
                'amount': float(scholarship.amount),
                'eligibility_gpa_min': float(scholarship.eligibility_gpa_min) if scholarship.eligibility_gpa_min else None,
                'eligibility_credits_min': scholarship.eligibility_credits_min,
                'eligibility_major': scholarship.eligibility_major,
                'application_deadline': scholarship.application_deadline.isoformat() if scholarship.application_deadline else None,
                'is_applied': scholarship.is_applied,
                'is_awarded': scholarship.is_awarded,
                'awarded_date': scholarship.awarded_date.isoformat() if scholarship.awarded_date else None,
                'renewal_required': scholarship.renewal_required,
                'renewal_gpa_min': float(scholarship.renewal_gpa_min) if scholarship.renewal_gpa_min else None
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/scholarships/<int:scholarship_id>', methods=['DELETE'])
def delete_scholarship(scholarship_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    
    try:
        scholarship = db.query(Scholarship).filter(
            Scholarship.id == scholarship_id,
            Scholarship.student_id == session['student_id']
        ).first()
        
        if not scholarship:
            return jsonify({'success': False, 'message': 'Scholarship not found'}), 404
        
        db.delete(scholarship)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Scholarship deleted successfully'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/financial/scholarships/check-eligibility', methods=['GET'])
def check_scholarship_eligibility():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == session['student_id']).first()
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        from database.models import StudentCourse
        completed_count = db.query(StudentCourse).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).count()
        
        total_credits = 0.0
        completed_courses = db.query(StudentCourse, Course).join(
            Course, StudentCourse.course_id == Course.id
        ).filter(
            StudentCourse.student_id == session['student_id'],
            StudentCourse.status == 'completed'
        ).all()
        
        for sc, course in completed_courses:
            total_credits += float(course.credit_hours or 0)
        
        scholarships = db.query(Scholarship).filter(
            Scholarship.student_id == session['student_id']
        ).all()
        
        eligibility_results = []
        for s in scholarships:
            eligible = True
            reasons = []
            
            if s.eligibility_gpa_min and student.gpa < s.eligibility_gpa_min:
                eligible = False
                reasons.append(f'GPA {student.gpa:.2f} below required {s.eligibility_gpa_min:.2f}')
            
            if s.eligibility_credits_min and total_credits < s.eligibility_credits_min:
                eligible = False
                reasons.append(f'Credits {total_credits:.1f} below required {s.eligibility_credits_min}')
            
            if s.eligibility_major and student.major.upper() != s.eligibility_major.upper():
                eligible = False
                reasons.append(f'Major {student.major} does not match required {s.eligibility_major}')
            
            eligibility_results.append({
                'scholarship_id': s.id,
                'scholarship_name': s.name,
                'eligible': eligible,
                'reasons': reasons,
                'student_gpa': float(student.gpa),
                'student_credits': float(total_credits),
                'student_major': student.major
            })
        
        return jsonify({
            'success': True,
            'eligibility': eligibility_results
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/sessions', methods=['GET'])
def get_study_sessions():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        course_id = request.args.get('course_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        query = db.query(StudySession).filter(StudySession.student_id == session['student_id'])
        
        if course_id:
            query = query.filter(StudySession.course_id == course_id)
        if start_date:
            query = query.filter(StudySession.date >= start_date)
        if end_date:
            query = query.filter(StudySession.date <= end_date)
        
        sessions = query.order_by(StudySession.date.desc()).all()
        
        return jsonify({
            'success': True,
            'sessions': [{
                'id': s.id,
                'course_id': s.course_id,
                'course_code': s.course.course_code if s.course else None,
                'course_name': s.course.name if s.course else None,
                'date': s.date.isoformat() if s.date else None,
                'duration_minutes': s.duration_minutes,
                'notes': s.notes,
                'created_at': s.created_at.isoformat() if s.created_at else None
            } for s in sessions]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/sessions', methods=['POST'])
def create_study_session():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        course_id = data.get('course_id')
        if not course_id:
            return jsonify({'success': False, 'message': 'Course ID required'}), 400
        
        session_obj = StudySession(
            student_id=session['student_id'],
            course_id=course_id,
            date=datetime.fromisoformat(data['date'].replace('Z', '+00:00')) if data.get('date') else datetime.utcnow(),
            duration_minutes=data.get('duration_minutes', 0),
            notes=data.get('notes', '')
        )
        
        db.add(session_obj)
        db.commit()
        
        return jsonify({
            'success': True,
            'session': {
                'id': session_obj.id,
                'course_id': session_obj.course_id,
                'date': session_obj.date.isoformat() if session_obj.date else None,
                'duration_minutes': session_obj.duration_minutes,
                'notes': session_obj.notes
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/sessions/<int:session_id>', methods=['DELETE'])
def delete_study_session(session_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        session_obj = db.query(StudySession).filter(
            StudySession.id == session_id,
            StudySession.student_id == session['student_id']
        ).first()
        
        if not session_obj:
            return jsonify({'success': False, 'message': 'Session not found'}), 404
        
        db.delete(session_obj)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Session deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/goals', methods=['GET'])
def get_study_goals():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        goals = db.query(StudyGoal).filter(
            StudyGoal.student_id == session['student_id']
        ).order_by(StudyGoal.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'goals': [{
                'id': g.id,
                'course_id': g.course_id,
                'course_code': g.course.course_code if g.course else None,
                'goal_type': g.goal_type,
                'target_hours_per_week': g.target_hours_per_week,
                'target_hours_total': g.target_hours_total,
                'start_date': g.start_date.isoformat() if g.start_date else None,
                'end_date': g.end_date.isoformat() if g.end_date else None,
                'is_active': g.is_active
            } for g in goals]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/goals', methods=['POST'])
def create_study_goal():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        goal = StudyGoal(
            student_id=session['student_id'],
            course_id=data.get('course_id'),
            goal_type=data.get('goal_type', 'weekly'),
            target_hours_per_week=data.get('target_hours_per_week', 0.0),
            target_hours_total=data.get('target_hours_total', 0.0),
            start_date=datetime.fromisoformat(data['start_date'].replace('Z', '+00:00')) if data.get('start_date') else None,
            end_date=datetime.fromisoformat(data['end_date'].replace('Z', '+00:00')) if data.get('end_date') else None,
            is_active=data.get('is_active', True)
        )
        
        db.add(goal)
        db.commit()
        
        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'course_id': goal.course_id,
                'goal_type': goal.goal_type,
                'target_hours_per_week': goal.target_hours_per_week,
                'target_hours_total': goal.target_hours_total,
                'is_active': goal.is_active
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/goals/<int:goal_id>', methods=['PUT'])
def update_study_goal(goal_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        goal = db.query(StudyGoal).filter(
            StudyGoal.id == goal_id,
            StudyGoal.student_id == session['student_id']
        ).first()
        
        if not goal:
            return jsonify({'success': False, 'message': 'Goal not found'}), 404
        
        if 'target_hours_per_week' in data:
            goal.target_hours_per_week = data['target_hours_per_week']
        if 'target_hours_total' in data:
            goal.target_hours_total = data['target_hours_total']
        if 'is_active' in data:
            goal.is_active = data['is_active']
        if 'end_date' in data and data['end_date']:
            from datetime import datetime
            goal.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
        
        db.commit()
        
        return jsonify({'success': True, 'goal': {
            'id': goal.id,
            'target_hours_per_week': goal.target_hours_per_week,
            'target_hours_total': goal.target_hours_total,
            'is_active': goal.is_active
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/goals/<int:goal_id>', methods=['DELETE'])
def delete_study_goal(goal_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        goal = db.query(StudyGoal).filter(
            StudyGoal.id == goal_id,
            StudyGoal.student_id == session['student_id']
        ).first()
        
        if not goal:
            return jsonify({'success': False, 'message': 'Goal not found'}), 404
        
        db.delete(goal)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Goal deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/study/analytics', methods=['GET'])
def get_study_analytics():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import func
        
        days = int(request.args.get('days', 30))
        start_date = datetime.utcnow() - timedelta(days=days)
        
        sessions = db.query(StudySession).filter(
            StudySession.student_id == session['student_id'],
            StudySession.date >= start_date
        ).all()
        
        total_minutes = sum(s.duration_minutes for s in sessions)
        total_hours = total_minutes / 60.0
        
        course_stats = {}
        for s in sessions:
            course_code = s.course.course_code if s.course else 'Unknown'
            if course_code not in course_stats:
                course_stats[course_code] = {'minutes': 0, 'sessions': 0}
            course_stats[course_code]['minutes'] += s.duration_minutes
            course_stats[course_code]['sessions'] += 1
        
        goals = db.query(StudyGoal).filter(
            StudyGoal.student_id == session['student_id'],
            StudyGoal.is_active == True
        ).all()
        
        goal_progress = []
        for g in goals:
            course_sessions = [s for s in sessions if s.course_id == g.course_id]
            actual_hours = sum(s.duration_minutes for s in course_sessions) / 60.0
            goal_progress.append({
                'goal_id': g.id,
                'course_id': g.course_id,
                'course_code': g.course.course_code if g.course else None,
                'target_hours_per_week': g.target_hours_per_week,
                'actual_hours': actual_hours,
                'progress_percent': (actual_hours / (g.target_hours_per_week * (days / 7))) * 100 if g.target_hours_per_week > 0 else 0
            })
        
        return jsonify({
            'success': True,
            'analytics': {
                'total_hours': total_hours,
                'total_sessions': len(sessions),
                'days_tracked': days,
                'course_stats': course_stats,
                'goal_progress': goal_progress
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/assignments', methods=['GET'])
def get_assignments():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        course_id = request.args.get('course_id', type=int)
        status = request.args.get('status')
        
        query = db.query(Assignment).filter(Assignment.student_id == session['student_id'])
        
        if course_id:
            query = query.filter(Assignment.course_id == course_id)
        if status:
            query = query.filter(Assignment.status == status)
        
        assignments = query.order_by(Assignment.due_date.asc()).all()
        
        return jsonify({
            'success': True,
            'assignments': [{
                'id': a.id,
                'course_id': a.course_id,
                'course_code': a.course.course_code if a.course else None,
                'course_name': a.course.name if a.course else None,
                'title': a.title,
                'description': a.description,
                'assignment_type': a.assignment_type,
                'due_date': a.due_date.isoformat() if a.due_date else None,
                'priority': a.priority,
                'status': a.status,
                'completed_date': a.completed_date.isoformat() if a.completed_date else None,
                'estimated_hours': a.estimated_hours,
                'actual_hours': a.actual_hours,
                'grade': a.grade,
                'notes': a.notes
            } for a in assignments]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/assignments', methods=['POST'])
def create_assignment():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        assignment = Assignment(
            student_id=session['student_id'],
            course_id=data.get('course_id'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            assignment_type=data.get('assignment_type', 'assignment'),
            due_date=datetime.fromisoformat(data['due_date'].replace('Z', '+00:00')) if data.get('due_date') else None,
            priority=data.get('priority', 'medium'),
            status=data.get('status', 'pending'),
            estimated_hours=data.get('estimated_hours'),
            notes=data.get('notes', '')
        )
        
        db.add(assignment)
        db.commit()
        
        return jsonify({
            'success': True,
            'assignment': {
                'id': assignment.id,
                'course_id': assignment.course_id,
                'title': assignment.title,
                'due_date': assignment.due_date.isoformat() if assignment.due_date else None,
                'status': assignment.status
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/assignments/<int:assignment_id>', methods=['PUT'])
def update_assignment(assignment_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        assignment = db.query(Assignment).filter(
            Assignment.id == assignment_id,
            Assignment.student_id == session['student_id']
        ).first()
        
        if not assignment:
            return jsonify({'success': False, 'message': 'Assignment not found'}), 404
        
        if 'title' in data:
            assignment.title = data['title']
        if 'description' in data:
            assignment.description = data['description']
        if 'due_date' in data and data['due_date']:
            from datetime import datetime
            assignment.due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
        if 'priority' in data:
            assignment.priority = data['priority']
        if 'status' in data:
            assignment.status = data['status']
            if data['status'] == 'completed' and not assignment.completed_date:
                from datetime import datetime
                assignment.completed_date = datetime.utcnow()
        if 'estimated_hours' in data:
            assignment.estimated_hours = data['estimated_hours']
        if 'actual_hours' in data:
            assignment.actual_hours = data['actual_hours']
        if 'grade' in data:
            assignment.grade = data['grade']
        if 'notes' in data:
            assignment.notes = data['notes']
        
        db.commit()
        
        return jsonify({'success': True, 'assignment': {
            'id': assignment.id,
            'title': assignment.title,
            'status': assignment.status,
            'due_date': assignment.due_date.isoformat() if assignment.due_date else None
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/assignments/<int:assignment_id>', methods=['DELETE'])
def delete_assignment(assignment_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        assignment = db.query(Assignment).filter(
            Assignment.id == assignment_id,
            Assignment.student_id == session['student_id']
        ).first()
        
        if not assignment:
            return jsonify({'success': False, 'message': 'Assignment not found'}), 404
        
        db.delete(assignment)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Assignment deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/goals', methods=['GET'])
def get_academic_goals():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        goal_type = request.args.get('goal_type')
        is_completed = request.args.get('is_completed')
        
        query = db.query(AcademicGoal).filter(AcademicGoal.student_id == session['student_id'])
        
        if goal_type:
            query = query.filter(AcademicGoal.goal_type == goal_type)
        if is_completed is not None:
            query = query.filter(AcademicGoal.is_completed == (is_completed.lower() == 'true'))
        
        goals = query.order_by(AcademicGoal.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'goals': [{
                'id': g.id,
                'goal_type': g.goal_type,
                'title': g.title,
                'description': g.description,
                'target_value': g.target_value,
                'current_value': g.current_value,
                'target_date': g.target_date.isoformat() if g.target_date else None,
                'semester': g.semester,
                'is_completed': g.is_completed,
                'completed_date': g.completed_date.isoformat() if g.completed_date else None,
                'progress_percent': (g.current_value / g.target_value * 100) if g.target_value and g.target_value > 0 else 0
            } for g in goals]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/goals', methods=['POST'])
def create_academic_goal():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        from datetime import datetime
        goal = AcademicGoal(
            student_id=session['student_id'],
            goal_type=data.get('goal_type', 'gpa'),
            title=data.get('title', ''),
            description=data.get('description', ''),
            target_value=data.get('target_value', 0.0),
            current_value=data.get('current_value', 0.0),
            target_date=datetime.fromisoformat(data['target_date'].replace('Z', '+00:00')) if data.get('target_date') else None,
            semester=data.get('semester', ''),
            is_completed=data.get('is_completed', False)
        )
        
        db.add(goal)
        db.commit()
        
        return jsonify({
            'success': True,
            'goal': {
                'id': goal.id,
                'goal_type': goal.goal_type,
                'title': goal.title,
                'target_value': goal.target_value,
                'current_value': goal.current_value
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/goals/<int:goal_id>', methods=['PUT'])
def update_academic_goal(goal_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        goal = db.query(AcademicGoal).filter(
            AcademicGoal.id == goal_id,
            AcademicGoal.student_id == session['student_id']
        ).first()
        
        if not goal:
            return jsonify({'success': False, 'message': 'Goal not found'}), 404
        
        if 'title' in data:
            goal.title = data['title']
        if 'description' in data:
            goal.description = data['description']
        if 'target_value' in data:
            goal.target_value = data['target_value']
        if 'current_value' in data:
            goal.current_value = data['current_value']
        if 'target_date' in data and data['target_date']:
            from datetime import datetime
            goal.target_date = datetime.fromisoformat(data['target_date'].replace('Z', '+00:00'))
        if 'is_completed' in data:
            goal.is_completed = data['is_completed']
            if data['is_completed'] and not goal.completed_date:
                from datetime import datetime
                goal.completed_date = datetime.utcnow()
        
        db.commit()
        
        return jsonify({'success': True, 'goal': {
            'id': goal.id,
            'title': goal.title,
            'current_value': goal.current_value,
            'target_value': goal.target_value,
            'is_completed': goal.is_completed
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/goals/<int:goal_id>', methods=['DELETE'])
def delete_academic_goal(goal_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        goal = db.query(AcademicGoal).filter(
            AcademicGoal.id == goal_id,
            AcademicGoal.student_id == session['student_id']
        ).first()
        
        if not goal:
            return jsonify({'success': False, 'message': 'Goal not found'}), 404
        
        db.delete(goal)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Goal deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/wishlist', methods=['GET'])
def get_wishlist():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        wishlist = db.query(CourseWishlist).filter(
            CourseWishlist.student_id == session['student_id']
        ).order_by(CourseWishlist.priority.desc(), CourseWishlist.created_at.desc()).all()

        from services.prerequisite_service import is_course_unlocked as _is_unlocked

        items = []
        for w in wishlist:
            code = w.course.course_code if w.course else None
            live_unlocked, _miss = _is_unlocked(session['student_id'], code) if code else (False, [])
            items.append({
                'id': w.id,
                'course_id': w.course_id,
                'course_code': code,
                'course_name': w.course.name if w.course else None,
                'priority': w.priority,
                'target_semester': w.target_semester,
                'notes': w.notes,
                'is_unlocked': live_unlocked,
            })

        return jsonify({'success': True, 'wishlist': items})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/wishlist', methods=['POST'])
def add_to_wishlist():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        course_id = data.get('course_id')
        if not course_id:
            return jsonify({'success': False, 'message': 'Course ID required'}), 400
        
        existing = db.query(CourseWishlist).filter(
            CourseWishlist.student_id == session['student_id'],
            CourseWishlist.course_id == course_id
        ).first()
        
        if existing:
            return jsonify({'success': False, 'message': 'Course already in wishlist'}), 400
        
        course_row = db.query(Course).filter(Course.id == course_id).first()
        if not course_row:
            return jsonify({'success': False, 'message': 'Course not found'}), 404
        
        from services.prerequisite_service import is_course_unlocked
        is_unlocked, _ = is_course_unlocked(session['student_id'], course_row.course_code)
        
        wishlist_item = CourseWishlist(
            student_id=session['student_id'],
            course_id=course_id,
            priority=data.get('priority', 1),
            target_semester=data.get('target_semester', ''),
            notes=data.get('notes', ''),
            is_unlocked=is_unlocked
        )
        
        db.add(wishlist_item)
        db.commit()
        
        return jsonify({
            'success': True,
            'wishlist_item': {
                'id': wishlist_item.id,
                'course_id': wishlist_item.course_id,
                'priority': wishlist_item.priority,
                'is_unlocked': wishlist_item.is_unlocked
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/wishlist/<int:wishlist_id>', methods=['PUT'])
def update_wishlist_item(wishlist_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        wishlist_item = db.query(CourseWishlist).filter(
            CourseWishlist.id == wishlist_id,
            CourseWishlist.student_id == session['student_id']
        ).first()
        
        if not wishlist_item:
            return jsonify({'success': False, 'message': 'Wishlist item not found'}), 404
        
        if 'priority' in data:
            wishlist_item.priority = data['priority']
        if 'target_semester' in data:
            wishlist_item.target_semester = data['target_semester']
        if 'notes' in data:
            wishlist_item.notes = data['notes']
        
        db.commit()
        
        return jsonify({'success': True, 'wishlist_item': {
            'id': wishlist_item.id,
            'priority': wishlist_item.priority,
            'target_semester': wishlist_item.target_semester
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/wishlist/<int:wishlist_id>', methods=['DELETE'])
def delete_wishlist_item(wishlist_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        wishlist_item = db.query(CourseWishlist).filter(
            CourseWishlist.id == wishlist_id,
            CourseWishlist.student_id == session['student_id']
        ).first()
        
        if not wishlist_item:
            return jsonify({'success': False, 'message': 'Wishlist item not found'}), 404
        
        db.delete(wishlist_item)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Removed from wishlist'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notes', methods=['GET'])
def get_study_notes():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        course_id = request.args.get('course_id', type=int)
        topic = request.args.get('topic')
        
        query = db.query(StudyNote).filter(StudyNote.student_id == session['student_id'])
        
        if course_id:
            query = query.filter(StudyNote.course_id == course_id)
        if topic:
            query = query.filter(StudyNote.topic == topic)
        
        notes = query.order_by(StudyNote.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'notes': [{
                'id': n.id,
                'course_id': n.course_id,
                'course_code': n.course.course_code if n.course else None,
                'course_name': n.course.name if n.course else None,
                'title': n.title,
                'content': n.content,
                'tags': n.tags,
                'topic': n.topic,
                'assignment_id': n.assignment_id,
                'is_shared': n.is_shared,
                'created_at': n.created_at.isoformat() if n.created_at else None,
                'updated_at': n.updated_at.isoformat() if n.updated_at else None
            } for n in notes]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notes', methods=['POST'])
def create_study_note():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        note = StudyNote(
            student_id=session['student_id'],
            course_id=data.get('course_id'),
            title=data.get('title', ''),
            content=data.get('content', ''),
            tags=data.get('tags', ''),
            topic=data.get('topic', ''),
            assignment_id=data.get('assignment_id'),
            is_shared=data.get('is_shared', False)
        )
        
        db.add(note)
        db.commit()
        
        return jsonify({
            'success': True,
            'note': {
                'id': note.id,
                'course_id': note.course_id,
                'title': note.title,
                'created_at': note.created_at.isoformat() if note.created_at else None
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_study_note(note_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        note = db.query(StudyNote).filter(
            StudyNote.id == note_id,
            StudyNote.student_id == session['student_id']
        ).first()
        
        if not note:
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        
        if 'title' in data:
            note.title = data['title']
        if 'content' in data:
            note.content = data['content']
        if 'tags' in data:
            note.tags = data['tags']
        if 'topic' in data:
            note.topic = data['topic']
        if 'is_shared' in data:
            note.is_shared = data['is_shared']
        
        db.commit()
        
        return jsonify({'success': True, 'note': {
            'id': note.id,
            'title': note.title,
            'updated_at': note.updated_at.isoformat() if note.updated_at else None
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_study_note(note_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        note = db.query(StudyNote).filter(
            StudyNote.id == note_id,
            StudyNote.student_id == session['student_id']
        ).first()
        
        if not note:
            return jsonify({'success': False, 'message': 'Note not found'}), 404
        
        db.delete(note)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Note deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/resources', methods=['GET'])
def get_learning_resources():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        course_id = request.args.get('course_id', type=int)
        resource_type = request.args.get('resource_type')
        
        query = db.query(LearningResource).filter(LearningResource.student_id == session['student_id'])
        
        if course_id:
            query = query.filter(LearningResource.course_id == course_id)
        if resource_type:
            query = query.filter(LearningResource.resource_type == resource_type)
        
        resources = query.order_by(LearningResource.created_at.desc()).all()
        
        return jsonify({
            'success': True,
            'resources': [{
                'id': r.id,
                'course_id': r.course_id,
                'course_code': r.course.course_code if r.course else None,
                'course_name': r.course.name if r.course else None,
                'title': r.title,
                'resource_type': r.resource_type,
                'url': r.url,
                'description': r.description,
                'topic': r.topic,
                'tags': r.tags,
                'is_helpful': r.is_helpful,
                'helpful_count': r.helpful_count,
                'is_shared': r.is_shared,
                'created_at': r.created_at.isoformat() if r.created_at else None
            } for r in resources]
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/resources', methods=['POST'])
def create_learning_resource():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    if not data:
        return jsonify({'success': False, 'message': 'No data provided'}), 400
    
    db = get_db()
    try:
        resource = LearningResource(
            student_id=session['student_id'],
            course_id=data.get('course_id'),
            title=data.get('title', ''),
            resource_type=data.get('resource_type', 'link'),
            url=data.get('url', ''),
            description=data.get('description', ''),
            topic=data.get('topic', ''),
            tags=data.get('tags', ''),
            is_helpful=data.get('is_helpful', True),
            is_shared=data.get('is_shared', False)
        )
        
        db.add(resource)
        db.commit()
        
        return jsonify({
            'success': True,
            'resource': {
                'id': resource.id,
                'course_id': resource.course_id,
                'title': resource.title,
                'resource_type': resource.resource_type,
                'created_at': resource.created_at.isoformat() if resource.created_at else None
            }
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/resources/<int:resource_id>', methods=['PUT'])
def update_learning_resource(resource_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    data = request.json
    db = get_db()
    try:
        resource = db.query(LearningResource).filter(
            LearningResource.id == resource_id,
            LearningResource.student_id == session['student_id']
        ).first()
        
        if not resource:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        
        if 'title' in data:
            resource.title = data['title']
        if 'url' in data:
            resource.url = data['url']
        if 'description' in data:
            resource.description = data['description']
        if 'topic' in data:
            resource.topic = data['topic']
        if 'tags' in data:
            resource.tags = data['tags']
        if 'is_helpful' in data:
            resource.is_helpful = data['is_helpful']
        if 'is_shared' in data:
            resource.is_shared = data['is_shared']
        
        db.commit()
        
        return jsonify({'success': True, 'resource': {
            'id': resource.id,
            'title': resource.title,
            'is_helpful': resource.is_helpful
        }})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/resources/<int:resource_id>', methods=['DELETE'])
def delete_learning_resource(resource_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        resource = db.query(LearningResource).filter(
            LearningResource.id == resource_id,
            LearningResource.student_id == session['student_id']
        ).first()
        
        if not resource:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        
        db.delete(resource)
        db.commit()
        
        return jsonify({'success': True, 'message': 'Resource deleted'})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/resources/<int:resource_id>/helpful', methods=['POST'])
def mark_resource_helpful(resource_id):
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        resource = db.query(LearningResource).filter(LearningResource.id == resource_id).first()
        
        if not resource:
            return jsonify({'success': False, 'message': 'Resource not found'}), 404
        
        resource.helpful_count = (resource.helpful_count or 0) + 1
        resource.is_helpful = True
        
        db.commit()
        
        return jsonify({'success': True, 'helpful_count': resource.helpful_count})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


@app.route('/api/performance/dashboard', methods=['GET'])
def get_performance_dashboard():
    
    if 'student_id' not in session:
        return jsonify({'success': False, 'message': 'Not authenticated'}), 401
    
    db = get_db()
    try:
        student_id = session['student_id']
        student = db.query(Student).filter(Student.id == student_id).first()
        
        if not student:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        completed_courses = db.query(StudentCourse).filter(
            StudentCourse.student_id == student_id
        ).order_by(StudentCourse.created_at.desc()).all()
        
        gpa_trend = []
        semester_gpa = defaultdict(lambda: {'total_points': 0, 'total_credits': 0, 'courses': []})
        
        for sc in completed_courses:
            if sc.grade and sc.created_at:
                grade_points = GRADE_POINTS.get(sc.grade.upper(), 0)
                credits = sc.course.credit_hours if sc.course else 3.0
                
                semester_gpa[sc.created_at.strftime('%Y-%m')]['total_points'] += grade_points * credits
                semester_gpa[sc.created_at.strftime('%Y-%m')]['total_credits'] += credits
                semester_gpa[sc.created_at.strftime('%Y-%m')]['courses'].append({
                    'code': sc.course.course_code if sc.course else 'N/A',
                    'grade': sc.grade,
                    'credits': credits
                })
        
        cumulative_points = 0
        cumulative_credits = 0
        
        for month in sorted(semester_gpa.keys()):
            month_data = semester_gpa[month]
            cumulative_points += month_data['total_points']
            cumulative_credits += month_data['total_credits']
            
            if cumulative_credits > 0:
                gpa = cumulative_points / cumulative_credits
                gpa_trend.append({
                    'month': month,
                    'gpa': round(gpa, 2),
                    'courses_count': len(month_data['courses'])
                })
        
        course_performance = []
        for sc in completed_courses[:20]:
            if sc.course and sc.grade:
                predicted = db.query(CourseDifficultyPrediction).filter(
                    CourseDifficultyPrediction.student_id == student_id,
                    CourseDifficultyPrediction.course_id == sc.course.id
                ).first()
                
                actual_grade_points = GRADE_POINTS.get(sc.grade.upper(), 0)
                predicted_difficulty = predicted.predicted_difficulty if predicted else None
                
                course_performance.append({
                    'course_code': sc.course.course_code,
                    'course_name': sc.course.name or '',
                    'grade': sc.grade,
                    'grade_points': actual_grade_points,
                    'predicted_difficulty': round(predicted_difficulty, 2) if predicted_difficulty else None,
                    'credits': sc.course.credit_hours
                })
        
        study_sessions = db.query(StudySession).filter(
            StudySession.student_id == student_id
        ).order_by(StudySession.date.desc()).limit(100).all()
        
        study_time_by_course = defaultdict(lambda: {'hours': 0, 'sessions': 0})
        study_time_by_date = defaultdict(float)
        
        for study_session in study_sessions:
            if study_session.course:
                course_code = study_session.course.course_code
                hours = (study_session.duration_minutes or 0) / 60.0
                study_time_by_course[course_code]['hours'] += hours
                study_time_by_course[course_code]['sessions'] += 1
                study_time_by_date[study_session.date.strftime('%Y-%m-%d')] += hours
        
        study_analytics = {
            'by_course': [
                {
                    'course_code': code,
                    'total_hours': round(data['hours'], 1),
                    'sessions': data['sessions']
                }
                for code, data in sorted(study_time_by_course.items(), key=lambda x: x[1]['hours'], reverse=True)[:10]
            ],
            'by_date': [
                {'date': date, 'hours': round(hours, 1)}
                for date, hours in sorted(study_time_by_date.items())[-30:]
            ]
        }
        
        assignments = db.query(Assignment).filter(
            Assignment.student_id == student_id
        ).all()
        
        assignment_stats = {
            'total': len(assignments),
            'completed': sum(1 for a in assignments if a.status == 'completed'),
            'pending': sum(1 for a in assignments if a.status != 'completed'),
            'overdue': sum(1 for a in assignments if a.status != 'completed' and a.due_date and a.due_date < datetime.utcnow())
        }
        
        academic_goals = db.query(AcademicGoal).filter(
            AcademicGoal.student_id == student_id
        ).all()
        
        goal_stats = {
            'total': len(academic_goals),
            'completed': sum(1 for g in academic_goals if g.is_completed),
            'in_progress': sum(1 for g in academic_goals if not g.is_completed),
            'goals': [
                {
                    'title': g.title,
                    'type': g.goal_type,
                    'current': g.current_value,
                    'target': g.target_value,
                    'progress': round((g.current_value / g.target_value * 100) if g.target_value > 0 else 0, 1),
                    'is_completed': g.is_completed
                }
                for g in academic_goals[:10]
            ]
        }
        
        total_credits = sum(sc.course.credit_hours if sc.course else 0 for sc in completed_courses)
        degree_progress = {
            'credits_completed': total_credits,
            'credits_required': 120,
            'percentage': round((total_credits / 120 * 100) if 120 > 0 else 0, 1)
        }
        
        return jsonify({
            'success': True,
            'data': {
                'gpa_trend': gpa_trend,
                'current_gpa': round(student.gpa, 2) if student.gpa else 0,
                'course_performance': course_performance,
                'study_analytics': study_analytics,
                'assignment_stats': assignment_stats,
                'goal_stats': goal_stats,
                'degree_progress': degree_progress,
                'total_courses': len(completed_courses),
                'total_credits': total_credits
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        db.close()


if __name__ == '__main__':
    import os

    from config import DEBUG, FLASK_USE_RELOADER, HOST, PORT

    run_options = {
        'host': HOST,
        'port': PORT,
        'debug': DEBUG,
        'threaded': True,
    }
    if DEBUG:
        # Stat reloader + SQLite under the project tree can cause constant restarts; allow disabling.
        run_options['use_reloader'] = FLASK_USE_RELOADER
        run_options['use_debugger'] = True
        # Ignore binary / data churn when matching reloader paths (fnmatch on basenames in filter).
        run_options['exclude_patterns'] = ['*.db', '*.sqlite3', '*.pkl', '*.pickle']

    app.run(**run_options)
