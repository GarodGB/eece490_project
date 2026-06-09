import pickle
import warnings
from pathlib import Path
from typing import Dict, Any, List, Optional

import numpy as np

warnings.filterwarnings("ignore")

from database.db import get_db
from database.models import Course, Student

try:
    from database.models import StudentCourse
except Exception:
    StudentCourse = None


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
ML_MODELS_DIR = BASE_DIR / "ml" / "models"

MODEL1_RF_FILE = ML_MODELS_DIR / "model1_random_forest.pkl"
MODEL1_XGB_FILE = ML_MODELS_DIR / "model1_xgboost.pkl"
MODEL1_INFO_FILE = ML_MODELS_DIR / "model1_info.pkl"

MODEL2_GB_FILE = ML_MODELS_DIR / "model2_gradient_boosting.pkl"
MODEL2_NN_FILE = ML_MODELS_DIR / "model2_neural_network.pkl"
MODEL2_SCALER_FILE = ML_MODELS_DIR / "model2_scaler.pkl"
MODEL2_INFO_FILE = ML_MODELS_DIR / "model2_info.pkl"

MODEL3_XGB_FILE = ML_MODELS_DIR / "model3_xgboost_risk.pkl"
MODEL3_GB_FILE = ML_MODELS_DIR / "model3_gradient_boosting_risk.pkl"
MODEL3_INFO_FILE = ML_MODELS_DIR / "model3_info.pkl"

MODEL4_RF_FILE = ML_MODELS_DIR / "model4_random_forest_success.pkl"
MODEL4_GB_FILE = ML_MODELS_DIR / "model4_gradient_boosting_success.pkl"
MODEL4_INFO_FILE = ML_MODELS_DIR / "model4_info.pkl"
# ============================================================
# HELPERS
# ============================================================

def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return low


def _load_pickle(path: Path):
    if not path.exists():
        return None

    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception as e:
        print(f"[ML WARNING] Could not load {path.name}: {e}")
        return None


def _difficulty_category(score: float) -> str:
    score = _clamp(score)
    if score < 0.40:
        return "Easy"
    if score < 0.70:
        return "Medium"
    return "Hard"


def _semester_difficulty_category(score: float) -> str:
    score = _clamp(score)
    if score < 0.33:
        return "Easy"
    if score < 0.67:
        return "Moderate"
    return "Challenging"


def _risk_category(score: float) -> str:
    score = _clamp(score)
    if score < 0.30:
        return "Low"
    if score < 0.60:
        return "Medium"
    if score < 0.80:
        return "High"
    return "Critical"


def _get_completed_student_courses(db, student_id: int):
    if StudentCourse is None:
        return []

    try:
        return (
            db.query(StudentCourse)
            .filter(StudentCourse.student_id == student_id)
            .all()
        )
    except Exception:
        return []


def _get_completed_grade_points(db, student_id: int) -> List[float]:
    rows = _get_completed_student_courses(db, student_id)
    grades = []

    for row in rows:
        gp = getattr(row, "grade_points", None)
        status = str(getattr(row, "status", "") or "").lower()

        if gp is None:
            continue

        if status and status not in {"completed", "passed", "done"}:
            continue

        grades.append(_safe_float(gp, 3.0))

    return grades


def _student_total_completed(db, student_id: int, student: Student) -> int:
    val = getattr(student, "total_courses_completed", None)

    if val is not None:
        return _safe_int(val, 0)

    rows = _get_completed_student_courses(db, student_id)
    return len(rows)


def _course_is_lab(course: Course) -> int:
    val = getattr(course, "is_lab", 0)

    if isinstance(val, str):
        return 1 if val.lower() in {"1", "true", "yes", "lab"} else 0

    return 1 if bool(val) else 0


def _course_level(course: Course) -> int:
    level = getattr(course, "course_level", None)

    if level is not None:
        return _safe_int(level, 100)

    code = str(getattr(course, "course_code", "") or "")
    digits = "".join(ch for ch in code if ch.isdigit())

    if len(digits) >= 3:
        return _safe_int(digits[:3], 100)

    return 100


def _course_credit_hours(course: Course) -> float:
    return _safe_float(getattr(course, "credit_hours", 3.0), 3.0)


def _course_prereq_count(course: Course) -> int:
    return _safe_int(getattr(course, "prerequisite_count", 0), 0)


def _course_prereq_depth(course: Course) -> int:
    return _safe_int(getattr(course, "prerequisite_depth", 0), 0)


def _course_graph_centrality(course: Course) -> float:
    return _safe_float(getattr(course, "graph_centrality", 0.0), 0.0)


def _temporary_student_values(
    student: Student,
    override_tolerance: Optional[float],
    override_gpa: Optional[float],
):
    if override_tolerance is not None:
        student.workload_tolerance = _clamp(override_tolerance)

    if override_gpa is not None:
        student.gpa = max(0.0, min(4.0, _safe_float(override_gpa, 3.0)))

    return student


# ============================================================
# MODEL 1: COURSE DIFFICULTY
# ============================================================

def _build_model1_features(db, student: Student, course: Course) -> np.ndarray:
    student_id = _safe_int(getattr(student, "id", 0), 0)

    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _safe_float(getattr(student, "workload_tolerance", 0.5), 0.5)
    ability = _safe_float(getattr(student, "academic_ability", gpa / 4.0), gpa / 4.0)

    grades = _get_completed_grade_points(db, student_id)
    avg_prereq_grade = float(np.mean(grades)) if grades else 3.0
    min_prereq_grade = float(np.min(grades)) if grades else 3.0
    total_completed = _student_total_completed(db, student_id, student)

    features = np.array([[
        _course_level(course) / 500.0,
        _course_prereq_count(course) / 10.0,
        _course_prereq_depth(course) / 10.0,
        _course_graph_centrality(course),
        _course_credit_hours(course) / 4.0,
        _course_is_lab(course),
        gpa / 4.0,
        ability,
        tolerance,
        total_completed / 50.0,
        avg_prereq_grade / 4.0,
        min_prereq_grade / 4.0,
        len(grades) / 10.0,
    ]], dtype=float)

    return features


def _heuristic_course_difficulty(student: Student, course: Course) -> float:
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _safe_float(getattr(student, "workload_tolerance", 0.5), 0.5)

    level = _course_level(course)
    credits = _course_credit_hours(course)
    prereqs = _course_prereq_count(course)
    depth = _course_prereq_depth(course)
    is_lab = _course_is_lab(course)

    difficulty = 0.16

    if level >= 400:
        difficulty += 0.34
    elif level >= 300:
        difficulty += 0.26
    elif level >= 200:
        difficulty += 0.16
    else:
        difficulty += 0.07

    difficulty += min(0.18, prereqs * 0.04)
    difficulty += min(0.12, depth * 0.03)
    difficulty += max(0.0, credits - 3.0) * 0.06

    if is_lab:
        difficulty += 0.08

    if gpa >= 3.7:
        difficulty -= 0.13
    elif gpa >= 3.3:
        difficulty -= 0.08
    elif gpa < 2.5:
        difficulty += 0.14
    elif gpa < 3.0:
        difficulty += 0.07

    # Course difficulty should change a little with tolerance, not huge.
    difficulty *= (1.08 - 0.18 * _clamp(tolerance))

    return _clamp(difficulty)


