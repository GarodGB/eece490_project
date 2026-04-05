# Questions for your instructor (Dr. / course supervisor)

**How to use this:** Before each check-in, send **1–2 focused blocks** (not the whole file). Attach or link: a **one-page scope**, your **stack diagram** (browser → Flask → SQLAlchemy → services → ML), and note which models you train (**1–3**: difficulty, semester workload, academic risk). That context makes answers concrete.

---

## Week 1 — scope, rubric, and engineering constraints

**Deliverable boundaries**

- For full credit, do you require a **publicly runnable demo** (e.g. `python app.py` + setup script), or is a **recorded walkthrough** acceptable if deployment is fragile?
- Should the write-up include an explicit **system architecture** section (layers: HTTP API, ORM, prerequisite logic, ML inference), or is a high-level diagram enough?
- Our app bundles many **dashboard modules** (calendar, finances, study sessions, assignments, etc.). For grading, is that **one integrated product**, or should we **clearly mark** a “core” slice (auth, courses, prerequisites, planner, ML) vs “extensions”?

**Version control and process**

- What do you look for in **Git history**: commit **frequency**, **message quality** (`feat:` / `fix:`), or **logical grouping**? Any minimum you consider “too sparse”?
- If we use **synthetic data** for ML and **seeded CSV** for courses, should the report state **data provenance** and **limitations** explicitly (required subsection)?

**Privacy, ethics, and data**

- We store **student GPA, grades, and usage** in SQLite/MySQL. Do you want a short **threat model** or **privacy note** (who can access DB, no real student data in repo, env-based secrets)?
- For **ML outputs** (difficulty, risk): should we document **disclaimer** language (advisory only, not official academic advice) for the demo or report?

---

## Week 2 — architecture, APIs, and ML (technical depth)

**Backend and data model**

- Our **prerequisite** logic uses DB tables plus a **course cache** (JSON/CSV-style index) for fast lookup and difficulty metadata. Is that a **reasonable pattern** for a course project, or do you prefer we justify “cache vs single source of truth” in writing?
- **Prerequisite graph**: we assume a **DAG** (no cycles). If the dataset ever contained cycles, is documenting the assumption and **sanitization in the loader** sufficient, or do you expect **cycle detection** in code?
- We use **Flask sessions** (`student_id`) and **server-side** DB access. For EECE 490, is **session cookie + HTTPS in production** enough to mention, or do you want **CSRF** / token discussion for forms/APIs?

**REST surface and integration**

- Core JSON endpoints include **completed courses**, **unlocked/locked** lists, **semester optimize**, **prerequisite graph**, and **ML routes** (e.g. difficulty, academic risk). Should the report include a **table of endpoints** (method, path, purpose) as a deliverable, or optional appendix?
- **Admin vs student** routes: we gate `/admin` via session flags. Any expectation for **role-based access** write-up beyond describing `before_request` checks?

**Machine learning (Models 1–3)**

- **Model 1** (per-course difficulty, regression): Is reporting **train/validation split**, **one regression metric** (e.g. RMSE or MAE on a 0–1 target), and **feature list** sufficient, or do you want **cross-validation** / **feature importance** plots?
- **Model 2** (semester workload, regression with optional **scaler**): Do you care whether we explain **why** semester-level features (credits, count of labs, aggregated difficulties) are grouped that way vs per-course-only models?
- **Model 3** (academic risk, **classification**): Should we report **per-class metrics** (precision/recall or confusion matrix on validation) or is **accuracy + qualitative risk buckets** enough?
- **Training data**: We can train on **synthetic students** (`generate_synthetic_data.py`). Do you require any discussion of **sim-to-real gap** or **leakage** (e.g. ensuring prediction-time features are available in production)?
- **Artifacts**: We load **`pickle`** (`.pkl`) in `ml_service.py`. Is acknowledging **serialization risks** (trusted env only) and **version pinning** (scikit-learn/XGBoost versions in `requirements.txt`) adequate?
- **Fallback behavior**: If `.pkl` files are missing, the app returns **neutral defaults** (e.g. medium difficulty) so the UI still runs. Is that acceptable for partial deployment, or should the rubric require **all three models** present for full ML marks?

**Advisor / LLM**

- **OpenAI** is optional; we ship a **rule-based** advisor fallback. Should the write-up compare **latency, cost, and failure modes** (rate limits, no API key) in a short subsection?

---

## Week 3 — evaluation, documentation, and demo

**Documentation set**

- We maintain **`README.md`** (install/run), **`PROJECT_EXPLANATION.md`** (behavior and flow), **`ML_MODELS.md`** (model-to-code map). What **minimum depth** do you want in the main report vs “appendix” (e.g. full API list, full DB schema)?
- Should **reproducibility** be spelled out as a checklist: `pip install -r requirements.txt` → `setup_database.py` → `train_all_models.py` → `app.py`?

**Demo and validation**

- For the live demo, do you prefer we show **one end-to-end path** (register → add grades → unlock graph → semester plan → ML panel) or **breadth** across tabs?
- Are **screenshots** of the prerequisite **graph visualization** and **academic risk** card sufficient if network fails, or must everything be live?

**Submission artifacts**

- **Trained models**: Submit **`ml/models/*.pkl`** in-repo, **Git LFS**, or **omit** and only submit training instructions? Any **size limits** for the LMS?
- If we **exclude** pickles, will you **run** `python ml/train_all_models.py` during marking, and is **CPU-only** training time acceptable?

---

## Week 4 (or final week) — rubric alignment and final review

**Grading clarity**

- Which rubric rows are **most often under-documented** (testing, security, ML evaluation, user study)? Where should we add **one extra paragraph** to be safe?
- Is **automated testing** (even a few `pytest` tests on prerequisite logic or API smoke tests) expected or bonus?

**Presentation**

- Time limit and format: **live demo + 2–3 slides** vs **slide-only**?
- Do you expect a **single architecture diagram** showing **Flask routes → services → `ml_service` → pickle loaders** and **SQLAlchemy**?

**Final technical sanity check**

- If we stayed on **SQLite** for the project, is stating **“production would use PostgreSQL/MySQL + migrations”** enough, or do you require **MySQL** in the submitted version?
- Any requirement to discuss **known bugs**, **TODOs**, or **deferred features** explicitly in the conclusion?

---

## Optional one-liners (quick email)

Use when you only have room for a single question:

- *“Does our three-model scope (difficulty, semester workload, risk) meet the EECE 490 ML bar if synthetic data + validation metrics are documented?”*
- *“Is pickle-based model loading acceptable with pinned versions, or do you prefer ONNX/Joblib-only?”*
- *“Should the report treat the prerequisite graph as a formal DAG with documented edge semantics?”*

---

See also **`PROJECT_GUIDE.md`** §3 for discussion-style questions (team prep / exam-style), separate from these supervisor check-ins.
