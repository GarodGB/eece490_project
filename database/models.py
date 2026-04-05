from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Course(Base):
    __tablename__ = 'courses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(50), unique=True, nullable=False, index=True)
    subject = Column(String(10), nullable=False)
    number = Column(String(10), nullable=False)
    name = Column(String(200))
    description = Column(Text)
    credit_hours = Column(Float, default=3.0)
    course_level = Column(Integer)
    course_type = Column(String(50))
    is_lab = Column(Boolean, default=False)
    is_major_course = Column(Boolean, default=True)
    prerequisite_count = Column(Integer, default=0)
    prerequisite_depth = Column(Integer, default=0)
    graph_centrality = Column(Float, default=0.0)
    unlocks_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    prerequisites = relationship('Prerequisite', foreign_keys='Prerequisite.course_id', back_populates='course')
    dependents = relationship('Prerequisite', foreign_keys='Prerequisite.prerequisite_id', back_populates='prerequisite_course')
    student_courses = relationship('StudentCourse', back_populates='course')
    
    __table_args__ = (Index('idx_course_code', 'course_code'),)


class Prerequisite(Base):
    __tablename__ = 'prerequisites'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    prerequisite_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    course = relationship('Course', foreign_keys=[course_id], back_populates='prerequisites')
    prerequisite_course = relationship('Course', foreign_keys=[prerequisite_id], back_populates='dependents')
    
    __table_args__ = (Index('idx_course_prereq', 'course_id', 'prerequisite_id'),)


class Student(Base):
    __tablename__ = 'students'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(255))
    major = Column(String(50), default='ECE')
    current_semester = Column(Integer, default=1)
    strategy = Column(String(20), default='balanced')
    workload_tolerance = Column(Float, default=0.5)
    gpa = Column(Float, default=0.0)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    completed_courses = relationship('StudentCourse', back_populates='student', cascade='all, delete-orphan')
    predictions = relationship('CourseDifficultyPrediction', back_populates='student', cascade='all, delete-orphan')
    semester_plans = relationship('SemesterPlan', back_populates='student', cascade='all, delete-orphan')
    calendar_events = relationship('AcademicCalendarEvent', cascade='all, delete-orphan')
    financial_records = relationship('FinancialRecord', cascade='all, delete-orphan')
    scholarships = relationship('Scholarship', cascade='all, delete-orphan')
    study_sessions = relationship('StudySession', cascade='all, delete-orphan')
    study_goals = relationship('StudyGoal', cascade='all, delete-orphan')
    assignments = relationship('Assignment', cascade='all, delete-orphan')
    academic_goals = relationship('AcademicGoal', cascade='all, delete-orphan')
    course_wishlist = relationship('CourseWishlist', cascade='all, delete-orphan')
    study_notes = relationship('StudyNote', cascade='all, delete-orphan')
    learning_resources = relationship('LearningResource', cascade='all, delete-orphan')


class StudentCourse(Base):
    __tablename__ = 'student_courses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    grade = Column(String(5))
    grade_points = Column(Float)
    semester_taken = Column(Integer)
    status = Column(String(20), default='completed')
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship('Student', back_populates='completed_courses')
    course = relationship('Course', back_populates='student_courses')
    
    __table_args__ = (Index('idx_student_course', 'student_id', 'course_id'),)


class CourseDifficultyPrediction(Base):
    __tablename__ = 'course_difficulty_predictions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    difficulty_score = Column(Float)
    difficulty_category = Column(String(20))
    confidence = Column(Float)
    predicted_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship('Student', back_populates='predictions')
    course = relationship('Course')


class SemesterPlan(Base):
    __tablename__ = 'semester_plans'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    semester_number = Column(Integer, nullable=False)
    total_credits = Column(Float, default=0.0)
    predicted_difficulty = Column(Float)
    overload_risk = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    courses = relationship('SemesterPlanCourse', back_populates='semester_plan', cascade='all, delete-orphan')
    student = relationship('Student', back_populates='semester_plans')


class SemesterPlanCourse(Base):
    __tablename__ = 'semester_plan_courses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    semester_plan_id = Column(Integer, ForeignKey('semester_plans.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    
    semester_plan = relationship('SemesterPlan', back_populates='courses')
    course = relationship('Course')


class CourseRating(Base):
    
    __tablename__ = 'course_ratings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (Index('idx_course_rating_course', 'course_id'), Index('idx_course_rating_student_course', 'student_id', 'course_id'),)