def predict_course_difficulty(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()

    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()

        if not student or not course:
            return None

        student = _temporary_student_values(student, override_tolerance, override_gpa)

        heuristic_score = _heuristic_course_difficulty(student, course)

        model_info = _load_pickle(MODEL1_INFO_FILE)
        best_model_name = "XGBoost"

        if isinstance(model_info, dict):
            best_model_name = str(model_info.get("best_model", "XGBoost"))

        model = None
        model_used = "Dynamic heuristic fallback"

        if best_model_name.lower().startswith("random"):
            model = _load_pickle(MODEL1_RF_FILE)
            model_used = "Model 1: Random Forest Course Difficulty"
        else:
            model = _load_pickle(MODEL1_XGB_FILE)
            model_used = "Model 1: XGBoost Course Difficulty"

        if model is not None:
            try:
                X = _build_model1_features(db, student, course)
                model_score = _clamp(float(model.predict(X)[0]))

                # Blend model + dynamic heuristic so UI reacts to GPA/tolerance.
                difficulty = _clamp(0.65 * model_score + 0.35 * heuristic_score)

                return {
                    "difficulty_score": round(difficulty, 4),
                    "difficulty_category": _difficulty_category(difficulty),
                    "model_used": model_used,
                    "source": "ml_model_blended",
                    "raw_model_score": round(model_score, 4),
                    "dynamic_score": round(heuristic_score, 4),
                }

            except Exception as e:
                print(f"[ML WARNING] Model 1 prediction failed: {e}")

        return {
            "difficulty_score": round(heuristic_score, 4),
            "difficulty_category": _difficulty_category(heuristic_score),
            "model_used": "Model 1: Dynamic Course Difficulty Fallback",
            "source": "fallback",
            "dynamic_score": round(heuristic_score, 4),
        }

    finally:
        db.close()


# ============================================================
# MODEL 2: SEMESTER WORKLOAD
# ============================================================

def _build_semester_features(
    db,
    student: Student,
    courses: List[Course],
    course_difficulties: List[float],
) -> np.ndarray:
    student_id = _safe_int(getattr(student, "id", 0), 0)

    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _safe_float(getattr(student, "workload_tolerance", 0.5), 0.5)
    ability = _safe_float(getattr(student, "academic_ability", gpa / 4.0), gpa / 4.0)
    total_completed = _student_total_completed(db, student_id, student)

    total_credits = sum(_course_credit_hours(c) for c in courses)
    num_courses = len(courses)
    num_labs = sum(_course_is_lab(c) for c in courses)

    avg_diff = float(np.mean(course_difficulties)) if course_difficulties else 0.5
    max_diff = float(np.max(course_difficulties)) if course_difficulties else 0.5
    var_diff = float(np.var(course_difficulties)) if len(course_difficulties) > 1 else 0.0

    features = np.array([[
        avg_diff,
        max_diff,
        var_diff,
        total_credits / 18.0,
        num_courses / 6.0,
        num_labs / 3.0,
        gpa / 4.0,
        tolerance,
        ability,
        total_completed / 50.0,
    ]], dtype=float)

    return features


def _heuristic_semester_workload(
    student: Student,
    courses: List[Course],
    difficulties: List[float],
) -> Dict[str, Any]:
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))

    total_credits = sum(_course_credit_hours(c) for c in courses)
    num_courses = len(courses)
    num_labs = sum(_course_is_lab(c) for c in courses)

    avg_diff = float(np.mean(difficulties)) if difficulties else 0.5
    max_diff = float(np.max(difficulties)) if difficulties else 0.5
    hard_count = len([d for d in difficulties if d >= 0.70])
    medium_count = len([d for d in difficulties if 0.40 <= d < 0.70])

    credit_pressure = _clamp(total_credits / 18.0)
    course_pressure = _clamp(num_courses / 6.0)
    lab_pressure = _clamp(num_labs / 3.0)
    hard_pressure = _clamp(hard_count / 3.0)
    medium_pressure = _clamp(medium_count / 5.0)

    if gpa < 2.5:
        gpa_risk = 0.30
    elif gpa < 3.0:
        gpa_risk = 0.18
    elif gpa < 3.4:
        gpa_risk = 0.08
    elif gpa < 3.7:
        gpa_risk = -0.04
    else:
        gpa_risk = -0.11

    # Stronger tolerance effect so demo visibly changes.
    tolerance_relief_difficulty = 0.36 * tolerance
    tolerance_relief_risk = 0.42 * tolerance

    semester_difficulty = (
        0.34 * avg_diff
        + 0.18 * max_diff
        + 0.20 * credit_pressure
        + 0.11 * course_pressure
        + 0.08 * lab_pressure
        + 0.07 * hard_pressure
        + 0.04 * medium_pressure
        + gpa_risk
        - tolerance_relief_difficulty
        + 0.18
    )

    overload_risk = (
        0.28 * credit_pressure
        + 0.21 * avg_diff
        + 0.15 * max_diff
        + 0.13 * course_pressure
        + 0.10 * lab_pressure
        + 0.08 * hard_pressure
        + gpa_risk
        - tolerance_relief_risk
        + 0.16
    )

    semester_difficulty = _clamp(semester_difficulty)
    overload_risk = _clamp(overload_risk)

    return {
        "semester_difficulty": round(semester_difficulty, 4),
        "overload_risk": round(overload_risk, 4),
        "difficulty_category": _semester_difficulty_category(semester_difficulty),
        "risk_category": _risk_category(overload_risk),
        "total_credits": round(total_credits, 2),
        "num_courses": num_courses,
        "num_labs": int(num_labs),
        "avg_course_difficulty": round(avg_diff, 4),
        "max_course_difficulty": round(max_diff, 4),
        "hard_courses": hard_count,
        "medium_courses": medium_count,
        "model_used": "Model 2: Dynamic Semester Workload Engine",
        "source": "dynamic_fallback",
    }


