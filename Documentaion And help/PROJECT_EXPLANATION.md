# Smart Academic Planning — How the Project Works

This document explains how the Smart Academic Planning system is built and how data and control flow through it.

> **Team workflow, Git cadence, discussion questions, and a longer narrative overview** → see **`PROJECT_GUIDE.md`**.  
> **Where ML Models 1–3 are used (files, APIs, UI)** → see **`ML_MODELS.md`**.

---

## 1. Overview

Smart Academic Planning is a web application that helps students choose courses, plan semesters, and track academic progress. It uses:

- **Flask** for the backend (Python).
- **SQLite** by default for the database (no server required). MySQL can be used by setting `USE_MYSQL=1`.
- **Pre-trained ML models** (XGBoost, Gradient Boosting) for course difficulty, semester workload, and academic risk.
- **Bootstrap 5** and **jQuery** on the frontend.

Users register, log in, add completed courses and grades, then get course recommendations, semester plans, prerequisite graphs, financial and study tools, and an optional AI advisor (OpenAI).

---

## 2. High-Level Architecture

```
Browser (HTML/JS/CSS)
        │
        ▼
   Flask app (app.py)
        │
   ┌────┴────┬──────────────┬─────────────────┬──────────────────┐
   ▼         ▼              ▼                 ▼                  ▼
 config   database/      services/          ml/            templates/
           db.py    prerequisite_service  models/        static/
           models.py ml_service
                     recommendation_engine
                     advisor
                     course_cache
                     prerequisite_graph
```

