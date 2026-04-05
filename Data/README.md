# Data folder

## Files kept here (what each is for)

| File | Purpose |
|------|---------|
| **`merged_courses.csv`** | Canonical course catalog (codes, titles, credits, graph metrics, etc.). Loaded into the DB via **`scripts/load_data_to_db_fast.py`** (called from **`scripts/setup_database.py`**), used by ML and `app.py`. |
| **`prerequisites.csv`** | Raw prerequisite edges (`course`, `prerequisite`). Source for the DB and for `scripts/create_course_csvs.py` / synthetic data generation. |
| **`courses_index.json`** | **App cache:** list of course objects (includes difficulty fields). Read by `services/course_cache.py` for fast lookup, search, and difficulty without hitting the database. |
| **`prerequisites_index.json`** | **App cache:** map `course_code → [prerequisite codes]`. Read by `services/course_cache.py` for prerequisite checks and planning. |
| **`majors.json`** | Major / program metadata for the UI (`app.py` prefers `Data/majors.json`, with fallback to `static/majors.json`). |
| **`synthetic/synthetic_students.csv`** | Synthetic student profiles for ML training (with `synthetic_student_courses.csv`). |
| **`synthetic/synthetic_student_courses.csv`** | Synthetic enrollment + grades / timing features per student-course pair for ML models. |

Regenerate synthetic data with `python scripts/generate_synthetic_data.py` (see main `README.md`).

---

## Removed from this folder (and what they were for)

These were **redundant or unused** in the current pipeline; the app and ML training do not depend on them.

| Removed | What it was for |
|---------|-----------------|
| **`courses_index.csv`** | Tabular duplicate of **`courses_index.json`**. The Flask app loads JSON first via `course_cache.py`; keeping both formats duplicated the same catalog and extra maintenance. CSV indexes for tooling still live under **`static/data/`** when produced by `scripts/create_course_csvs.py`. |
| **`prerequisites_index.csv`** | Row-per-edge duplicate of **`prerequisites_index.json`**. The app uses the JSON map only; the CSV was a fallback the JSON already replaces. |
| **`student_grades.csv`** (under `Data/`, removed) | Was an optional offline grade dump; the app and **`ml/train_all_models.py`** use **`Data/synthetic/`** only. A copy may still exist under **`static/data/`** for manual experiments and can be deleted if unused. |