def predict_semester_workload(
    student_id: int,
    course_ids: List[int],
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()

    try:
        student = db.query(Student).filter(Student.id == student_id).first()

        if not student:
            return None

        student = _temporary_student_values(student, override_tolerance, override_gpa)

        courses = []
        for cid in course_ids or []:
            course = db.query(Course).filter(Course.id == cid).first()
            if course:
                courses.append(course)

        if not courses:
            return {
                "semester_difficulty": 0.0,
                "overload_risk": 0.0,
                "difficulty_category": "Easy",
                "risk_category": "Low",
                "total_credits": 0.0,
                "num_courses": 0,
                "num_labs": 0,
                "avg_course_difficulty": 0.0,
                "max_course_difficulty": 0.0,
                "model_used": "No courses selected",
                "source": "empty",
            }

        difficulties = []
        for course in courses:
            diff_result = predict_course_difficulty(
                student_id,
                course.id,
                override_tolerance=override_tolerance,
                override_gpa=override_gpa,
            )

            if diff_result and diff_result.get("difficulty_score") is not None:
                difficulties.append(_safe_float(diff_result["difficulty_score"], 0.5))
            else:
                difficulties.append(_heuristic_course_difficulty(student, course))

        dynamic_result = _heuristic_semester_workload(student, courses, difficulties)

        model_info = _load_pickle(MODEL2_INFO_FILE)

        best_model_name = "Gradient Boosting"
        uses_scaler = False

        if isinstance(model_info, dict):
            best_model_name = str(model_info.get("best_model", "Gradient Boosting"))
            uses_scaler = bool(model_info.get("uses_scaler", False))

        model = None
        model_used = dynamic_result["model_used"]

        if "neural" in best_model_name.lower():
            model = _load_pickle(MODEL2_NN_FILE)
            model_used = "Model 2: Neural Network Semester Workload"
        else:
            model = _load_pickle(MODEL2_GB_FILE)
            model_used = "Model 2: Gradient Boosting Semester Workload"

        if model is not None:
            try:
                X = _build_semester_features(db, student, courses, difficulties)

                if uses_scaler:
                    scaler = _load_pickle(MODEL2_SCALER_FILE)
                    if scaler is not None:
                        X = scaler.transform(X)

                model_difficulty = _clamp(float(model.predict(X)[0]))

                # Blend model + dynamic result so inputs visibly affect the demo.
                semester_difficulty = _clamp(
                    0.35 * model_difficulty
                    + 0.65 * dynamic_result["semester_difficulty"]
                )

                overload_risk = _clamp(
                    0.72 * dynamic_result["overload_risk"]
                    + 0.18 * semester_difficulty
                    + 0.10 * _clamp(sum(_course_credit_hours(c) for c in courses) / 18.0)
                )

                return {
                    **dynamic_result,
                    "semester_difficulty": round(semester_difficulty, 4),
                    "overload_risk": round(overload_risk, 4),
                    "difficulty_category": _semester_difficulty_category(semester_difficulty),
                    "risk_category": _risk_category(overload_risk),
                    "model_used": model_used,
                    "source": "ml_model_blended",
                    "raw_model_difficulty": round(model_difficulty, 4),
                    "dynamic_difficulty": dynamic_result["semester_difficulty"],
                    "dynamic_overload_risk": dynamic_result["overload_risk"],
                }

            except Exception as e:
                print(f"[ML WARNING] Model 2 prediction failed: {e}")

        return dynamic_result

    finally:
        db.close()


# ============================================================
# MODEL 3: ACADEMIC RISK
# ============================================================

def _build_model3_features(db, student: Student) -> np.ndarray:
    student_id = _safe_int(getattr(student, "id", 0), 0)

    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _safe_float(getattr(student, "workload_tolerance", 0.5), 0.5)
    ability = _safe_float(getattr(student, "academic_ability", gpa / 4.0), gpa / 4.0)
    total_completed = _student_total_completed(db, student_id, student)

    grades = _get_completed_grade_points(db, student_id)
    recent = grades[-10:] if grades else []

    avg_grade = float(np.mean(grades)) if grades else gpa
    avg_recent = float(np.mean(recent)) if recent else gpa
    min_recent = float(np.min(recent)) if recent else gpa

    failed_count = len([x for x in recent if x < 1.0])
    low_grade_count = len([x for x in recent if x < 2.0])

    if len(recent) >= 4:
        y = np.array(recent, dtype=float)
        x = np.arange(len(y), dtype=float)
        try:
            gpa_trend_slope = float(np.polyfit(x, y, 1)[0])
        except Exception:
            gpa_trend_slope = 0.0
    else:
        gpa_trend_slope = 0.0

    avg_difficulty = _clamp(1.0 - avg_recent / 4.0)
    difficulty_variance = float(np.var([1.0 - g / 4.0 for g in recent])) if len(recent) > 1 else 0.0
    performance_vs_difficulty = avg_recent / 4.0 - avg_difficulty

    features = np.array([[
        gpa / 4.0,
        gpa_trend_slope,
        avg_grade / 4.0,
        avg_recent / 4.0,
        min_recent / 4.0,
        failed_count / 10.0,
        low_grade_count / 10.0,
        avg_difficulty,
        difficulty_variance,
        performance_vs_difficulty,
        ability,
        tolerance,
        total_completed / 50.0,
    ]], dtype=float)

    return features


def _heuristic_academic_risk(student: Student, db) -> Dict[str, Any]:
    student_id = _safe_int(getattr(student, "id", 0), 0)

    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))

    grades = _get_completed_grade_points(db, student_id)
    recent = grades[-10:] if grades else []

    avg_recent = float(np.mean(recent)) if recent else gpa
    failed_count = len([x for x in recent if x < 1.0])
    low_grade_count = len([x for x in recent if x < 2.0])

    risk = 0.18

    if gpa < 2.0:
        risk += 0.52
    elif gpa < 2.5:
        risk += 0.36
    elif gpa < 3.0:
        risk += 0.20
    elif gpa < 3.4:
        risk += 0.08
    elif gpa >= 3.7:
        risk -= 0.10

    if avg_recent < 2.0:
        risk += 0.30
    elif avg_recent < 2.5:
        risk += 0.20
    elif avg_recent < 3.0:
        risk += 0.09

    risk += min(0.24, failed_count * 0.12)
    risk += min(0.20, low_grade_count * 0.05)

    # Stronger tolerance relief for visible demo behavior.
    risk -= 0.22 * tolerance

    risk = _clamp(risk)

    risk_name = _risk_category(risk)

    return {
                "risk_score": round(risk, 4),
                "risk_level": risk_name,
                    "risk_category": risk_name,
                "model_used": "Model 3: Dynamic Academic Risk Engine",
                 "source": "dynamic_fallback",
     }