- **config.py**: Settings (database choice, paths, secrets, grade points, credit limits).
- **database/db.py**: Creates the SQLAlchemy engine (SQLite or MySQL), session factory, and helpers (`get_db`, `init_db`, `test_connection`).
- **database/models.py**: All table definitions (Student, Course, StudentCourse, SemesterPlan, etc.).
- **app.py**: Defines all routes (pages and APIs), uses `get_db()` and services.
- **services/**: Business logic (prerequisites, recommendations, ML predictions, advisor, cache, graph).
- **ml/models/**: Pickled models and metadata used by `ml_service.py`.
- **Training**: Run `python ml/train_all_models.py` to train models **1–3** (see **`ML_MODELS.md`** for purpose and usage of each).

---

## 3. Configuration and Database Connection

**config.py**

- **BASE_DIR**: Project root directory.
- **USE_MYSQL**: If set (e.g. `USE_MYSQL=1`), the app connects to MySQL using `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`. Otherwise it uses SQLite.
- **SQLite**: Database file is `instance/smart_academic.db`. The `instance` folder is created automatically.
- **Paths**: `DATA_DIR`, `COURSES_FILE`, `PREREQUISITES_FILE`, `ML_MODELS_DIR` point to data and ML assets.
- **GRADE_POINTS**: Mapping of letter grades (A+, A, B+, …) to numeric grade points.
- **STRATEGIES**: `easy`, `balanced`, `fast` for recommendation behavior.
- **MIN_CREDITS / MAX_CREDITS / DEFAULT_CREDITS**: Used for semester planning and recommendations.

**database/db.py**

- If `USE_MYSQL` is true: builds a PyMySQL connection with the config values and passes it to SQLAlchemy via a `creator`; engine uses `mysql+pymysql://`.
- If `USE_MYSQL` is false: creates a SQLite engine pointing at `SQLITE_DB_PATH` with `check_same_thread=False` for Flask.
- **SessionLocal**: A scoped session factory bound to that engine. All request handlers use `get_db()` to get a session and must close it when done.
- **init_db()**: Drops all tables and recreates them (used by setup scripts).
- **test_connection()**: Runs `SELECT 1` to verify the database is reachable.

On startup, **app.py** calls `Base.metadata.create_all(bind=engine)` so all tables exist (e.g. for a fresh SQLite file). It does not drop data.

---

## 4. Database Models (Schema)

**database/models.py** defines the main entities:

- **Course**: course_code, subject, number, name, description, credit_hours, level, type, flags (is_lab, is_major_course), prerequisite_count, prerequisite_depth, graph_centrality, unlocks_count.
- **Prerequisite**: Links two courses (course_id, prerequisite_id).
- **Student**: username, email, password_hash, major, current_semester, strategy, workload_tolerance, gpa, is_admin, timestamps.
- **StudentCourse**: student_id, course_id, grade, grade_points, semester_taken, status (e.g. completed).
- **CourseRating**: student_id, course_id, rating (e.g. 1–5 difficulty).
- **SemesterPlan / SemesterPlanCourse**: Planned semesters and which courses are in each.
- **CourseDifficultyPrediction**: Cached or stored difficulty predictions per student/course.
- **AcademicCalendarEvent**, **FinancialRecord**, **Scholarship**: Calendar and financial tracking.
- **StudySession**, **StudyGoal**, **Assignment**, **AcademicGoal**, **CourseWishlist**, **StudyNote**, **LearningResource**: Study and assignment tracking.

Relationships (e.g. Student → StudentCourse → Course) are defined so the ORM can load related data without writing raw SQL.

---

## 5. Application Entry and Request Flow (app.py)

**Startup**

- Flask app is created, secret key and CORS set.
- `Base.metadata.create_all(bind=engine)` ensures all tables exist.
- **before_request (setup())**: Runs `test_connection()` once per app lifecycle and enforces admin-only routes when `session.is_admin` is set.

**Pages (HTML)**

- `/`: Home (index).
- `/login`, `/register`: Login and registration forms.
- `/dashboard`: Main student dashboard (requires login, non-admin).
- `/profile`: Student profile and settings.
- `/admin`: Admin dashboard (admin only).
- `/admin/courses`: Admin course list/edit (admin only).

**Authentication APIs**

- `POST /api/register`: Validates input, hashes password, creates `Student`, starts session.
- `POST /api/login`: Checks credentials, sets `session['student_id']` and optionally `session['is_admin']`.
- `POST /api/logout`: Clears session.

**Profile**

- `GET /api/student/profile`: Returns current student’s profile.
- `PUT /api/student/profile`: Updates major, strategy, workload_tolerance, etc.

**Completed courses**

- `GET /api/courses/completed`: List completed courses for the student.
- `POST /api/courses/completed`: Add a completed course (course code, grade, semester).
- `PUT /api/courses/completed/<id>`: Update a completed course.
- `DELETE /api/courses/completed/<id>`: Remove a completed course.

**Course discovery and difficulty**

- `GET /api/courses/unlocked`: Courses the student can take (prerequisites satisfied).
- `GET /api/courses/available`: Similar availability with extra filters.
- `GET /api/courses/locked`: Courses still locked by prerequisites.
- `GET /api/courses/search?q=...`: Search courses.
- `GET /api/courses/<course_code>/difficulty`: ML-based difficulty prediction for that course for the current student.
- `POST /api/courses/<course_code>/rate`: Submit a difficulty rating (1–5).
- `GET /api/courses/<course_code>/ratings`: Aggregate ratings for a course.

**Recommendations and semester**

- `GET /api/recommendations?credits=...`: Recommended courses for the semester (uses strategy, credits, prerequisites, and difficulty).
- `POST /api/semester/optimize`: Analyze a list of course codes for predicted workload and overload risk.

**Advisor and explanations**

- `POST /api/advisor/chat`: Send a message to the advisor (OpenAI if configured, else rule-based).
- `GET /api/advisor/bottlenecks`: Courses that unlock many others (bottlenecks).
- `GET /api/courses/<course_code>/explain`: Explanation for why a course is locked or recommended.

**Other APIs**

- Majors: `GET /api/majors`.
- GPA: `POST /api/gpa/what-if`, `POST /api/gpa/simulate`.
- Prerequisite graph: `GET /api/prerequisite-graph`.
- Export: `GET/POST /api/export/plan/csv`, `GET/POST /api/export/plan/pdf`.
- Calendar: CRUD for `/api/calendar/events`.
- Financial: records, summary, tuition calculator, scholarships (CRUD and eligibility).
- Study: sessions, goals, analytics.
- Assignments: CRUD.
- Academic goals: CRUD.
- Wishlist: CRUD.
- Admin: stats, courses list/update, majors.

Each route that needs the database calls `get_db()`, uses the session, and should close it (e.g. in a `finally` block or after the response).

---

## 6. How Recommendations Work (recommendation_engine.py)

- Loads the **student** and their **completed course codes** from the DB.
- Gets **unlocked courses** (prerequisites satisfied) via `get_unlocked_courses(student_id, filter_by_major=True)`.
- Excludes already completed courses and invalid credits.
- Splits courses into major vs non-major; limits how many are scored.
- For each candidate course:
  - Gets **course difficulty** (from cache or ML) via `get_course_difficulty(course_code)`.
  - Optionally adjusts difficulty by student GPA (e.g. lower GPA → slightly harder; higher GPA → slightly easier).
  - Computes a **recommendation score** (e.g. inverse of difficulty, possibly with strategy weighting).
- Sorts by score and returns a list of recommended courses with metadata (difficulty category, credits, etc.).

**optimize_semester_plan** takes a list of course codes and returns predicted semester difficulty and overload risk using the semester workload model.

---

## 7. How Prerequisites Work (prerequisite_service.py, course_cache)

- **get_completed_courses(student_id)**: Returns set of course codes the student has completed (from `StudentCourse` with status completed).
- **get_prerequisites_for_course(course_code)**: Delegates to course cache (which reads from DB or CSV/cache) to get list of prerequisite course codes.
- **is_course_unlocked(student_id, course_code)**: Compares required prerequisites to completed courses; returns whether unlocked and list of missing prerequisites.
- **get_unlocked_courses(student_id, filter_by_major)**: Builds list of courses the student can take: optionally restricts to major and related subjects, uses prerequisite graph so only courses whose prereqs are satisfied are included. Returns list of dicts with course_code, credit_hours, is_major_course, etc.

Course data and prerequisite lists are centralized in **course_cache** (and ultimately from DB or CSV) so the rest of the app does not duplicate that logic.

---

## 8. How ML Predictions Work (ml_service.py)

- **Models used**: Model 1 (course difficulty), Model 2 (semester workload), Model 3 (academic risk). Stored as pickle files in `ml/models/` with optional metadata (e.g. scaler for Model 2).
- **load_models()**: Lazy-loads pickle files into module-level variables so they are loaded once per process.
- **predict_course_difficulty(student_id, course_id)**: Loads student and course from DB, builds a feature vector (e.g. GPA, credits, course features, historical grades), runs Model 1, returns difficulty_score, difficulty_category (Easy/Medium/Hard), and confidence.
- **predict_semester_workload(student_id, list of course_ids)**: Builds features for the semester (e.g. total credits, per-course difficulty), uses Model 2 (and scaler if present), returns predicted difficulty and overload risk.
- **Academic risk (Model 3)** follows the same pattern: load student history, build features (including difficulty signals from Model 1), run the classifier, return risk category and factors.

If a model file is missing, the service returns safe defaults (e.g. medium difficulty, zero confidence) so the UI still works.

---

## 9. Advisor (advisor.py)

- **chatbot_response(message, student_id)**: If an OpenAI API key is set, sends the message (plus context such as major, completed courses, strategy) to the API and returns the reply. Otherwise uses a rule-based fallback (e.g. keyword-based answers about prerequisites, recommendations, GPA).
- **explain_course_lock**, **explain_semester_difficulty**: Build short explanations (e.g. “Course X is locked because you have not completed Y and Z”) for the UI.
- **get_bottleneck_courses(student_id)**: Identifies courses that are prerequisites for many others so the student can prioritize them.

---

## 10. Prerequisite Graph (prerequisite_graph.py)

Builds a directed graph of courses and prerequisites (nodes = courses, edges = prerequisite → course). Used to serve **GET /api/prerequisite-graph** with nodes and edges for the frontend (e.g. DAG visualization: completed / unlocked / locked).

---

## 11. Data Loading and Setup

- **scripts/setup_database.py**: Calls `test_connection()`, then `init_db()` (drop + create all tables), then loads courses and prerequisites (e.g. from `load_data_to_db_fast.py`). Run once for a new DB or to reset.
- **scripts/load_data_to_db_fast.py**: Reads `Data/merged_courses.csv` and `Data/prerequisites.csv`, inserts into `Course` and `Prerequisite` (invoked from **setup_database.py**).
- **scripts/seed_admin.py**: Creates a default admin user (e.g. admin / admin123). **scripts/set_admin.py**: Promotes an existing user to admin.

Course and prerequisite data can also be loaded from CSV into the DB by other scripts; the app always reads from the database via the ORM and course cache.

---

## 12. Frontend (Templates and Static)

- **templates/base.html**: Navbar, footer (© 2026 Smart Academic Planning), block placeholders for title, content, extra_css, extra_js. Includes Bootstrap, jQuery, Chart.js, and `static/js/main.js` (e.g. dark mode, logout).
- **templates/index.html**, **login.html**, **register.html**, **dashboard.html**, **profile.html**, **admin/dashboard.html**, **admin/courses.html**: Extend base and fill content and optional JS/CSS.
- **static/css/style.css**: Layout, dark mode, footer, modals, forms.
- **static/js/dashboard.js**: Dashboard-specific AJAX calls (recommendations, semester optimize, calendar, financial, study, assignments, goals, wishlist, export, etc.) and DOM updates.

The dashboard calls the APIs above to load and update data without full page reloads.

---

## 13. End-to-End User Flows

**New user**

1. Opens `/register`, submits username, email, password.
2. `POST /api/register` creates `Student`, logs in via session.
3. Redirected to dashboard.

**Building a plan**

1. User goes to profile and sets major, strategy (easy/balanced/fast).
2. User adds completed courses and grades via “Completed courses” and `POST /api/courses/completed`.
3. `GET /api/recommendations` returns suggested courses; dashboard displays them.
4. User selects courses for the semester; `POST /api/semester/optimize` shows predicted workload and risk.
5. User can export plan via `/api/export/plan/csv` or `/api/export/plan/pdf`.

**Understanding prerequisites**

1. `GET /api/courses/unlocked` and `GET /api/courses/locked` drive “can take” vs “locked” lists.
2. `GET /api/prerequisite-graph` feeds the graph visualization.
3. `GET /api/courses/<code>/explain` explains why a course is locked or recommended.
4. `GET /api/advisor/bottlenecks` highlights bottleneck courses.

**Difficulty and ratings**

1. `GET /api/courses/<course_code>/difficulty` shows ML-predicted difficulty for the logged-in student.
2. User can rate a course; `POST /api/courses/<course_code>/rate` saves the rating; aggregate ratings are shown via `/api/courses/<course_code>/ratings`.

**Admin**

1. Admin logs in; `session['is_admin']` is set.
2. Admin can open `/admin` and `/admin/courses`, and call `/api/admin/stats`, `/api/admin/courses`, etc., to manage courses and view stats.

---

## 14. Summary

- **Config** chooses SQLite (default) or MySQL and sets paths and constants.
- **Database** layer creates tables on startup and exposes a single engine/session factory; all persistence goes through SQLAlchemy models.
- **app.py** defines every URL and delegates to services and the DB.
- **Services** implement prerequisites, recommendations, ML predictions, advisor, and graph; they use `get_db()` and the course cache.
- **ML** models are loaded from disk and used to predict difficulty, workload, and academic risk.
- **Frontend** uses base template and dashboard JS to call APIs and render the UI; footer shows © 2026 Smart Academic Planning.

Running `python app.py` starts the server; with SQLite, no extra database setup is required beyond creating tables (done automatically). For a full course catalog, run `python scripts/setup_database.py` once after placing the CSV data in the expected paths.
