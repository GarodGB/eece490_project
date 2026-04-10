# Smart Academic Planning — Project Guide

This guide is for **EECE 490 / team use**: a **detailed project explanation**, **discussion & exam-style questions**.


For a concise technical walkthrough of modules and APIs, see **`PROJECT_EXPLANATION.md`**.  
**Where each ML model is used (Models 1–3)** → **`ML_MODELS.md`**.

---

## 1. Detailed project explanation

### 1.1 Purpose

**Smart Academic Planning** is a web application that helps engineering students:

- Record **completed courses** and **grades**, and track **GPA**
- See which courses are **unlocked** vs **locked** using a **prerequisite graph**
- Get **personalized course recommendations** (strategy: easy / balanced / fast)
- **Plan semesters** (credits, labs, predicted difficulty, overload risk)
- Use **ML-backed insights**: per-course difficulty, semester workload, and academic risk
- Use **study & life tools**: calendar, finances, scholarships, study sessions, goals, assignments, wishlist, notes, resources
- Talk to an **academic advisor chatbot** (OpenAI when `OPENAI_API_KEY` is set; otherwise rule-based answers)
- **Admins** manage courses and view stats via `/admin`

### 1.2 How the stack fits together

| Layer | Role |
|--------|------|
| **Browser** | Bootstrap 5 + jQuery; `dashboard.html` + `static/js/dashboard.js` call JSON APIs |
| **Flask (`app.py`)** | Sessions, routes, validation, orchestrates DB + services |
| **`database/`** | SQLAlchemy models (`models.py`), engine/session (`db.py`); SQLite by default or MySQL via env |
| **`services/`** | Prerequisites, recommendations, ML wrappers, advisor, course cache, prerequisite graph |
| **`ml/`** | Training scripts; trained artifacts live under **`ml/models/`** as `.pkl` files |
| **`Data/`** | `merged_courses.csv`, `prerequisites.csv` (and optional synthetic data for training) |

### 1.3 Data flow (typical student session)

1. User **registers** or **logs in** → row in `students`, session cookie stores `student_id`.
2. **Completed courses** → `student_courses` with grades → **GPA** updated on the student record.
3. **Prerequisite service** uses DB (and **course cache** loaded from DB/CSV) to compute **unlocked** and **locked** courses.
4. **Recommendations** combine eligibility, strategy, credits, and difficulty/workload signals.
5. **Semester planner** sends a list of course IDs → **`predict_semester_workload`** (Model 2) + explanations from **`explain_semester_difficulty`**.
6. **Per-course difficulty** → **`predict_course_difficulty`** (Model 1), optionally persisted or shown with **ratings** (`course_ratings`).
7. **`predict_academic_risk`** (Model 3) summarizes overall risk (with fallbacks if `.pkl` files are missing).

### 1.4 ML models actually used in production code (numbered 1–3)

Only these are loaded in **`services/ml_service.py`**. Full call graph (APIs, services, UI) is in **`ML_MODELS.md`**.

| ID | Purpose | Runtime artifacts (in `ml/models/`) |
|----|---------|--------------------------------------|
| **1** | Course difficulty for a student + course | `model1_xgboost.pkl`, `model1_info.pkl` |
| **2** | Semester difficulty from planned courses | `model2_gradient_boosting.pkl`, `model2_info.pkl`, optional `model2_scaler.pkl` |
| **3** | Academic risk (classification) | `model3_xgboost_risk.pkl`, `model3_info.pkl` |

**Train all of the above:**

```bash
python ml/train_all_models.py
```

### 1.5 Security & configuration notes

- **Secrets**: Use environment variables for `SECRET_KEY`, DB passwords, and `OPENAI_API_KEY`—do not commit real production credentials (the README may show placeholders; replace locally).
- **Admin users**: `scripts/seed_admin.py` / `scripts/set_admin.py` for elevated access; admins are restricted to admin UI and admin APIs.
- **Passwords**: Stored as Werkzeug password hashes, not plaintext.





---