def predict_academic_risk(
    student_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()

    try:
        student = db.query(Student).filter(Student.id == student_id).first()

        if not student:
            return None

        student = _temporary_student_values(student, override_tolerance, override_gpa)

        dynamic_result = _heuristic_academic_risk(student, db)

        model_info = _load_pickle(MODEL3_INFO_FILE)

        best_model_name = "XGBoost"
        if isinstance(model_info, dict):
            best_model_name = str(model_info.get("best_model", "XGBoost"))

        model = None
        model_used = dynamic_result["model_used"]

        if "gradient" in best_model_name.lower():
            model = _load_pickle(MODEL3_GB_FILE)
            model_used = "Model 3: Gradient Boosting Academic Risk"
        else:
            model = _load_pickle(MODEL3_XGB_FILE)
            model_used = "Model 3: XGBoost Academic Risk"

        if model is not None:
            try:
                X = _build_model3_features(db, student)
                pred = int(model.predict(X)[0])

                pred = max(0, min(3, pred))
                model_score = pred / 3.0

                risk_score = _clamp(
                    0.45 * model_score
                    + 0.55 * dynamic_result["risk_score"]
                )

                risk_name = _risk_category(risk_score)

                return {
                    "risk_score": round(risk_score, 4),
                    "risk_level": risk_name,
                    "risk_category": risk_name,
                    "risk_label": pred,
                    "model_used": model_used,
                    "source": "ml_model_blended",
                    "raw_model_score": round(model_score, 4),
                    "dynamic_score": dynamic_result["risk_score"],
                }

            except Exception as e:
                print(f"[ML WARNING] Model 3 prediction failed: {e}")

        return dynamic_result

    finally:
        db.close()


# ============================================================
# ALIASES
# ============================================================

def get_course_difficulty_prediction(student_id: int, course_id: int):
    return predict_course_difficulty(student_id, course_id)


def get_semester_workload_prediction(student_id: int, course_ids: List[int]):
    return predict_semester_workload(student_id, course_ids)


def get_academic_risk_prediction(student_id: int):
    return predict_academic_risk(student_id)

# ============================================================
# MODEL 4: COURSE SUCCESS PROBABILITY
# ============================================================

def _build_model4_features(db, student: Student, course: Course) -> np.ndarray:
    student_id = _safe_int(getattr(student, "id", 0), 0)

    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _safe_float(getattr(student, "workload_tolerance", 0.5), 0.5)
    ability = _safe_float(getattr(student, "academic_ability", gpa / 4.0), gpa / 4.0)

    grades = _get_completed_grade_points(db, student_id)
    total_completed = _student_total_completed(db, student_id, student)

    course_level_norm = _course_level(course) / 500.0
    credit_norm = _course_credit_hours(course) / 4.0
    prereq_count_norm = _course_prereq_count(course) / 10.0
    prereq_depth_norm = _course_prereq_depth(course) / 10.0
    centrality_norm = _course_graph_centrality(course)

    gpa_norm = gpa / 4.0
    ability_norm = ability
    tolerance_norm = tolerance

    completed_norm = total_completed / 50.0
    credits_completed_norm = len(grades) * 3.0 / 150.0
    semester_norm = _safe_float(getattr(student, "current_semester", 1), 1.0) / 12.0

    is_lab = _course_is_lab(course)

    course_pressure = (
        0.35 * course_level_norm
        + 0.20 * prereq_count_norm
        + 0.15 * prereq_depth_norm
        + 0.15 * credit_norm
        + 0.10 * is_lab
        + 0.05 * centrality_norm
    )

    student_fit = (
        0.45 * gpa_norm
        + 0.35 * ability_norm
        + 0.20 * tolerance_norm
    )

    fit_minus_pressure = student_fit - course_pressure

    return np.array([[
        gpa_norm,
        ability_norm,
        tolerance_norm,
        course_level_norm,
        credit_norm,
        prereq_count_norm,
        prereq_depth_norm,
        centrality_norm,
        is_lab,
        completed_norm,
        credits_completed_norm,
        semester_norm,
        course_pressure,
        student_fit,
        fit_minus_pressure,
    ]], dtype=float)


def _heuristic_course_success_probability(student: Student, course: Course) -> float:
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))

    difficulty = _heuristic_course_difficulty(student, course)

    success = (
        0.50 * (gpa / 4.0)
        + 0.25 * tolerance
        + 0.25 * (1.0 - difficulty)
    )

    return _clamp(success, 0.08, 0.94)


def _success_category(probability: float) -> str:
    probability = _clamp(probability)

    if probability >= 0.75:
        return "High"
    if probability >= 0.55:
        return "Medium"
    return "Low"


def predict_course_success_probability(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()

    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()

        if not student or not course:
            return None

        student = _temporary_student_values(student, override_tolerance, override_gpa)

        heuristic_probability = _heuristic_course_success_probability(student, course)

        model_info = _load_pickle(MODEL4_INFO_FILE)
        best_model_name = "Gradient Boosting"

        if isinstance(model_info, dict):
            best_model_name = str(model_info.get("best_model", "Gradient Boosting"))

        model = None
        model_used = "Model 4: Dynamic Success Probability Fallback"

        if "random" in best_model_name.lower():
            model = _load_pickle(MODEL4_RF_FILE)
            model_used = "Model 4: Random Forest Course Success Probability"
        else:
            model = _load_pickle(MODEL4_GB_FILE)
            model_used = "Model 4: Gradient Boosting Course Success Probability"

        if model is not None:
            try:
                X = _build_model4_features(db, student, course)

                if hasattr(model, "predict_proba"):
                    model_probability = float(model.predict_proba(X)[0][1])
                else:
                    model_probability = float(model.predict(X)[0])

                final_probability = _clamp(
                    0.75 * model_probability + 0.25 * heuristic_probability,
                    0.08,
                    0.94,
                )

                return {
                    "success_probability": round(final_probability, 4),
                    "success_chance": round(final_probability, 4),
                    "success_category": _success_category(final_probability),
                    "model_used": model_used,
                    "source": "model4_ml_blended",
                    "raw_model_probability": round(_clamp(model_probability), 4),
                    "dynamic_probability": round(heuristic_probability, 4),
                }

            except Exception as e:
                print(f"[ML WARNING] Model 4 prediction failed: {e}")

        return {
            "success_probability": round(heuristic_probability, 4),
            "success_chance": round(heuristic_probability, 4),
            "success_category": _success_category(heuristic_probability),
            "model_used": "Model 4: Dynamic Success Probability Fallback",
            "source": "fallback",
            "dynamic_probability": round(heuristic_probability, 4),
        }

    finally:
        db.close()


def get_course_success_probability(student_id: int, course_id: int):
    return predict_course_success_probability(student_id, course_id)


# ============================================================
# IMPROVED MODEL OVERRIDES (STEP: ML rigor upgrade)
# These definitions intentionally override the earlier versions above.
# They use pre-attempt features only and add Model 5 expected grade points.
# ============================================================

MODEL5_RF_FILE = ML_MODELS_DIR / "model5_random_forest_grade.pkl"
MODEL5_GB_FILE = ML_MODELS_DIR / "model5_gradient_boosting_grade.pkl"
MODEL5_INFO_FILE = ML_MODELS_DIR / "model5_info.pkl"


def _student_grade_context(db, student: Student):
    sid = _safe_int(getattr(student, "id", 0), 0)
    grades = _get_completed_grade_points(db, sid)
    current_gpa = _safe_float(getattr(student, "gpa", 0.0), 0.0)
    if grades:
        prior_gpa = float(np.mean(grades))
        recent_avg = float(np.mean(grades[-6:]))
        min_recent = float(np.min(grades[-6:]))
    else:
        prior_gpa = current_gpa if current_gpa > 0 else 3.0
        recent_avg = prior_gpa
        min_recent = prior_gpa
    total_completed = _student_total_completed(db, sid, student)
    prior_credits = max(0.0, float(total_completed) * 3.0)
    return grades, prior_gpa, recent_avg, min_recent, total_completed, prior_credits


def _course_pressure_from_course(course: Course) -> float:
    level = _course_level(course) / 500.0
    credits = _course_credit_hours(course) / 4.0
    prereqs = _course_prereq_count(course) / 10.0
    depth = _course_prereq_depth(course) / 10.0
    lab = _course_is_lab(course)
    centrality = _course_graph_centrality(course)
    return _clamp(0.28*level + 0.18*credits + 0.20*prereqs + 0.16*depth + 0.10*lab + 0.08*centrality)


def _preattempt_feature_dict(db, student: Student, course: Course, assumed_term_load: float = 15.0) -> Dict[str, float]:
    grades, prior_gpa, recent_avg, _min_recent, total_completed, prior_credits = _student_grade_context(db, student)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))
    pressure = _course_pressure_from_course(course)
    prereq_avg = prior_gpa  # conservative proxy when exact prerequisite grade map is unavailable in DB service
    prereq_ratio = 1.0 if _course_prereq_count(course) == 0 else min(1.0, len(grades) / max(1, _course_prereq_count(course)))
    prior_gpa_norm = _clamp(prior_gpa / 4.0)
    recent_avg_norm = _clamp(recent_avg / 4.0)
    prereq_avg_norm = _clamp(prereq_avg / 4.0)
    fit_minus_pressure = (0.55*prior_gpa_norm + 0.30*recent_avg_norm + 0.15*tolerance) - pressure
    return {
        "course_level_norm": _course_level(course) / 500.0,
        "credit_norm": _course_credit_hours(course) / 4.0,
        "prereq_count_norm": _course_prereq_count(course) / 10.0,
        "prereq_depth_norm": _course_prereq_depth(course) / 10.0,
        "centrality_norm": _course_graph_centrality(course),
        "is_lab": float(_course_is_lab(course)),
        "course_pressure": pressure,
        "prior_gpa_norm": prior_gpa_norm,
        "recent_avg_norm": recent_avg_norm,
        "prereq_avg_norm": prereq_avg_norm,
        "workload_tolerance": tolerance,
        "prior_credits_norm": prior_credits / 150.0,
        "completed_before_norm": total_completed / 50.0,
        "term_load_norm": assumed_term_load / 18.0,
        "prereq_completed_ratio": prereq_ratio,
        "fit_minus_pressure": fit_minus_pressure,
        # Backward-compatible names that old info files may expect.
        "gpa_norm": prior_gpa_norm,
        "ability_norm": prior_gpa_norm,
        "tolerance_norm": tolerance,
        "completed_norm": total_completed / 50.0,
        "credits_completed_norm": prior_credits / 150.0,
        "semester_norm": _safe_float(getattr(student, "current_semester", 1), 1.0) / 12.0,
        "student_fit": 0.55*prior_gpa_norm + 0.30*recent_avg_norm + 0.15*tolerance,
    }


