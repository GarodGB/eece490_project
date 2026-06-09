# Smart Academic Planning — Technical report (code logic & algorithms)

This document is the **deep-dive companion** to **`PROJECT_EXPLANATION.md`**. It explains **why** the code is structured the way it is, **how** major algorithms behave, and **which file** owns each responsibility.

---

## 1. Architectural principles

| Principle | How it shows up in code |
|-----------|-------------------------|
| **Single HTTP entry** | Almost all routes live in **`app.py`**. It validates sessions, parses JSON/query params, calls **`get_db()`**, delegates to **`services/`**, returns `jsonify` or rendered templates. |
| **Business logic not in templates** | HTML only renders; **`static/js/dashboard.js`** calls REST APIs. |
| **Shared course/prerequisite truth in cache** | **`services/course_cache.py`** loads **`Data/courses_index.json`** (or `static/data/`) and **`prerequisites_index.json`**. Prerequisite **edges** for the graph and “what unlocks what” come from this layer; the **DB** holds `Course` / `Prerequisite` rows used for enrollment and admin. |
| **Lazy ML loading** | **`services/ml_service.py`** loads pickles on first prediction; missing files → **deterministic fallbacks** so the UI never crashes. |
| **Regression vs classification** | Models **1 and 2** predict continuous difficulty in **[0, 1]**; Model **3** predicts a **discrete risk class** with `predict_proba`. |

---

## 2. Configuration → database session

**File: `config.py`**

- **`USE_MYSQL`** (env): if truthy, **`database/db.py`** builds a SQLAlchemy engine with a PyMySQL **creator** callback; otherwise **SQLite** at **`instance/smart_academic.db`**.
- **`ML_MODELS_DIR`**: directory for **`model1_xgboost.pkl (compatibility filename; stores the selected tree-based model)`**, **`model2_gradient_boosting.pkl`**, **`model3_xgboost_risk.pkl (compatibility filename; stores the selected risk model)`**, plus `*_info.pkl` and optional **`model2_scaler.pkl`**.
- **`GRADE_POINTS`**, **`MIN_CREDITS` / `MAX_CREDITS`**: used when adding completed courses and validating semester suggestions.

**File: `database/db.py`**

- **`SessionLocal`**: scoped session factory. Callers must **`db.close()`** in a `finally` block after work (pattern used throughout **`app.py`** and services that query the DB).
- **`init_db()`**: **drops all tables** then creates them — only used from **`scripts/setup_database.py`**, not on every `app.py` start.
- **App startup** (`app.py`): **`Base.metadata.create_all`** ensures tables exist without wiping data.

---

## 3. Course cache (fast path for catalog + difficulty metadata)

**File: `services/course_cache.py`**

**Directory selection (at import time)**

1. If **`Data/courses_index.json`** or **`Data/courses_index.csv`** exists → use **`Data/`** for both course and prerequisite cache files.
2. Else → fall back to **`static/data/`** (same filenames).

**Load order**

- **Courses:** try **JSON** first (list of objects → dict by `course_code`), else **CSV** row → dict.
- **Prerequisites:** try **JSON** (map `course_code → [prereq codes]`), else **CSV** with columns `course`, `prerequisite` aggregated into the same map.

**Downstream helpers**

- **`get_course_by_code`**: O(1) dict lookup.
- **`get_prerequisites(course_code)`**: list of direct prerequisite codes (one hop; full transitive closure is **not** computed here — unlocking uses “all direct prereqs must be completed”).
- **`get_course_difficulty(course_code)`**: reads **`difficulty_score`** / **`difficulty_category`** from cache if present; otherwise heuristic from score.
- **`get_courses_by_subject` / `search_courses` / `get_all_courses`**: scan in memory over the cache (acceptable size for course catalog).

**Design note:** The **DB** mirrors catalog rows for FK integrity (`StudentCourse.course_id`). The **cache** adds **enriched fields** (e.g. difficulty from offline analysis) without a migration for every tweak.

---

## 4. Prerequisite and unlock logic

**File: `services/prerequisite_service.py`**

**`get_completed_courses(student_id)`**

- SQL join **`StudentCourse` ↔ `Course`** where **`status == 'completed'`** → set of **`course_code`** strings.

**`is_course_unlocked(student_id, course_code, completed_courses=None)`**

