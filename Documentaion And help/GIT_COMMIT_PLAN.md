# Git commit plan — Smart Academic Planning

Work from the **project root**. Initialize once: `git init`  
Copy **one command block at a time** (each `# --- …` section: `git add` then `git commit`).  
If a path does not exist yet on your machine, skip it or wait until that milestone.

The schedule uses **2 calendar days per pair** of commits (21 steps → ~3 weeks). Adjust dates to your course.

---

## Days 1–2

```bash
# --- Day 1 · Step A — skeleton (chore: init)
git add README.md requirements.txt
# git add .gitignore   # uncomment when you have created it
git commit -m "chore: init repo with README and requirements.txt" \
  -m "First commit: project skeleton, README stub, requirements.txt, .gitignore basics"

# --- Day 2 · Step B — setup docs (docs)
git add README.md PROJECT_GUIDE.md config.py
git commit -m "docs: document local setup and environment variables" \
  -m "How to install deps, env vars (SECRET_KEY, DB, OPENAI), and run the app"
```

---

## Days 3–4

```bash
# --- Day 3 · Step C — database layer (feat)
git add database/models.py database/db.py config.py
git commit -m "feat: add SQLAlchemy models and db session helper" \
  -m "Database layer: models.py, db.py, SQLite or MySQL"

# --- Day 4 · Step D — load CSV pipeline (feat)
git add scripts/setup_database.py scripts/load_data_to_db_fast.py
git add Data/merged_courses.csv Data/prerequisites.csv
git commit -m "feat: load courses and prerequisites from CSV scripts" \
  -m "Data pipeline: setup/load scripts, merged_courses, prerequisites"
```

---

## Days 5–6

```bash
# --- Day 5 · Step E — Flask shell + static (feat)
git add app.py config.py
git add templates/base.html templates/index.html
git add static/css/style.css static/js/main.js
git commit -m "feat: Flask app entrypoint, base template, static assets" \
  -m "app.py skeleton, templates/base, static CSS/JS"

# --- Day 6 · Step F — auth API + pages (feat)
git add app.py templates/login.html templates/register.html
git commit -m "feat: register and login API with session cookies" \
  -m "Auth: register/login APIs, session, login & register pages"
```

---

## Days 7–8

```bash
# --- Day 7 · Step G — auth polish (fix)
git add app.py
git commit -m "fix: return clear error when username already exists" \
  -m "Polish auth validation and JSON error messages"

# --- Day 8 · Step H — dashboard + profile shell (feat)
git add app.py templates/dashboard.html templates/profile.html
git add static/js/dashboard.js static/js/profile.js
git commit -m "feat: student dashboard and profile page" \
  -m "Dashboard & profile routes, templates, user context"
```

---

## Days 9–10

```bash
# --- Day 9 · Step I — completed courses + GPA (feat)
git add app.py database/models.py database/db.py
git add templates/dashboard.html templates/profile.html static/js/dashboard.js static/js/profile.js
git commit -m "feat: completed courses CRUD and GPA recalculation" \
  -m "Student courses APIs, grade points, GPA update"

# --- Day 10 · Step J — locked / unlocked courses (feat)
git add app.py services/prerequisite_service.py services/course_cache.py
git add Data/courses_index.json Data/prerequisites_index.json
git commit -m "feat: unlocked and locked courses API" \
  -m "Prerequisite service over HTTP: completed vs available"
```

---

## Days 11–12

```bash
# --- Day 11 · Step K — prerequisite graph API (feat)
git add app.py services/prerequisite_graph.py services/prerequisite_service.py
git commit -m "feat: prerequisite graph endpoint" \
  -m "Graph JSON for UI (prerequisite_graph service)"

# --- Day 12 · Step L — semester planner (feat)
git add app.py services/recommendation_engine.py
git commit -m "feat: semester planner optimize endpoint" \
  -m "Semester plan POST, workload / difficulty analysis"
```

---

## Days 13–14