def _vector_for_feature_columns(feature_map: Dict[str, float], feature_columns: List[str]) -> np.ndarray:
    return np.array([[float(feature_map.get(col, 0.0)) for col in feature_columns]], dtype=float)


def _expected_grade_category(points: float) -> str:
    p = max(0.0, min(4.3, float(points)))
    if p >= 3.3:
        return "Strong"
    if p >= 2.7:
        return "Good"
    if p >= 2.3:
        return "Acceptable"
    if p >= 2.0:
        return "Borderline"
    return "Weak"


def predict_expected_grade_points(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
    assumed_term_load: float = 15.0,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        if not student or not course:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        grades, prior_gpa, recent_avg, _min_recent, _total_completed, _prior_credits = _student_grade_context(db, student)
        difficulty = _heuristic_course_difficulty(student, course)
        fallback = max(0.0, min(4.3, 0.55*prior_gpa + 0.25*recent_avg + 0.20*(4.3*(1.0-difficulty))))

        info = _load_pickle(MODEL5_INFO_FILE)
        feature_columns = info.get("feature_columns", []) if isinstance(info, dict) else []
        best_model_name = str(info.get("best_model", "Gradient Boosting")) if isinstance(info, dict) else "Gradient Boosting"
        model = _load_pickle(MODEL5_RF_FILE if "random" in best_model_name.lower() else MODEL5_GB_FILE)
        if model is not None and feature_columns:
            fmap = _preattempt_feature_dict(db, student, course, assumed_term_load=assumed_term_load)
            X = _vector_for_feature_columns(fmap, feature_columns)
            raw = float(model.predict(X)[0])
            # Blend for stability, but keep model dominant.
            expected = max(0.0, min(4.3, 0.78*raw + 0.22*fallback))
            return {
                "expected_grade_points": round(expected, 3),
                "expected_grade_category": _expected_grade_category(expected),
                "model_used": f"Model 5: {best_model_name} Expected Grade",
                "source": "model5_ml_blended",
                "raw_model_grade": round(max(0.0, min(4.3, raw)), 3),
                "dynamic_grade": round(fallback, 3),
            }
        return {
            "expected_grade_points": round(fallback, 3),
            "expected_grade_category": _expected_grade_category(fallback),
            "model_used": "Model 5: Dynamic Expected Grade Fallback",
            "source": "fallback",
            "dynamic_grade": round(fallback, 3),
        }
    finally:
        db.close()


def predict_course_difficulty(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        if not student or not course:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        fallback = _heuristic_course_difficulty(student, course)
        info = _load_pickle(MODEL1_INFO_FILE)
        feature_columns = info.get("feature_columns", []) if isinstance(info, dict) else []
        best_model_name = str(info.get("best_model", "XGBoost")) if isinstance(info, dict) else "XGBoost"
        model = _load_pickle(MODEL1_RF_FILE if "random" in best_model_name.lower() else MODEL1_XGB_FILE)
        if model is not None and feature_columns:
            fmap = _preattempt_feature_dict(db, student, course)
            X = _vector_for_feature_columns(fmap, feature_columns)
            raw = _clamp(float(model.predict(X)[0]))
            score = _clamp(0.72*raw + 0.28*fallback)
            return {
                "difficulty_score": round(score, 4),
                "difficulty_category": _difficulty_category(score),
                "model_used": f"Model 1: {best_model_name} Personalized Difficulty",
                "source": "model1_ml_blended",
                "raw_model_score": round(raw, 4),
                "dynamic_score": round(fallback, 4),
            }
        return {
            "difficulty_score": round(fallback, 4),
            "difficulty_category": _difficulty_category(fallback),
            "model_used": "Model 1: Dynamic Difficulty Fallback",
            "source": "fallback",
            "dynamic_score": round(fallback, 4),
        }
    finally:
        db.close()


def _build_model4_features(db, student: Student, course: Course) -> np.ndarray:
    info = _load_pickle(MODEL4_INFO_FILE)
    feature_columns = info.get("feature_columns", []) if isinstance(info, dict) else []
    fmap = _preattempt_feature_dict(db, student, course)
    if not feature_columns:
        feature_columns = [
            "prior_gpa_norm","recent_avg_norm","prereq_avg_norm","workload_tolerance","course_level_norm","credit_norm",
            "prereq_count_norm","prereq_depth_norm","centrality_norm","is_lab","prior_credits_norm","completed_before_norm",
            "term_load_norm","course_pressure","prereq_completed_ratio","fit_minus_pressure"
        ]
    return _vector_for_feature_columns(fmap, feature_columns)


def _heuristic_course_success_probability(student: Student, course: Course) -> float:
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))
    difficulty = _heuristic_course_difficulty(student, course)
    success = 0.46*(gpa/4.0) + 0.18*tolerance + 0.28*(1.0-difficulty) + 0.08
    return _clamp(success, 0.05, 0.96)