1. Load prerequisites via **`get_prerequisites(course_code)`** (cache).
2. If none → **unlocked**, no missing list.
3. Else **`missing = [p for p in prereqs if p not in completed]`** → unlocked iff empty.

**`get_unlocked_courses(student_id, filter_by_major=True, limit=150)`**

1. Load **student**; **`completed_courses`** set.
2. **If `filter_by_major` and student has major:**
   - Take all cache courses for **`subject == major`**.
   - Collect **every prerequisite code** referenced by those major courses.
   - Include prerequisite courses whose **subject** is in an allowed STEM list **or** the student’s major.
   - Merge into a deduplicated dict: **major courses** flagged **`is_major_course=True`**, prereq chain courses **`False`**.
3. **Else:** use **`get_all_courses()`** from cache.
4. **Sort** so major subject comes first, then by **`course_level`**, then code.
5. For each candidate: **skip** if completed, **skip** if any prerequisite not in **`completed_courses`**.
6. Return up to **`limit`** unlocked rows (dicts with metadata from cache).

**Logic summary:** Unlocking is **conjunctive** (all direct prereqs required). Major filtering **expands** the candidate set to include feeder gen-ed/STEM prereqs, not only courses whose subject equals the major.

---

## 5. Recommendation engine (goals + scoring + packing)

**File: `services/recommendation_engine.py`**

**`_compute_goal_planning(current_gpa, target_gpa, tol, target_credits, max_courses)`**

- Inputs: **current GPA**, optional **target semester GPA**, **tolerance** (0–1), requested credits/course cap.
- Outputs: **`goal_mode`** (e.g. `recovery`, `raise_gpa_strong`, `raise_gpa`, `maintain`, `relaxed_target`, `tolerance_only`), **`gpa_gap`**, **`credit_slack`**, **`effective_max_credits`**, **`effective_max_courses`**, **`max_hard_allowed`**, **`easy_preference_weight`** (0–1).
- Intent: if the student must **raise** GPA (positive gap) or is in **recovery** (low current GPA + ambitious target), **tighten** credit slack, **fewer** courses, and **cap Hard** sections; if goals are **relaxed** and GPA/tolerance are high, **allow** a heavier mix.

**`recommend_courses(student_id, target_credits, max_courses, term, override_target_gpa=None, override_tolerance=None)`**

1. Resolve **tolerance** and **target_gpa** from the student row; optional **overrides** apply only to this call (used by `GET /api/recommendations?...` without persisting).
2. **Eligible set:** **`get_unlocked_courses(..., filter_by_major=True)`** → filter completed / invalid credits; split major vs other; score a bounded pool.
3. **Per course:**
   - **`get_course_difficulty`** + optional **ML** blend (`predict_course_difficulty`).
   - Adjust **difficulty_score** for current GPA bands, **GPA vs target gap**, and tolerance (existing heuristics).
   - Rebucket **Easy / Medium / Hard** (thresholds 0.4 / 0.7; original Hard stays Hard).
   - **`base_score = 1.0 - difficulty_score`**, **`major_bonus`**, strategy branch (**easy** / **fast** / **balanced**).
   - Apply **`easy_boost`** / **`fast_easy`** using **`easy_preference_weight`** so safer plans rank higher when goals require it; **fast** still adds **`unlocks_count`** bonus.
4. **Sort** by **`recommendation_score`** descending.
5. **Greedy packing:** respect **`effective_max_credits`**, **`max_hard_allowed`**, buckets, then fill from top scores.

**`optimize_semester_plan(student_id, course_ids)`**

- Delegates to **`predict_semester_workload`** (**`ml_service`**), then maps outputs to **`difficulty_category`** and **`risk_category`** via thresholds on **`semester_difficulty`** and **`overload_risk`**.

---

## 6. Prerequisite graph API

**File: `services/prerequisite_graph.py`**

**`build_prerequisite_graph(student_id, major=None, limit_nodes=200)`**