```bash
# --- Day 13 · Step M — difficulty ML (feat)
git add services/ml_service.py ml/model1_course_difficulty.py app.py
git add ml/train_all_models.py
git commit -m "feat: integrate course difficulty ML prediction" \
  -m "ml_service Model 1, difficulty API, fallbacks if .pkl missing"

# --- Day 14 · Step N — advisor chat (feat)
git add services/advisor.py app.py
git commit -m "feat: advisor chat endpoint and rule-based fallback" \
  -m "/api/advisor/chat, OpenAI optional"
```

---

## Days 15–16

```bash
# --- Day 15 · Step O — academic risk ML (feat)
git add ml/model3_academic_risk.py
git add services/ml_service.py app.py templates/dashboard.html static/js/dashboard.js
git commit -m "feat: academic risk prediction API and dashboard" \
  -m "Model 3 endpoint + AI Insights tab hooks"

# --- Day 16 · Step P — dashboard UI polish (style)
git add templates/dashboard.html static/js/dashboard.js static/css/style.css
git commit -m "style: dashboard tabs and responsive layout tweaks" \
  -m "UI: Bootstrap, charts, mobile"
```

---

## Days 17–18

```bash
# --- Day 17 · Step Q — marker docs (docs)
git add PROJECT_EXPLANATION.md PROJECT_GUIDE.md ML_MODELS.md diagrams/
git commit -m "docs: update PROJECT_EXPLANATION and PROJECT_GUIDE for markers" \
  -m "Technical narrative for course staff"

# --- Day 18 · Step R — README demo (docs)
git add README.md
git commit -m "docs: add demo steps and screenshots in README" \
  -m "Demo flow for presentation or report"
```

---

## Days 19–20

```bash
# --- Day 19 · Step S — export hardening (fix)
git add app.py templates/dashboard.html
git commit -m "fix: harden PDF or export edge cases" \
  -m "PDF/CSV export when data is empty or partial"

# --- Day 20 · Step T — git hygiene + scripts (chore)
git add .gitignore
git add scripts/git_project_commit.sh scripts/git_commit_plan.pipe GIT_COMMIT_PLAN.md
git add scripts/generate_synthetic_data.py scripts/create_course_csvs.py Data/README.md
git commit -m "chore: gitignore trained models and tidy scripts" \
  -m "Ignore ml/models/*.pkl if policy says so; clean scripts"
```

---

## Day 21 (hand-in)

```bash
# --- Day 21 · Step U — final README + tag (chore)
git add README.md GIT_COMMIT_PLAN.md Data/README.md PROJECT_GUIDE.md
git commit -m "chore: final README and tag v1.0-final submission note" \
  -m "Submission checklist; then tag hand-in"

git tag -a v1.0-final -m "EECE 490 / Smart Academic Planning submission"
# git push origin main
# git push origin v1.0-final
```

---

## What each step is about (quick reference)

| Step | Code | What you’re committing |
|:---:|:---:|:---|
| 1 | A | Repo skeleton: README, requirements, ignore rules |
| 2 | B | Install/run/env documentation |
| 3 | C | SQLAlchemy models + DB helper |
| 4 | D | CSV → DB scripts + `merged_courses` / `prerequisites` |
| 5 | E | Flask app shell, base template, static assets |
| 6 | F | Register/login APIs + pages |
| 7 | G | Auth validation polish |
| 8 | H | Dashboard + profile |
| 9 | I | Completed courses CRUD + GPA |
| 10 | J | Locked/unlocked courses via prerequisites |
| 11 | K | Prerequisite graph JSON |
| 12 | L | Semester planner / optimize |
| 13 | M | Course difficulty ML |
| 14 | N | Advisor chat |
| 15 | O | Academic risk (Model 3) API + dashboard |
| 16 | P | Dashboard UI polish |
| 17 | Q | PROJECT_* + diagrams for markers |
| 18 | R | README demo |
| 19 | S | PDF/CSV edge cases |
| 20 | T | .gitignore, helper scripts, data docs |
| 21 | U | Final docs + version tag |


The **copy-paste blocks above** are the main workflow; the script only supplies the same `-m` subject/body if you prefer not to type them.