def predict_course_success_probability(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        if not student or not course:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        fallback = _heuristic_course_success_probability(student, course)
        info = _load_pickle(MODEL4_INFO_FILE)
        best_model_name = str(info.get("best_model", "Gradient Boosting")) if isinstance(info, dict) else "Gradient Boosting"
        model = _load_pickle(MODEL4_RF_FILE if "random" in best_model_name.lower() else MODEL4_GB_FILE)
        if model is not None:
            try:
                X = _build_model4_features(db, student, course)
                raw = float(model.predict_proba(X)[0][1]) if hasattr(model, "predict_proba") else float(model.predict(X)[0])
                prob = _clamp(0.74*_clamp(raw) + 0.26*fallback, 0.05, 0.96)
                return {
                    "success_probability": round(prob, 4),
                    "success_chance": round(prob, 4),
                    "success_category": _success_category(prob),
                    "model_used": f"Model 4: {best_model_name} Success Probability",
                    "source": "model4_ml_blended",
                    "raw_model_probability": round(_clamp(raw), 4),
                    "dynamic_probability": round(fallback, 4),
                }
            except Exception as e:
                print(f"[ML WARNING] Model 4 prediction failed: {e}")
        return {
            "success_probability": round(fallback, 4),
            "success_chance": round(fallback, 4),
            "success_category": _success_category(fallback),
            "model_used": "Model 4: Dynamic Success Fallback",
            "source": "fallback",
            "dynamic_probability": round(fallback, 4),
        }
    finally:
        db.close()


def _build_model3_features(db, student: Student) -> np.ndarray:
    sid = _safe_int(getattr(student, "id", 0), 0)
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))
    grades = _get_completed_grade_points(db, sid)
    recent = grades[-6:] if grades else []
    avg_grade = float(np.mean(grades)) if grades else gpa
    avg_recent = float(np.mean(recent)) if recent else gpa
    min_recent = float(np.min(recent)) if recent else gpa
    fail_count = len([g for g in recent if g < 1.0])
    low_count = len([g for g in recent if g < 2.0])
    weak_count = len([g for g in recent if 1.0 <= g < 2.3])
    if len(recent) > 2:
        try:
            trend = float(np.polyfit(np.arange(len(recent)), np.array(recent), 1)[0])
        except Exception:
            trend = 0.0
    else:
        trend = 0.0
    total_completed = _student_total_completed(db, sid, student)
    feature_map = {
        "current_gpa": gpa/4.0,
        "avg_grade": avg_grade/4.0,
        "avg_recent_grade": avg_recent/4.0,
        "min_recent_grade": min_recent/4.0,
        "gpa_trend_slope": trend,
        "failed_count": fail_count/6.0,
        "low_grade_count": low_count/6.0,
        "weak_pass_count": weak_count/6.0,
        "avg_term_credits": 12.0/18.0,
        "max_term_credits": 15.0/18.0,
        "completed_courses": total_completed/50.0,
        "workload_tolerance": tolerance,
        # old compatibility
        "difficulty_variance": 0.0,
        "avg_difficulty": _clamp(1.0 - avg_recent/4.0),
        "performance_vs_difficulty": avg_recent/4.0 - _clamp(1.0 - avg_recent/4.0),
        "total_courses_completed": total_completed/50.0,
    }
    info = _load_pickle(MODEL3_INFO_FILE)
    feature_columns = info.get("feature_columns", []) if isinstance(info, dict) else []
    if not feature_columns:
        feature_columns = ["current_gpa","avg_grade","avg_recent_grade","min_recent_grade","gpa_trend_slope","failed_count","low_grade_count","weak_pass_count","avg_term_credits","max_term_credits","completed_courses","workload_tolerance"]
    return _vector_for_feature_columns(feature_map, feature_columns)