1. **`completed`** = completed course codes.
2. **`prereq_cache`** = full map course → list of prereqs.
3. **Node universe:** all codes appearing as keys or values in cache.
4. **If `major` given:** restrict to courses **reachable from major subject** (union of major courses and their prerequisite closure), intersect with node universe.
5. **Cap** exploratory size: take **`limit_nodes * 2`** codes (order-dependent slice — acceptable heuristic for vis performance).
6. **Nodes:** for each code, attach **status** via **`is_course_unlocked`** using shared **`completed`** set: `completed` / `unlocked` / `locked`.
7. **Edges:** for each `(course, prereqs)` in cache, add edge **`prereq → course`** (direction matches “prerequisite points to dependent course” for typical DAG drawing).
8. **Sort** nodes: completed first, then unlocked, then locked; **truncate** to **`limit_nodes`** and filter edges to induced subgraph.

This feeds **`GET /api/prerequisite-graph`** for **vis-network** on the dashboard.

---

## 7. Machine learning service (inference logic)

**File: `services/ml_service.py`**

### 7.1 Model loading

- **`load_models()`** reads pickles into module globals once; on failure, models stay **`None`**.
- **Model 2** may use **`model2_scaler.pkl`** if **`model2_info['uses_scaler']`** is true.

### 7.2 Model 1 — course difficulty (regression)

**Function: `predict_course_difficulty(student_id, course_id)`**

**If `_model1` missing:** return neutral **`0.5` / `Medium` / confidence 0**.

**Feature vector (single row, 13 inputs)** — matches the **idea** of training (course + student + prior performance on any completed course):

1. `course_level / 500`
2. `prerequisite_count / 10`
3. `prerequisite_depth / 10`
4. `graph_centrality` (from catalog)
5. `credit_hours / 4`
6. `1` if lab else `0`
7. `student.gpa / 4`
8–9. `workload_tolerance` (duplicated in vector — placeholder for training dims)
10. `len(prior completed courses) / 50`
11. `avg(grade points of completed courses) / 4` — used as **proxy for prereq performance** at inference
12. `min(...)/4`
13. `count(nonzero grades)/10`

**Post-processing (rule layers on top of tree-based scikit-learn model output):**

- Clamp model output to **[0, 1]**.
- **Subject bumps** (e.g. MATH/PHYS/CHEM/CS/ECE): add up to **+0.20**.
- **Level bumps:** 200/300/400-level floors and increments.
- **Lab / prereq count** further increments.
- **Student GPA** slight nudge.
- **MATH/PHYS** and **ECE/CS/ENGR** floors at higher levels (force minimum difficulty).
- Map score to **Easy / Medium / Hard** by **0.4 / 0.7** thresholds.

So production difficulty is **learned signal + interpretable engineering rules** (stabilizes outputs for edge degrees).

### 7.3 Model 2 — semester workload (regression)

**Function: `predict_semester_workload(student_id, course_ids)`**

**If `_model2` missing:** return **heuristic** `semester_difficulty = 0.5` and **`overload_risk`** from **credit bands** and lab count only.

**When model present:**

1. For each `course_id`, load row, call **`predict_course_difficulty`** → collect difficulty scores.
2. Aggregate: **mean, max, variance** of difficulties; **total_credits**, **num courses**, **num labs**.
3. **Feature row:**
   `[avg_diff, max_diff, var, total_credits/18, n_courses/6, n_labs/3, gpa/4, workload_tol, workload_tol, n_courses/50]`
   then **optional scaler**.
4. **`semester_difficulty`** = clamp(model predict, 0, 1).
5. **`overload_risk`** = **separate heuristic** combining credit bands, **`avg_difficulty`**, **`workload_tolerance`**, penalty for **>5–6** courses and multiple labs — **not** the raw model output (model explains “hard semester”; risk encodes **load + tolerance**).

### 7.4 Model 3 — academic risk (classification)

**Function: `predict_academic_risk(student_id)`**

**Early exits:**

- No model → **Medium** with low score **0.3**.
- **&lt; 3** completed courses → **Low** risk (not enough signal).

**Features (13 dims):**

- Normalized **GPA**, **GPA trend slope** (linear fit on rolling windows of recent grade points), means/mins of recent grades, **fail / low-grade counts**, **mean/var of difficulty** on recent courses (each via **`predict_course_difficulty`** — **expensive** but ties risk to perceived hardness), **grade − difficulty gap**, **workload_tolerance** (twice), **count/50**.

**Output:**

