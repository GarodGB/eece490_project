# Smart Academic Planning — Project Guide

<<<<<<< HEAD
This guide is for **EECE 490 / team use**: a **detailed project explanation**, **discussion & exam-style questions**, and a **3-week Git commit plan** (spread commits across the term — not one dump at the end).

**Questions to ask your instructor (week by week)** → **`QUESTIONS_FOR_INSTRUCTOR.md`**.
=======
This guide is for **EECE 490 / team use**: a **detailed project explanation**, **discussion & exam-style questions**.

>>>>>>> origin/main

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

<<<<<<< HEAD
### 1.6 What was cleaned up (unused / duplicate)

- **`ml/backup/`** (removed earlier) — duplicate experimental trainers not wired to the running app.
- **`scripts/train_all_models.py`** — outdated entry point that only trained models 1–2; superseded by **`ml/train_all_models.py`**.
- **`explain_recommendation`** in `advisor.py` — never called from `app.py` or the frontend.
- **`init_db` import** in `app.py` — unused (DB reset lives in scripts such as `setup_database.py`).

Database models in **`database/models.py`** were **kept**: they all have **live API usage** in `app.py` (calendar, finance, study tools, etc.).

---

## 2. Git for a ~3-week uni project (commit often — not everything at the end)

For coursework, your history should show **steady progress**. **You cannot put the whole project in one final commit** and still look like you worked across the term—TAs and supervisors expect **many small commits** over **weeks**, not one “upload assignment” push.

### 2.1 How often to commit

| Guideline | Why |
|-----------|-----|
| **Most weekdays** — e.g. **3–5+ commits per week** when you’re actively building | Proves ongoing work; easy to roll back mistakes. |
| **At least every 2–3 days** if you’re swamped | Still better than 12 days of silence then 20 files at once. |
| **Multiple commits in one day** is fine | e.g. `fix: login redirect` then `feat: add wishlist API` — two logical steps. |
| **Push to remote** regularly | Local-only commits for weeks looks like last-minute work. |

Try to leave **`main`** in a **runnable** state when possible (`python app.py` after `pip install` + DB setup). If mid-refactor, say so in the commit body.

### 2.2 What counts as a “good” commit

- **One clear purpose** — not `final project` with everything.
- **Imperative subject line** (~50–72 chars), optional body:

```text
Add validation for semester plan credit limits

- Clamp credits to MIN/MAX from config
- Return 400 with message when over max
```

- **Small commits are valid**: docs, one bugfix, one template, `.gitignore`.

### 2.3 Three-week commit calendar (example + sample messages)

Use as a **checklist**. Target roughly **15–22 commits** over 3 weeks (teams can do more). Skip weekends if you want—**catch up mid-week** instead of piling everything into week 3.

#### Week 1 — Foundation

| Day | Focus | Example `git commit -m "..."` |
|-----|--------|--------------------------------|
| **D1** | Repo + deps | `chore: init repo with README and requirements.txt` |
| **D2** | Docs / config | `docs: document local setup and environment variables` |
| **D3** | Database | `feat: add SQLAlchemy models and db session helper` |
| **D4** | Data load | `feat: load courses and prerequisites from CSV scripts` |
| **D5** | Flask shell | `feat: Flask app entrypoint, base template, static assets` |
| **D6** | Auth | `feat: register and login API with session cookies` |
| **D7** | Fix / polish | `fix: return clear error when username already exists` |

#### Week 2 — Core product

| Day | Focus | Example commit message |
|-----|--------|-------------------------|
| **D8** | Dashboard | `feat: student dashboard and profile page` |
| **D9** | Courses / GPA | `feat: completed courses CRUD and GPA recalculation` |
| **D10** | Prerequisites | `feat: unlocked and locked courses API` |
| **D11** | Graph or recs | `feat: prerequisite graph endpoint` or `feat: recommendations API` |
| **D12** | Semester | `feat: semester planner optimize endpoint` |
| **D13** | ML / advisor | `feat: integrate course difficulty prediction` or `feat: advisor chat endpoint` |
| **D14** | Cleanup | `refactor: extract repeated JSON error responses` |

