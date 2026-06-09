# What I Did — Smart Academic Planning (EECE 490)

This file is a **plain-language log** of major work completed on the project: features, UX, docs, and checks. Use it for demos, reports, or hand-ins. Technical detail lives in **`docs/`** and **`README.md`**.

---

## 1. Goal-driven course recommendations

- **Problem:** Recommendations should not depend only on prerequisites; they should reflect **personal goals**.
- **What changed:**
  - **`services/recommendation_engine.py`** — Added **`_compute_goal_planning()`** so each plan uses **current GPA**, optional **target semester GPA**, and **workload tolerance** (0–1). Produces **`goal_mode`** (e.g. recovery, raise GPA, maintain, relaxed target), **credit/course caps**, **max Hard courses**, and **`easy_preference_weight`** to rank safer mixes when the student needs to raise GPA or has low tolerance.
  - **Scoring** — Strategy (**easy** / **balanced** / **fast**) is combined with goal-based **easy_boost** so “raise GPA” paths favor easier courses; high GPA + high tolerance + relaxed targets can allow heavier schedules.
  - **`app.py`** — `GET /api/recommendations` accepts optional query **`tolerance`** and **`target_gpa`** for one-off overrides (no DB write). Response **`planning_params`** includes **`goal_mode`**, **`current_gpa`**, **`easy_preference_weight`**, etc.

---

## 2. Dashboard: Recommendations tab

- **`templates/dashboard.html`** — “Your goals for this plan” block: **current GPA**, **target GPA**, **semester intensity** slider.
- **`static/js/dashboard.js`** — **Save goals & get recommendations** saves **`workload_tolerance`** and **`target_semester_gpa`** via profile API, then loads recommendations; **`syncRecommendationGoalsFields`** keeps fields aligned with profile; opening the tab refreshes goals from the server.
- User-facing summary shows **plan mode**, **GPA now**, **target**, **safety weight**, and caps.

---

## 3. Documentation cleanup

- Renamed folder **`Documentaion And help/`** → **`docs/`** (typo fixed, clearer paths).
- Rewrote root **`README.md`** (single structure: setup, venv note, verification commands, API highlights, links to **`docs/`**).
- Added **`docs/README.md`** as an index of technical documents.
- Updated **`PROJECT_GUIDE.md`**, **`docs/PROJECT_EXPLANATION.md`**, **`docs/TECHNICAL_REPORT.md`**, **`docs/QUESTIONS_FOR_INSTRUCTOR.md`**, and **`docs/GIT_COMMIT_PLAN.md`** so paths and descriptions match the current recommendation behavior and **`docs/`** layout.

---

## 4. Automated checks

- **`scripts/verify_advisor_scenarios.py`** — Registers a user, adds sample courses with semesters, checks **semester-timeline**, **insights**, rule-based **advisor** chat, **bottlenecks**, **course search**; guards for missing Flask with a clear message; **`_assert`** usage fixed.
- **`scripts/verify_plan_features.py`** — Tolerance-driven **planning_params**, prerequisite block, insights/timeline (unchanged purpose; still part of the smoke suite).

Run from project root (with venv activated or deps installed):

```bash
python3 scripts/verify_plan_features.py
python3 scripts/verify_advisor_scenarios.py
```

---

## 5. Other UX / product work (earlier in the project arc)

- Prerequisite errors surfaced with a **modal / message box** instead of only fleeting alerts (**`templates/base.html`**, **`static/js/main.js`**, **`static/js/dashboard.js`**).
- **Course catalog / browse** — Broader elective/gen-ed exposure and tagging where implemented in **`services/course_cache.py`** and related API routes.
- **Insights / advisor / semester journey** — Richer student context (timeline, insights fields, advisor prompts) in **`services/insights_service.py`**, **`services/advisor.py`**, and dashboard loads where wired.

*(Adjust this section if your branch differs.)*
