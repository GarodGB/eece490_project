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