#### Week 3 — Finish line

| Day | Focus | Example commit message |
|-----|--------|-------------------------|
| **D15** | More ML / UI | `feat: academic risk dashboard widget` |
| **D16** | UX | `style: dashboard tabs and responsive layout tweaks` |
| **D17** | Report / docs | `docs: update PROJECT_EXPLANATION for markers` |
| **D18** | Demo | `docs: add demo script and screenshot placeholders in README` |
| **D19** | Bugs | `fix: PDF export when semester has no courses` |
| **D20** | Hygiene | `chore: gitignore ml/models/*.pkl and tidy scripts` |
| **D21** | Hand-in | `chore: tag v1.0-final and final README submission note` |

**If you fall behind:** merge two rows into one day, but **avoid** doing all of Week 1–3 in the last two days.

**Automated helper:** see **`GIT_COMMIT_PLAN.md`** and run **`./scripts/git_project_commit.sh list`** — then **`./scripts/git_project_commit.sh 5`** or **`./scripts/git_project_commit.sh E`** to `git add -A`, commit with the planned message + explanation, and `git push` (optional `DRY_RUN=1` / `SKIP_PUSH=1`).

### 2.4 Message prefixes (optional, course-friendly)

- `feat:` — new behavior users see  
- `fix:` — bugfix  
- `docs:` — README, reports, comments only  
- `refactor:` — code move, same behavior  
- `chore:` — deps, `.gitignore`, tooling  
- `test:` — tests only  

### 2.5 Branching (optional)

- `main` — always something you can demo  
- `feature/short-name` — one feature, merge when done  
- `git tag -a v1.0-final -m "EECE 490 submission"` before the deadline  

### 2.6 Before you push

- [ ] App starts (no import errors)  
- [ ] No real passwords / API keys in the diff  
- [ ] Large `.pkl` — follow course rules (**LFS** or ignore + “train locally”)  

---

## 3. Questions (discussion, demo prep, exam-style)

Use these for team meetings, supervisor check-ins, or written reports.

### 3.1 Product & users

1. Who is the **primary user** (e.g. ECE undergrad) and what is their **top task** in under 2 minutes?
2. What problems does this solve better than a **static PDF degree plan**?
3. How would you explain **overload risk** to a student who has never taken ML?

### 3.2 Data & prerequisites

4. How are prerequisites **represented** in the database vs in CSV files?
5. What happens if **circular prerequisites** exist in the data? Does the code assume a DAG?
6. How is **GPA** computed and when is it updated?

### 3.3 Machine learning

7. What are the **inputs** and **outputs** of Models 1 vs 2 vs 3?
8. Why does the app **still work** if `.pkl` files are missing?
9. What **ethical concerns** apply to difficulty/risk predictions (bias, false reassurance)?
10. How would you **evaluate** model quality on real student data (if you were allowed to use it)?

### 3.4 Software architecture

11. Why use a **course_cache** instead of querying the DB on every recommendation?
12. Where would you add **rate limiting** for the advisor chat API?
13. How does **admin** isolation work in `before_request`?

### 3.5 Security & privacy

14. What OWASP-style risks apply (SQL injection, XSS, session fixation, etc.) and what mitigations exist?
15. Should **email** be verified at registration? Why or why not?

### 3.6 Testing & DevOps

16. What **three automated tests** would you add first (unit / integration)?
17. How would you deploy this for a pilot (Docker, env vars, HTTPS)?

### 3.7 Presentation / demo script (short answers)

18. In 30 seconds: what is the **one screenshot** you must show?
19. What is a **known limitation** you will disclose honestly during demo?

---

## 4. Quick reference commands

```bash
# Dependencies
pip install -r requirements.txt

# Database (see README for your environment)
python scripts/setup_database.py

# Train ML models used by the app
python ml/train_all_models.py

# Run
python app.py
```

---

*Last updated to match repo cleanup: unused ML trainers removed; commit cadence documented; supervisor check-in questions live in **`QUESTIONS_FOR_INSTRUCTOR.md`**.*
=======




---
>>>>>>> origin/main
