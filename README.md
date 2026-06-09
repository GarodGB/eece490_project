# AcademicPath — Option A ML Academic Planning System

AcademicPath is an **application-oriented machine learning system** for semester planning. It helps CCE/ECE/CSE students enter completed courses, set a target GPA, and receive a personalized semester plan that balances degree progress, GPA protection, prerequisite readiness, workload, and predicted course performance.

> Important scope note: this is a rigorous **ML-assisted prototype** trained on synthetic student outcomes and real catalogue/planning structure. It should not be presented as a validated AUB advising system trained on real AUB student records.

---

## Why this fits Option A

This project is not only a notebook model. It is a running web application with:

- a real student-facing workflow: register/login → completed courses → GPA goal → recommendations;
- explicit academic rules for eligibility: completed courses, prerequisites, program requirements, failed-course repair, credit limits;
- ML models for prediction/ranking: difficulty, workload, risk, success probability, expected grade;
- baseline-vs-ML evidence saved in reports;
- error/limitation discussion and responsible ML notes;
- Flask API/UI and Docker support.

### Real-world problem
Students often choose next-semester courses using informal advice, incomplete prerequisite knowledge, or a rough idea of what is “easy.” This can lead to overload, delayed graduation, GPA damage, or taking courses in a poor sequence.

### Decision supported
The system supports the decision:

> Which valid courses should this student take next semester, given their completed courses, strengths/weaknesses, target GPA, workload tolerance, and degree progress?

### Why non-AI alone is insufficient
A pure rule system can say whether a course is allowed, but it cannot personalize course fit using prior performance patterns, subject strengths, expected grade, workload pressure, and academic risk. AcademicPath therefore uses rules for **eligibility** and ML for **personalized ranking**.

---

## ML design

The final system uses five supervised models trained from the generated student-course history.

| Model | Task | Output used by recommender |
|---|---|---|
| Model 1 | Personalized course difficulty regression | Expected difficulty score/category |
| Model 2 | Semester workload regression | Predicted semester difficulty + overload risk |
| Model 3 | Future academic risk classification | Low/medium/high/critical academic risk |
| Model 4 | Course success classification | Probability of earning C+ or above |
| Model 5 | Expected grade regression | Expected AUB grade points out of 4.3 |

### Key ML features

The models use pre-attempt features only, including:

- prior GPA and recent average;
- prerequisite performance and completion ratio;
- subject/area strength and weakness indicators;
- course level, credits, lab/project status;
- prerequisite count/depth and course centrality;
- term load and workload tolerance;
- major/support/elective role;
- course topic profile inferred from title/description/catalogue tags.

The recommender then combines ML outputs with academic constraints to create a valid plan. Rules filter invalid candidates; ML scores and ranks valid candidates.

---

## AUB-style GPA handling

- `A+` is supported as **4.3** quality points for individual course grades.
- Cumulative GPA and simulated GPA are capped at **4.0**.
- Target GPA feasibility warnings are shown when the requested GPA cannot realistically be reached in one semester.

---

## Run locally on Windows PowerShell

Use Python 3.11 or 3.12.

Open the project folder:

```text
EECE 490 - Smart Academic Planning
```

Then run the commands one by one:

```powershell
python -m venv .venv
```

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --timeout 300 --prefer-binary
```

```powershell
.\.venv\Scripts\python.exe scripts\setup_database.py
```

```powershell
.\.venv\Scripts\python.exe ml\train_all_models.py --regenerate
```

```powershell
.\.venv\Scripts\python.exe app.py
```

Open the URL shown in the terminal, usually:

```text
http://127.0.0.1:5005
```

### Daily use after first setup

After the first setup, you usually only need:

```powershell
.\.venv\Scripts\python.exe app.py
```

Retrain only if you changed data, feature engineering, or ML code.

---


## AI Advisor

The AI Advisor is grounded in the student's saved profile. It can answer questions about:

- current GPA and completed credits;
- failed/weak courses and retake logic;
- strengths and weaknesses by course area;
- target-GPA feasibility;
- recommended courses and why they were selected;
- prerequisite status and course difficulty.

By default, the advisor uses deterministic project logic and the same ML/recommendation engine as the dashboard. If `OPENAI_API_KEY` is set, it can use an LLM fallback, but the prompt is grounded in the student's actual app data and instructed not to invent policies or course facts.

## Docker run

```powershell
docker compose up --build
```

The app runs inside a container and exposes the Flask web app. Local database files are mounted through the `instance/` volume.

---

## Important files

| File/folder | Purpose |
|---|---|
| `app.py` | Flask routes and API endpoints |
| `templates/` | UI pages |
| `static/` | CSS/JS assets |
| `database/` | SQLAlchemy models and DB connection |
| `Data/` | course catalogue, prerequisites, synthetic data |
| `scripts/setup_database.py` | initializes the database |
| `scripts/generate_synthetic_data.py` | builds synthetic training data |
| `ml/train_all_models.py` | trains all five ML models |
| `ml/model1_course_difficulty.py` | course difficulty model |
| `ml/model2_semester_workload.py` | semester workload model |
| `ml/model3_academic_risk.py` | future academic risk model |
| `ml/model4_course_success_probability.py` | course success model |
| `ml/model5_expected_grade.py` | expected grade model |
| `services/recommendation_engine.py` | final course ranking/recommendation logic |
| `services/ml_service.py` | runtime ML prediction helpers |
| `reports/` | ML metrics and quality reports |
| `docs/` | explanation, ML design, and final notes |

---

## Reports to cite in the project discussion

- `reports/final_ml_rigor_upgrade.json`
- `reports/ml_quality_gate.json`
- `reports/ml_strength_weakness_quality_gate.json`
- `docs/FINAL_ML_RIGOR_UPGRADE.md`
- `docs/STEP_FINAL_LOGICAL_RECOMMENDER_FIX.md`
- `docs/OPTION_A_FINAL_README.md`

---

## Limitations and responsible ML

1. **Synthetic outcomes:** real AUB student grades were not available. The system validates ML logic on synthetic student-course histories.
2. **Not an official advisor:** recommendations should support, not replace, human advising.
3. **Bias/fairness:** synthetic data assumptions can shape outputs; this is documented and should be discussed.
4. **Privacy:** student data is stored locally in SQLite for the prototype. A production version would require stronger authentication, encryption, and access controls.
5. **Robustness:** unusual student histories may produce uncertain recommendations; the UI flags unrealistic GPA targets and high-risk plans.

---

## Final positioning

AcademicPath should be presented as:

> A production-style, ML-assisted academic planning prototype that combines deterministic degree rules with personalized machine learning predictions to recommend feasible, GPA-aware semester plans.

Do **not** present it as:

> A fully validated AUB production system trained on real student outcomes.

## Optional OpenAI Advisor

The core ML system runs locally. The AI Advisor can optionally use OpenAI as a natural-language explanation layer.

Create a private `.env` file in the project root:

```env
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-4o-mini
ADVISOR_USE_OPENAI=true
```

Do not commit `.env` to GitHub. The project includes `.env.example` only.

The advisor is grounded: it receives only the student's saved academic record, target GPA, failed/weak courses, strengths/weaknesses, prerequisite/course status, and the current ML recommendation output. If the API key is missing or fails, the app automatically falls back to the local grounded advisor.