class AcademicCalendarEvent(Base):
    
    __tablename__ = 'academic_calendar_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    event_type = Column(String(50), nullable=False)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)
    is_all_day = Column(Boolean, default=True)
    color = Column(String(20), default='#3788d8')
    reminder_days = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='calendar_events')
    
    __table_args__ = (Index('idx_calendar_student_date', 'student_id', 'start_date'),)


class FinancialRecord(Base):
    
    __tablename__ = 'financial_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    record_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    amount = Column(Float, nullable=False)
    semester = Column(String(20))
    due_date = Column(DateTime)
    is_paid = Column(Boolean, default=False)
    paid_date = Column(DateTime)
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='financial_records')
    
    __table_args__ = (Index('idx_financial_student_semester', 'student_id', 'semester'),)


class Scholarship(Base):
    
    __tablename__ = 'scholarships'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    amount = Column(Float, nullable=False)
    eligibility_gpa_min = Column(Float)
    eligibility_credits_min = Column(Integer)
    eligibility_major = Column(String(50))
    application_deadline = Column(DateTime)
    is_applied = Column(Boolean, default=False)
    is_awarded = Column(Boolean, default=False)
    awarded_date = Column(DateTime)
    renewal_required = Column(Boolean, default=False)
    renewal_gpa_min = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='scholarships')
    
    __table_args__ = (Index('idx_scholarship_student', 'student_id'),)


class StudySession(Base):
    __tablename__ = 'study_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    date = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    student = relationship('Student', overlaps='study_sessions')
    course = relationship('Course')
    
    __table_args__ = (Index('idx_study_student_date', 'student_id', 'date'), Index('idx_study_student_course', 'student_id', 'course_id'),)


class StudyGoal(Base):
    __tablename__ = 'study_goals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=True)
    goal_type = Column(String(50), nullable=False)
    target_hours_per_week = Column(Float, default=0.0)
    target_hours_total = Column(Float, default=0.0)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='study_goals')
    course = relationship('Course')
    
    __table_args__ = (Index('idx_study_goal_student', 'student_id'),)


class Assignment(Base):
    __tablename__ = 'assignments'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    assignment_type = Column(String(50), nullable=False)
    due_date = Column(DateTime, nullable=False)
    priority = Column(String(20), default='medium')
    status = Column(String(20), default='pending')
    completed_date = Column(DateTime)
    estimated_hours = Column(Float)
    actual_hours = Column(Float)
    grade = Column(String(5))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='assignments')
    course = relationship('Course')
    
    __table_args__ = (Index('idx_assignment_student_due', 'student_id', 'due_date'), Index('idx_assignment_student_course', 'student_id', 'course_id'),)


class AcademicGoal(Base):
    __tablename__ = 'academic_goals'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    goal_type = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    target_value = Column(Float)
    current_value = Column(Float, default=0.0)
    target_date = Column(DateTime)
    semester = Column(String(20))
    is_completed = Column(Boolean, default=False)
    completed_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='academic_goals')
    
    __table_args__ = (Index('idx_goal_student', 'student_id'), Index('idx_goal_student_type', 'student_id', 'goal_type'),)


class CourseWishlist(Base):
    __tablename__ = 'course_wishlist'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    priority = Column(Integer, default=1)
    target_semester = Column(String(20))
    notes = Column(Text)
    is_unlocked = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='course_wishlist')
    course = relationship('Course')
    
    __table_args__ = (Index('idx_wishlist_student', 'student_id'), Index('idx_wishlist_student_course', 'student_id', 'course_id'),)


class StudyNote(Base):
    __tablename__ = 'study_notes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    tags = Column(String(500))
    topic = Column(String(200))
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=True)
    is_shared = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='study_notes')
    course = relationship('Course')
    assignment = relationship('Assignment')
    
    __table_args__ = (Index('idx_note_student_course', 'student_id', 'course_id'), Index('idx_note_student_created', 'student_id', 'created_at'),)


class LearningResource(Base):
    __tablename__ = 'learning_resources'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False)
    title = Column(String(200), nullable=False)
    resource_type = Column(String(50), nullable=False)
    url = Column(Text)
    description = Column(Text)
    topic = Column(String(200))
    tags = Column(String(500))
    is_helpful = Column(Boolean, default=True)
    helpful_count = Column(Integer, default=0)
    is_shared = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    student = relationship('Student', overlaps='learning_resources')
    course = relationship('Course')
    
    __table_args__ = (Index('idx_resource_student_course', 'student_id', 'course_id'), Index('idx_resource_student_type', 'student_id', 'resource_type'),)