def predict_academic_risk(
    student_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        dynamic_result = _heuristic_academic_risk(student, db)
        info = _load_pickle(MODEL3_INFO_FILE)
        best_model_name = str(info.get("best_model", "Random Forest")) if isinstance(info, dict) else "Random Forest"
        model = _load_pickle(MODEL3_GB_FILE if "gradient" in best_model_name.lower() else MODEL3_XGB_FILE)
        if model is not None:
            try:
                X = _build_model3_features(db, student)
                pred = int(model.predict(X)[0])
                pred = max(0, min(3, pred))
                model_score = pred/3.0
                risk_score = _clamp(0.54*model_score + 0.46*dynamic_result["risk_score"])
                risk_name = _risk_category(risk_score)
                return {
                    "risk_score": round(risk_score,4),
                    "risk_level": risk_name,
                    "risk_category": risk_name,
                    "risk_label": pred,
                    "model_used": f"Model 3: {best_model_name} Future Risk",
                    "source": "model3_future_ml_blended",
                    "raw_model_score": round(model_score,4),
                    "dynamic_score": dynamic_result["risk_score"],
                }
            except Exception as e:
                print(f"[ML WARNING] Model 3 prediction failed: {e}")
        return dynamic_result
    finally:
        db.close()

# Refresh aliases after overriding functions.
def get_course_difficulty_prediction(student_id: int, course_id: int):
    return predict_course_difficulty(student_id, course_id)


def get_academic_risk_prediction(student_id: int):
    return predict_academic_risk(student_id)


def get_course_success_probability(student_id: int, course_id: int):
    return predict_course_success_probability(student_id, course_id)


# Override semester workload to match improved Model 2 feature schema.
def _semester_feature_dict(student: Student, courses: List[Course], difficulties: List[float]) -> Dict[str, float]:
    gpa = _safe_float(getattr(student, "gpa", 3.0), 3.0)
    tolerance = _clamp(_safe_float(getattr(student, "workload_tolerance", 0.5), 0.5))
    total_credits = sum(_course_credit_hours(c) for c in courses)
    num_courses = len(courses)
    num_labs = sum(_course_is_lab(c) for c in courses)
    avg_diff = float(np.mean(difficulties)) if difficulties else 0.5
    max_diff = float(np.max(difficulties)) if difficulties else 0.5
    var_diff = float(np.var(difficulties)) if len(difficulties) > 1 else 0.0
    pressures = [_course_pressure_from_course(c) for c in courses] if courses else [0.5]
    avg_pressure = float(np.mean(pressures))
    max_pressure = float(np.max(pressures))
    avg_level = float(np.mean([_course_level(c) for c in courses])) if courses else 100.0
    return {
        "avg_difficulty": avg_diff,
        "max_difficulty": max_diff,
        "var_difficulty": var_diff,
        "avg_pressure": avg_pressure,
        "max_pressure": max_pressure,
        "total_credits_norm": total_credits/18.0,
        "num_courses_norm": num_courses/6.0,
        "num_labs_norm": num_labs/3.0,
        "avg_level_norm": avg_level/500.0,
        "prior_gpa_norm": gpa/4.0,
        "recent_avg_norm": gpa/4.0,
        "workload_tolerance": tolerance,
    }


def predict_semester_workload(
    student_id: int,
    course_ids: List[int],
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        courses = []
        for cid in course_ids or []:
            c = db.query(Course).filter(Course.id == cid).first()
            if c:
                courses.append(c)
        if not courses:
            return {"semester_difficulty":0.0,"overload_risk":0.0,"difficulty_category":"Easy","risk_category":"Low","total_credits":0,"num_courses":0,"num_labs":0,"source":"empty"}
        difficulties=[]
        for c in courses:
            pred = predict_course_difficulty(student_id, c.id, override_tolerance=override_tolerance, override_gpa=override_gpa)
            difficulties.append(_safe_float(pred.get("difficulty_score") if pred else None, _heuristic_course_difficulty(student, c)))
        dynamic = _heuristic_semester_workload(student, courses, difficulties)
        info = _load_pickle(MODEL2_INFO_FILE)
        feature_columns = info.get("feature_columns", []) if isinstance(info, dict) else []
        best_name = str(info.get("best_model", "Gradient Boosting")) if isinstance(info, dict) else "Gradient Boosting"
        model = _load_pickle(MODEL2_NN_FILE if "random" in best_name.lower() else MODEL2_GB_FILE)
        if model is not None and feature_columns:
            try:
                fmap = _semester_feature_dict(student, courses, difficulties)
                X = _vector_for_feature_columns(fmap, feature_columns)
                raw = _clamp(float(model.predict(X)[0]))
                sem = _clamp(0.62*raw + 0.38*dynamic["semester_difficulty"])
                overload = _clamp(0.65*dynamic["overload_risk"] + 0.25*sem + 0.10*fmap["total_credits_norm"])
                return {**dynamic, "semester_difficulty":round(sem,4), "overload_risk":round(overload,4), "difficulty_category":_semester_difficulty_category(sem), "risk_category":_risk_category(overload), "model_used":f"Model 2: {best_name} Semester Workload", "source":"model2_ml_blended", "raw_model_difficulty":round(raw,4)}
            except Exception as e:
                print(f"[ML WARNING] Model 2 prediction failed: {e}")
        return dynamic
    finally:
        db.close()

# Refresh semester alias.
def get_semester_workload_prediction(student_id: int, course_ids: List[int]):
    return predict_semester_workload(student_id, course_ids)

# ============================================================
# FINAL ML OVERRIDES: strength/weakness aware success + grade models
# These are intentionally last in the file so they override older duplicate definitions.
# ============================================================

def _runtime_course_area(course: Course) -> str:
    subj = str(getattr(course, 'subject', '') or '').upper()
    text = f"{getattr(course, 'name', '') or ''} {getattr(course, 'description', '') or ''}".lower()
    if subj in {'MATH', 'STAT'}:
        return 'math'
    if subj == 'PHYS':
        return 'physics'
    if subj in {'CHEM', 'BIOL'}:
        return 'chem_bio'
    if subj in {'ENGL', 'FEAA', 'INDE'}:
        return 'humanities_business'
    if 'lab' in text or 'project' in text:
        return 'lab_project'
    if subj == 'CMPS' or any(k in text for k in ['program', 'algorithm', 'data structure', 'software', 'computer', 'network', 'database']):
        return 'computing'
    if any(k in text for k in ['circuit', 'electronics', 'electric', 'power', 'device', 'microelectronic']):
        return 'circuits'
    if any(k in text for k in ['signal', 'image', 'speech', 'digital processing', 'probability']):
        return 'signals'
    if any(k in text for k in ['control', 'robot', 'system', 'embedded', 'automation']):
        return 'systems_control'
    if any(k in text for k in ['communication', 'wireless', 'antenna', 'telecom', 'radio']):
        return 'communication'
    if subj == 'EECE':
        return 'circuits'
    return 'humanities_business'


def _runtime_student_area_context(db, student: Student, course: Course):
    sid = _safe_int(getattr(student, 'id', 0), 0)
    target_area = _runtime_course_area(course)
    target_subject = str(getattr(course, 'subject', '') or '').upper()
    rows = _get_completed_student_courses(db, sid)
    all_grades = []
    area_grades = []
    subject_grades = []
    prereq_grades = []

    prereq_ids = set()
    try:
        for pr in getattr(course, 'prerequisites', []) or []:
            pid = getattr(pr, 'prerequisite_id', None)
            if pid:
                prereq_ids.add(pid)
    except Exception:
        prereq_ids = set()

    completed_prereq_ids = set()
    for row in rows:
        gp = getattr(row, 'grade_points', None)
        c = getattr(row, 'course', None)
        if gp is None or c is None:
            continue
        gp = _safe_float(gp, 0.0)
        all_grades.append(gp)
        area = _runtime_course_area(c)
        subject = str(getattr(c, 'subject', '') or '').upper()
        if area == target_area:
            area_grades.append(gp)
        if subject == target_subject:
            subject_grades.append(gp)
        cid = getattr(c, 'id', None)
        if cid in prereq_ids:
            completed_prereq_ids.add(cid)
            prereq_grades.append(gp)

    current_gpa = _safe_float(getattr(student, 'gpa', 0.0), 0.0)
    prior_gpa = float(np.mean(all_grades)) if all_grades else (current_gpa if current_gpa > 0 else 3.0)
    recent_avg = float(np.mean(all_grades[-6:])) if all_grades else prior_gpa
    area_avg = float(np.mean(area_grades)) if area_grades else prior_gpa
    subject_avg = float(np.mean(subject_grades)) if subject_grades else prior_gpa
    prereq_avg = float(np.mean(prereq_grades)) if prereq_grades else prior_gpa
    prereq_count = max(0, len(prereq_ids))
    prereq_ratio = 1.0 if prereq_count == 0 else len(completed_prereq_ids) / max(1, prereq_count)
    weak_area = int(len(area_grades) >= 1 and area_avg < 2.3)
    strong_area = int(len(area_grades) >= 1 and area_avg >= 3.3)
    return {
        'prior_gpa': prior_gpa,
        'recent_avg': recent_avg,
        'area_avg': area_avg,
        'subject_avg': subject_avg,
        'prereq_avg': prereq_avg,
        'prereq_ratio': prereq_ratio,
        'weak_area': weak_area,
        'strong_area': strong_area,
        'completed_count': len(rows),
        'prior_credits': float(len(rows)) * 3.0,
    }


def _preattempt_feature_dict(db, student: Student, course: Course, assumed_term_load: float = 15.0) -> Dict[str, float]:
    ctx = _runtime_student_area_context(db, student, course)
    tolerance = _clamp(_safe_float(getattr(student, 'workload_tolerance', 0.5), 0.5))
    pressure = _course_pressure_from_course(course)
    prior_gpa_norm = _clamp(ctx['prior_gpa'] / 4.0)
    recent_avg_norm = _clamp(ctx['recent_avg'] / 4.0)
    prereq_avg_norm = _clamp(ctx['prereq_avg'] / 4.0)
    subject_avg_norm = _clamp(ctx['subject_avg'] / 4.0)
    area_strength_norm = _clamp(ctx['area_avg'] / 4.0)
    subj = str(getattr(course, 'subject', '') or '').upper()
    ctype = str(getattr(course, 'course_type', '') or '').lower()
    is_major_or_core = 1.0 if (ctype == 'core' or subj == 'EECE') else 0.0
    is_support = 1.0 if ctype == 'support' else 0.0
    is_elective = 1.0 if ctype in {'major_elective','general_elective'} else 0.0
    fit_minus_pressure = (
        0.34*prior_gpa_norm + 0.24*recent_avg_norm + 0.18*area_strength_norm
        + 0.14*prereq_avg_norm + 0.10*tolerance - pressure
    )
    total_completed = ctx['completed_count']
    prior_credits = ctx['prior_credits']
    return {
        'prior_gpa_norm': prior_gpa_norm,
        'recent_avg_norm': recent_avg_norm,
        'prereq_avg_norm': prereq_avg_norm,
        'subject_avg_norm': subject_avg_norm,
        'area_strength_norm': area_strength_norm,
        'workload_tolerance': tolerance,
        'course_level_norm': _course_level(course) / 500.0,
        'credit_norm': _course_credit_hours(course) / 4.0,
        'prereq_count_norm': _course_prereq_count(course) / 10.0,
        'prereq_depth_norm': _course_prereq_depth(course) / 10.0,
        'centrality_norm': _course_graph_centrality(course),
        'is_lab': float(_course_is_lab(course)),
        'prior_credits_norm': prior_credits / 150.0,
        'completed_before_norm': total_completed / 50.0,
        'term_load_norm': assumed_term_load / 18.0,
        'course_pressure': pressure,
        'prereq_completed_ratio': ctx['prereq_ratio'],
        'fit_minus_pressure': fit_minus_pressure,
        'weak_area_flag': float(ctx['weak_area']),
        'strong_area_flag': float(ctx['strong_area']),
        'is_major_or_core': is_major_or_core,
        'is_support': is_support,
        'is_elective': is_elective,
        # Backward-compatible names used by older pickles.
        'gpa_norm': prior_gpa_norm,
        'ability_norm': prior_gpa_norm,
        'tolerance_norm': tolerance,
        'completed_norm': total_completed / 50.0,
        'credits_completed_norm': prior_credits / 150.0,
        'semester_norm': _safe_float(getattr(student, 'current_semester', 1), 1.0) / 12.0,
        'student_fit': 0.34*prior_gpa_norm + 0.24*recent_avg_norm + 0.18*area_strength_norm + 0.14*prereq_avg_norm + 0.10*tolerance,
    }


def _heuristic_course_success_probability(student: Student, course: Course) -> float:
    # Strength-aware fallback: not a rule label, only a backup when model files are missing.
    db = get_db()
    try:
        fmap = _preattempt_feature_dict(db, student, course, assumed_term_load=15.0)
        score = (
            0.28*fmap['prior_gpa_norm'] + 0.18*fmap['recent_avg_norm'] + 0.20*fmap['area_strength_norm']
            + 0.10*fmap['prereq_avg_norm'] + 0.08*fmap['workload_tolerance'] + 0.08*fmap['prereq_completed_ratio']
            - 0.20*fmap['course_pressure'] - 0.06*fmap['weak_area_flag'] + 0.04*fmap['strong_area_flag']
        )
        return _clamp(0.12 + 0.95*score, 0.05, 0.97)
    finally:
        db.close()


def predict_course_success_probability(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        if not student or not course:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        heuristic_probability = _heuristic_course_success_probability(student, course)
        info = _load_pickle(MODEL4_INFO_FILE)
        feature_columns = info.get('feature_columns', []) if isinstance(info, dict) else []
        best_model_name = str(info.get('best_model', 'Gradient Boosting')) if isinstance(info, dict) else 'Gradient Boosting'
        model = _load_pickle(MODEL4_RF_FILE if 'random' in best_model_name.lower() else MODEL4_GB_FILE)
        if model is not None and feature_columns:
            fmap = _preattempt_feature_dict(db, student, course, assumed_term_load=15.0)
            X = _vector_for_feature_columns(fmap, feature_columns)
            raw = float(model.predict_proba(X)[0][1]) if hasattr(model, 'predict_proba') else float(model.predict(X)[0])
            # Model dominant, fallback only stabilizes edge cases.
            final = _clamp(0.86*raw + 0.14*heuristic_probability, 0.04, 0.98)
            return {
                'success_probability': round(final, 4),
                'success_chance': round(final, 4),
                'success_category': _success_category(final),
                'model_used': f'Model 4: {best_model_name} Course Success Probability',
                'source': 'model4_strength_weakness_ml',
                'raw_model_probability': round(_clamp(raw), 4),
                'dynamic_probability': round(heuristic_probability, 4),
                'area_strength_norm': round(fmap.get('area_strength_norm', 0), 4),
                'weak_area_flag': int(fmap.get('weak_area_flag', 0)),
            }
        return {
            'success_probability': round(heuristic_probability, 4),
            'success_chance': round(heuristic_probability, 4),
            'success_category': _success_category(heuristic_probability),
            'model_used': 'Model 4: Strength-aware fallback',
            'source': 'fallback',
            'dynamic_probability': round(heuristic_probability, 4),
        }
    finally:
        db.close()


def predict_expected_grade_points(
    student_id: int,
    course_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
    assumed_term_load: float = 15.0,
) -> Optional[Dict[str, Any]]:
    db = get_db()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        course = db.query(Course).filter(Course.id == course_id).first()
        if not student or not course:
            return None
        student = _temporary_student_values(student, override_tolerance, override_gpa)
        fmap = _preattempt_feature_dict(db, student, course, assumed_term_load=assumed_term_load)
        fallback = max(0.0, min(4.3, (
            1.15
            + 1.35*fmap['prior_gpa_norm']
            + 0.58*fmap['recent_avg_norm']
            + 0.72*fmap['area_strength_norm']
            + 0.34*fmap['prereq_avg_norm']
            + 0.26*fmap['workload_tolerance']
            - 1.34*fmap['course_pressure']
            - 0.25*max(0.0, fmap['term_load_norm'] - 0.75)
            - 0.35*fmap['weak_area_flag']
            + 0.18*fmap['strong_area_flag']
        )))
        info = _load_pickle(MODEL5_INFO_FILE)
        feature_columns = info.get('feature_columns', []) if isinstance(info, dict) else []
        best_model_name = str(info.get('best_model', 'Gradient Boosting')) if isinstance(info, dict) else 'Gradient Boosting'
        model = _load_pickle(MODEL5_RF_FILE if 'random' in best_model_name.lower() else MODEL5_GB_FILE)
        if model is not None and feature_columns:
            X = _vector_for_feature_columns(fmap, feature_columns)
            raw = float(model.predict(X)[0])
            expected = max(0.0, min(4.3, 0.86*raw + 0.14*fallback))
            return {
                'expected_grade_points': round(expected, 3),
                'expected_grade_category': _expected_grade_category(expected),
                'model_used': f'Model 5: {best_model_name} Expected Grade',
                'source': 'model5_strength_weakness_ml',
                'raw_model_grade': round(max(0.0, min(4.3, raw)), 3),
                'dynamic_grade': round(fallback, 3),
                'area_strength_norm': round(fmap.get('area_strength_norm', 0), 4),
                'weak_area_flag': int(fmap.get('weak_area_flag', 0)),
            }
        return {
            'expected_grade_points': round(fallback, 3),
            'expected_grade_category': _expected_grade_category(fallback),
            'model_used': 'Model 5: Strength-aware fallback',
            'source': 'fallback',
            'dynamic_grade': round(fallback, 3),
        }
    finally:
        db.close()
