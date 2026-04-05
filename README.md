# Smart Academic Planning System

A comprehensive AI-powered web application for semester-wise course selection and workload optimization.

## Features

- **AI-Powered Course Difficulty Prediction** - Predicts course difficulty based on student profile
- **Semester Workload Estimation** - Estimates overall semester difficulty and overload risk
- **Smart Course Recommendations** - Personalized recommendations based on academic strategy
- **Prerequisite Tracking** - Automatic course unlocking based on completed prerequisites
- **Prerequisite Graph** - Interactive DAG of courses (completed / unlocked / locked)
- **What-If GPA** - See what GPA you need this semester to hit a target; simulate grades
- **Export & Share** - Export semester plan as PDF or CSV
- **Dark Mode** - Toggle with preference saved in localStorage
- **Course Ratings** - Rate completed courses (1–5 difficulty); see aggregate next to predictions
- **Semester Planner** - Plan and analyze semester course loads
- **AI Academic Advisor** - Chatbot for academic guidance
- **Bottleneck Analysis** - Identify critical courses that unlock many others
- **Admin Panel** - Dashboard, course list/edit, stats, majors (admin users only)
- **Modern Responsive UI** - Bootstrap 5 with beautiful, mobile-friendly design

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: SQLite by default (`instance/smart_academic.db`); optional MySQL via environment variables
- **ML Models**: XGBoost, Random Forest, Gradient Boosting, Neural Networks
- **Frontend**: Bootstrap 5, jQuery
- **AI Chatbot**: OpenAI GPT (optional)

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure database (optional)

**Default — SQLite:** do nothing. The app creates `instance/smart_academic.db` when you run `scripts/setup_database.py` or when tables are initialized.

**Optional — MySQL:** set environment variables before running (do not commit real passwords):

```bash
export USE_MYSQL=1
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=your_user
export DB_PASSWORD=your_password
export DB_NAME=your_database
```

**Production:** set `SECRET_KEY` and `OPENAI_API_KEY` (optional) via environment variables; turn off `DEBUG` in `config.py` for real deployment.

### 3. Initialize Database

First, make sure your cleaned data files exist:
- `Data/merged_courses.csv`
- `Data/prerequisites.csv`

Then run:
```bash
python scripts/setup_database.py
```

This will:
- Drop all existing tables
- Create fresh database schema
- Load all courses and prerequisites

### 4. Train ML Models (Optional)

Retrain all models used by the app (1–3):
```bash
python ml/train_all_models.py
```

Or train individually after generating synthetic data (`python scripts/generate_synthetic_data.py`):
```bash
python ml/model1_course_difficulty.py
python ml/model2_semester_workload.py
python ml/model3_academic_risk.py
```

### 5. Run the Application

```bash
python app.py
```

The URL and port come from **`config.py`** (default **`http://localhost:5005`**).

## Project Structure

```
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── database/
│   ├── models.py               # SQLAlchemy models
│   └── db.py                   # Database connection
├── services/
│   ├── prerequisite_service.py  # Prerequisite logic
│   ├── ml_service.py          # ML model predictions
│   ├── recommendation_engine.py # Course recommendations
│   └── advisor.py             # AI advisor/chatbot
├── ml/
│   ├── train_all_models.py    # Train models 1–3
│   ├── model1_course_difficulty.py
│   ├── model2_semester_workload.py
│   ├── model3_academic_risk.py
│   └── models/                # Trained .pkl files (created by training)
├── scripts/
│   ├── setup_database.py       # init DB + load CSVs (uses load_data_to_db_fast)
│   ├── load_data_to_db_fast.py
│   ├── generate_synthetic_data.py
│   ├── create_course_csvs.py   # optional: refresh static/data course indexes
│   ├── extract_majors.py
│   ├── seed_admin.py
│   └── set_admin.py
├── templates/
│   ├── base.html
│   ├── index.html
│   └── dashboard.html
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       ├── main.js
│       └── dashboard.js
└── Data/
    ├── merged_courses.csv
    └── prerequisites.csv
```

## API Endpoints

### Authentication
- `POST /api/register` - Register new student
- `POST /api/login` - Login student
- `POST /api/logout` - Logout

### Student Profile
- `GET /api/student/profile` - Get profile
- `PUT /api/student/profile` - Update profile

### Courses
- `GET /api/courses/completed` - Get completed courses
- `POST /api/courses/completed` - Add completed course
- `GET /api/courses/unlocked` - Get unlocked courses
- `GET /api/courses/locked` - Get locked courses
- `GET /api/courses/search?q=query` - Search courses
- `GET /api/courses/<id>/difficulty` - Get difficulty prediction

### Recommendations
- `GET /api/recommendations?credits=15` - Get course recommendations

### Semester Planning
- `POST /api/semester/optimize` - Analyze semester plan

### Advisor
- `POST /api/advisor/chat` - Chat with AI advisor
- `GET /api/advisor/bottlenecks` - Get bottleneck courses

## Usage

1. **Register/Login**: Create an account or login
2. **Add Completed Courses**: Add courses you've already taken with grades
3. **View Recommendations**: Get AI-powered course recommendations
4. **Plan Semester**: Select courses and analyze semester difficulty
5. **Chat with Advisor**: Ask questions about your academic plan
6. **Check Bottlenecks**: Identify critical courses to prioritize

## ML Models

### Model 1: Course Difficulty Prediction
- **Algorithms**: Random Forest, XGBoost
- **Performance**: R² = 0.71, RMSE = 0.12
- **Purpose**: Predict individual course difficulty for a student

### Model 2: Semester Workload Estimation
- **Algorithms**: Gradient Boosting, Neural Network
- **Performance**: R² = 0.92, RMSE = 0.06
- **Purpose**: Estimate overall semester difficulty and overload risk

### Model 3 (API / dashboard)
- **Model 3**: Academic risk — `GET /api/student/academic-risk`  
See **`Documentaion And help/ML_MODELS.md`** for how each model maps to code paths.

## Admin

- **Create default admin** (run once after DB is set up):  
  `python scripts/seed_admin.py`  
  Creates user **admin** / **admin@gmail.com** / **admin123** with admin rights. Log in with username `admin` and password `admin123` to see the Admin link and access `/admin`.
- **Set another user as admin**:  
  `python scripts/set_admin.py <username>`

## Git / coursework commits

For a **3-week-style project timeline**, commit **several times per week** (small, logical changes)—not everything in one push. See **`PROJECT_GUIDE.md` → Section 2** for a day-by-day example plan.

**Guided commit messages (course workflow):** **`Documentaion And help/GIT_COMMIT_PLAN.md`** (copy-paste blocks). Optional: add your own `git_project_commit.sh` that reads `scripts/git_commit_plan.pipe`.

## Notes

- The system uses synthetic student data for ML training
- Real student data is only used for predictions, not model retraining
- OpenAI API key is optional (chatbot works with rule-based fallback)
- After clone, run **`python ml/train_all_models.py`** to create **`ml/models/*.pkl`** (otherwise the app uses safe fallbacks for predictions)
- PDF export requires `reportlab` (included in requirements.txt)

## Troubleshooting

**Database connection issues**
- **SQLite:** delete `instance/smart_academic.db` and run `python scripts/setup_database.py` again.
- **MySQL:** confirm `USE_MYSQL=1` and all `DB_*` env vars match your server; test with `mysql` CLI.

**Model Loading Issues:**
- Ensure model files exist in `ml/models/`
- Run training scripts if models are missing

**Import Errors:**
- Install all requirements: `pip install -r requirements.txt`
- Check Python version (3.8+)

## License

This project is for academic purposes.