- **`predict` → class id**; **`predict_proba` → `risk_score`** as probability of predicted class.
- Label map from **`model3_info['risk_levels']`** default `{0: Low, 1: Medium, 2: High, 3: Critical}`.
- **Rule-based `risk_factors` / `recommendations`** (GPA, failures, declining trend).

---

## 8. Training vs inference (Model 1 caveat)

**File: `ml/model1_course_difficulty.py`**

Training builds a supervised target **`difficulty_score = 1.0 - (grade_points/4)`** from synthetic enrollments and uses features including **`academic_ability`** and **`total_courses_completed`**.

**Runtime** **`ml_service.predict_course_difficulty`** uses a **slightly different 13D vector** (duplicated tolerance, counts from DB completed courses). This is a deliberate **approximation** so inference uses only **fields available on the live `Student` model** and completed history. For a thesis-quality report, you would **retrain** with the exact inference schema or add columns to **`Student`** to match training.

---

## 9. Synthetic data generation (ML training input)

**File: `scripts/generate_synthetic_data.py`**

- Reads **`Data/merged_courses.csv`** and **`Data/prerequisites.csv`** (or index) to respect **real prerequisite structure**.
- Simulates **students** and **student_course** rows with grades, semesters, abilities — outputs **`Data/synthetic/*.csv`**.
- **`ml/train_all_models.py`** runs **`train_model1/2/3`** in **`ml/`**, each consuming those CSVs plus catalog stats.

---

## 10. Frontend ↔ backend contract (dashboard)

**File: `static/js/dashboard.js`** (representative flows)

- **Recommendations:** `GET /api/recommendations?credits=&term=` → renders cards with difficulty badges.
- **Semester plan:** collects selected **DB course ids** → `POST /api/semester/optimize` with id list → shows workload + risk categories.
- **Graph:** `GET /api/prerequisite-graph` → **vis.Network** nodes/edges with colors by **`status`**.
- **AI Insights:** `GET /api/student/academic-risk` → Model 3 summary card.
- **Per-course difficulty:** `GET /api/courses/<id>/difficulty` uses **numeric DB id** on some paths and **course_code** on others — **check `app.py` for each route** when tracing a bug.

---

## 11. Security and session model (brief)

- **Login** sets **`session['student_id']`**; **admin** sets **`session['is_admin']`**.
- **`before_request`** in **`app.py`** blocks non-admins from **`/admin*`** routes.
- Passwords are **Werkzeug hashes**; never store plaintext.
- **OpenAI** key only in env; advisor falls back to **keyword rules** in **`advisor.py`** if unset.

---

## 12. File → responsibility quick map

| File | Responsibility |
|------|------------------|
| **`app.py`** | Routes, auth, CRUD orchestration, JSON responses |
| **`config.py`** | Paths, DB mode, secrets, business constants |
| **`database/models.py`** | ORM schema |
| **`database/db.py`** | Engine, session, `init_db`, `test_connection` |
| **`services/course_cache.py`** | In-memory catalog + prereq map from JSON/CSV |
| **`services/prerequisite_service.py`** | Unlock tests, unlocked course list |
| **`services/recommendation_engine.py`** | Scoring + greedy semester suggestions |
| **`services/prerequisite_graph.py`** | Graph payload for visualization |
| **`services/ml_service.py`** | Pickle load, feature build, predict 1–3 |
| **`services/advisor.py`** | Chat + explanations + bottlenecks |
| **`ml/model*.py`** | Offline training pipelines |
| **`scripts/setup_database.py`** | Reset DB + bulk CSV load |
| **`scripts/generate_synthetic_data.py`** | Train CSV generation |

---

## 13. Suggested citations for reports / presentations

- **“Unlocking”** = conjunctive satisfaction of **direct** prerequisites from **`prerequisites_index.json`**.
- **“Recommendation score”** = inverted difficulty + major bonus + strategy (**easy / balanced / fast**).
- **“Overload risk”** = heuristic layer combining **credits, model difficulty, tolerance, course count, labs** — see **`predict_semester_workload`** after the model output.
- **“Academic risk”** = multiclass tree-based scikit-learn model + **post-hoc** factor text.

For endpoint-level enumeration, see **`PROJECT_EXPLANATION.md` §5**; for per-model file/API mapping, see **`ML_MODELS.md`**.
