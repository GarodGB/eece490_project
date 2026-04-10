# ML models 1–3 — where they are used

Models are numbered **1 through 3** in the order they matter for the running app (course → semester → risk).  
Runtime loading and prediction live in **`services/ml_service.py`**. Training lives under **`ml/`**; weights are saved under **`ml/models/`**.

---

## Model 1 — Course difficulty (regression)

| | |
|---|---|
| **Purpose** | Predict how hard a **single course** will be for the logged-in student (0–1 score + Easy/Medium/Hard). |
| **Trainer** | `ml/model1_course_difficulty.py` → `train_model1()` |
| **Artifacts loaded at runtime** | `ml/models/model1_xgboost.pkl`, `model1_info.pkl` |
| **Python API** | `predict_course_difficulty(student_id, course_id)` in `ml_service.py` |

**Used in the project via**

- **`app.py`** — `GET /api/courses/<id>/difficulty`, semester optimize, recommendations, ratings aggregates, export paths that include difficulty.
- **`services/recommendation_engine.py`** — difficulty-aware recommendations.
- **`services/advisor.py`** — chatbot / explanations; uses workload and difficulty indirectly.
- **`services/ml_service.predict_semester_workload`** — builds per-course difficulties for Model 2 features.
- **`services/ml_service.predict_academic_risk`** — calls `predict_course_difficulty` for recent courses.
- **Training**: **`ml/model2_semester_workload.py`** may load `model1_xgboost.pkl` to align features.

---

## Model 2 — Semester workload (regression)

| | |
|---|---|
| **Purpose** | Predict **semester_difficulty** from the set of planned courses + student stats; **overload_risk** is derived in code from credits, labs, tolerance, etc. |
| **Trainer** | `ml/model2_semester_workload.py` → `train_model2()` |
| **Artifacts** | `model2_gradient_boosting.pkl`, `model2_info.pkl`, optional `model2_scaler.pkl` |
| **Python API** | `predict_semester_workload(student_id, course_ids)` |

**Used in the project via**

- **`app.py`** — `POST /api/semester/optimize` and related semester-plan analysis.
- **`services/advisor.py`** — `explain_semester_difficulty`, chatbot “what-if” / projection paths.
- **`services/recommendation_engine.optimize_semester_plan`** (if it calls workload ML).

---

## Model 3 — Academic risk (classification)

| | |
|---|---|
| **Purpose** | Classify overall **academic risk** (e.g. Low / Medium / High / Critical) from recent grades, GPA trend, failures, and difficulty signals. |
| **Trainer** | `ml/model3_academic_risk.py` → `train_model3()` |
| **Artifacts** | `model3_xgboost.pkl` (plus `model3_gradient_boosting_risk.pkl` on disk; runtime uses XGBoost), `model3_info.pkl` |
| **Python API** | `predict_academic_risk(student_id)` |

**Used in the project via**

- **`app.py`** — `GET /api/student/academic-risk`.
- **`static/js/dashboard.js`** — AI Insights tab loads academic risk and renders it.

**Depends on** Model 1 (via `predict_course_difficulty` inside `predict_academic_risk`).

---

## Train all three

```bash
python ml/train_all_models.py
```
