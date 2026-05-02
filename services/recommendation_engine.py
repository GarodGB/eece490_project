import hashlib
from typing import List, Dict, Any, Optional, Tuple

from database.db import get_db
from database.models import Course, Student
from services.prerequisite_service import get_unlocked_courses
from services.course_cache import get_course_by_code, get_course_difficulty

try:
    from services.ml_service import (
        predict_course_difficulty,
        predict_semester_workload,
        predict_academic_risk,
    )
except Exception:
    from services.ml_service import predict_course_difficulty, predict_semester_workload

    def predict_academic_risk(student_id: int, *args, **kwargs):
        return {
            "risk_score": 0.35,
            "risk_level": "Medium",
            "model_used": "Model 3 unavailable",
            "source": "fallback",
        }


_ELECTIVE_CREDIT_CAP_BY_MAJOR = {
    "ECE": 6.0,
    "CSE": 6.0,
    "CS": 6.0,
    "ENGR": 9.0,
}

_MAX_PER_NON_MAJOR_SUBJECT = 3
STRICT_SUPPORT_SUBJECTS = {"MATH", "PHYS", "CHEM", "STAT", "ENGL", "ENG"}
_CORE_SUPPORT_SUBJECTS = frozenset({"MATH", "PHYS", "CHEM", "STAT"})


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except Exception:
        return low


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _risk_score_from_result(academic_risk: Optional[Dict[str, Any]]) -> float:
    if not academic_risk:
        return 0.35

    if academic_risk.get("risk_score") is not None:
        return _clamp(float(academic_risk.get("risk_score", 0.35)))

    level = str(academic_risk.get("risk_level", "Medium")).lower()
    mapping = {
        "low": 0.18,
        "medium": 0.45,
        "high": 0.72,
        "critical": 0.92,
    }
    return mapping.get(level, 0.35)


def _safe_predict_academic_risk(
    student_id: int,
    override_tolerance: Optional[float] = None,
    override_gpa: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        risk = predict_academic_risk(
            student_id,
            override_tolerance=override_tolerance,
            override_gpa=override_gpa,
        )
        if risk:
            return risk
    except TypeError:
        try:
            risk = predict_academic_risk(student_id)
            if risk:
                return risk
        except Exception as e:
            print(f"[ML WARNING] Academic risk prediction failed: {e}")
    except Exception as e:
        print(f"[ML WARNING] Academic risk prediction failed: {e}")

    return {
        "risk_score": 0.35,
        "risk_level": "Medium",
        "model_used": "Model 3: Dynamic Academic Risk Fallback",
        "source": "fallback",
    }


def _difficulty_to_category(score: float) -> str:
    score = _clamp(score)
    if score < 0.40:
        return "Easy"
    if score < 0.70:
        return "Medium"
    return "Hard"


def _make_recommendation_reason(
    course: Dict[str, Any],
    category: str,
    difficulty_score: float,
    ml_fit_score: float,
    academic_risk: Dict[str, Any],
    goal_mode: str,
    tol: float,
) -> str:
    role = course.get("role_label") or course.get("catalog_bucket") or "Course"
    risk_level = academic_risk.get("risk_level", "Medium")

    if difficulty_score < 0.40:
        diff_text = "low predicted difficulty"
    elif difficulty_score < 0.70:
        diff_text = "moderate predicted difficulty"
    else:
        diff_text = "high predicted difficulty"

    if ml_fit_score >= 0.75:
        fit_text = "strong ML fit"
    elif ml_fit_score >= 0.55:
        fit_text = "good ML fit"
    else:
        fit_text = "acceptable ML fit"

    if goal_mode in ("raise_gpa", "raise_gpa_strong", "recovery"):
        goal_text = "supports your GPA goal by controlling workload"
    elif goal_mode == "relaxed_target":
        goal_text = "allows a more flexible semester plan"
    else:
        goal_text = "matches your current workload profile"

    return (
        f"{role} course; prerequisites are satisfied. "
        f"ML predicts {diff_text} ({difficulty_score:.0%}), "
        f"{fit_text} ({ml_fit_score:.0%}), and {risk_level.lower()} academic risk. "
        f"It {goal_text} with tolerance {tol:.2f}."
    )


def _apply_role_based_difficulty(
    difficulty_score: float,
    catalog_bucket: str,
    course_level: int,
    subject_upper: str,
) -> float:
    ds = min(1.0, max(0.0, float(difficulty_score)))
    lvl = int(course_level or 100)
    tier = max(0.0, min(1.0, (lvl - 100) / 300.0))

    if catalog_bucket == "major":
        ds = min(1.0, ds + 0.07 + 0.10 * tier)
    elif catalog_bucket == "elective":
        ds = max(0.0, ds * 0.84 - 0.035)
    elif catalog_bucket == "support":
        if subject_upper in _CORE_SUPPORT_SUBJECTS:
            ds = min(1.0, ds + 0.045 + 0.04 * tier)
        else:
            ds = min(1.0, ds + 0.02)

    return ds


def _bucket_order_key(course: Dict[str, Any]) -> Tuple[int, float]:
    b = course.get("catalog_bucket") or "major"
    tier = {"major": 0, "support": 1, "elective": 2}.get(b, 1)
    ar = float(course.get("adjusted_rank_score", course.get("recommendation_score", 0)) or 0)
    return (tier, -ar)


def _take_diverse_courses(
    courses: List[Dict[str, Any]],
    limit: int,
    per_subject_cap: int = 2,
) -> List[Dict[str, Any]]:
    if limit <= 0 or not courses:
        return []

    ranked = sorted(courses, key=_bucket_order_key)
    subject_counts: Dict[str, int] = {}
    selected: List[Dict[str, Any]] = []

    for c in ranked:
        if len(selected) >= limit:
            break

        subj = str(c.get("subject", "") or "UNK").upper()

        if subject_counts.get(subj, 0) >= per_subject_cap:
            continue

        selected.append(c)
        subject_counts[subj] = subject_counts.get(subj, 0) + 1

    if len(selected) < limit:
        selected_codes = {str(c.get("course_code", "") or "") for c in selected}

        for c in ranked:
            if len(selected) >= limit:
                break

            code = str(c.get("course_code", "") or "")

            if not code or code in selected_codes:
                continue

            selected.append(c)
            selected_codes.add(code)

    return selected


def _build_candidate_pool(
    em: str,
    effective_max_courses: int,
    core_courses: List[Dict[str, Any]],
    support_courses: List[Dict[str, Any]],
    major_elective_courses: List[Dict[str, Any]],
    general_elective_courses: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if em == "major_first":
        core_take = max(20, effective_max_courses * 6)
        support_take = max(10, effective_max_courses * 3)
        major_elective_take = max(4, effective_max_courses * 2)
        general_elective_take = max(2, effective_max_courses)
        general_subj_cap = 1
        major_subj_cap = 2

    elif em == "balanced":
        core_take = max(18, effective_max_courses * 5)
        support_take = max(12, effective_max_courses * 3)
        major_elective_take = max(8, effective_max_courses * 3)
        general_elective_take = max(8, effective_max_courses * 3)
        general_subj_cap = 1
        major_subj_cap = 2

    else:
        core_take = max(12, effective_max_courses * 4)
        support_take = max(8, effective_max_courses * 2)
        major_elective_take = max(12, effective_max_courses * 4)
        general_elective_take = max(12, effective_max_courses * 4)
        general_subj_cap = 2
        major_subj_cap = 2

    core_part = core_courses[:core_take]
    support_part = support_courses[:support_take]

    major_part = _take_diverse_courses(
        major_elective_courses,
        limit=major_elective_take,
        per_subject_cap=major_subj_cap,
    )

    general_part = _take_diverse_courses(
        general_elective_courses,
        limit=general_elective_take,
        per_subject_cap=general_subj_cap,
    )

    combined = core_part + support_part + major_part + general_part

    seen = set()
    out: List[Dict[str, Any]] = []

    for c in combined:
        code = str(c.get("course_code", "") or "")

        if not code or code in seen:
            continue

        out.append(c)
        seen.add(code)

    return out


def _apply_adjusted_rank_scores(scored_courses: List[Dict[str, Any]], tol: float, em: str) -> None:
    tol = min(1.0, max(0.0, float(tol)))

    for c in scored_courses:
        rs = float(c.get("recommendation_score", 0) or 0)
        ds = float(c.get("difficulty_score", 0.5) or 0.5)
        ml_fit = float(c.get("ml_fit_score", 0.5) or 0.5)
        risk_impact = float(c.get("ml_risk_impact", 0.0) or 0.0)

        ds = min(1.0, max(0.0, ds))
        ml_fit = min(1.0, max(0.0, ml_fit))

        tw = 0.64
        tol_curve = (2.0 * tol - 1.0) * (ds - 0.5)
        adj = rs * (1.0 + tw * tol_curve)

        cb = c.get("catalog_bucket") or "major"
        ct = str(c.get("course_type", "") or "").strip().lower()

        if em == "include_electives" and cb == "elective":
            adj *= 1.0 + 0.10 + 0.18 * tol

        elif em == "major_first" and cb == "elective":
            adj *= max(0.08, 1.0 - 0.62 - 0.22 * (1.0 - tol))

        elif em == "balanced" and cb == "elective":
            if ct == "general_elective":
                adj *= 0.96
            elif ct == "major_elective":
                adj *= 0.92
            else:
                adj *= 0.90

        if cb == "major" and tol >= 0.55:
            adj *= 1.0 + 0.05 * (tol - 0.55)

        ml_multiplier = 1.0 + 0.30 * (ml_fit - 0.5) - 0.18 * risk_impact
        ml_multiplier = max(0.76, min(1.26, ml_multiplier))
        adj *= ml_multiplier

        c["adjusted_rank_score"] = adj


def _rank_sort_key(
    course: Dict[str, Any],
    student_id: int,
    term_s: str,
    tol: float,
    em: str,
    max_hard: int,
    target_credits: int,
) -> tuple:
    ars = float(course.get("adjusted_rank_score", course.get("recommendation_score", 0)) or 0)
    primary = -round(ars, 3)

    code = str(course.get("course_code", "") or "")
    seed = f"{student_id}|{term_s}|{tol:.5f}|{em}|{max_hard}|{target_credits}|{code}"
    h = hashlib.blake2s(seed.encode("utf-8"), digest_size=8).digest()
    tie = int.from_bytes(h, "big") / float(2 ** 64)

    return (primary, tie)


def _effective_elective_credit_cap(major_u: str, include_electives: bool, elective_emphasis: str) -> float:
    base = float(_ELECTIVE_CREDIT_CAP_BY_MAJOR.get(major_u, 9.0))

    if not include_electives:
        return 0.0

    if elective_emphasis == "include_electives":
        return min(15.0, base * 2.0)

    if elective_emphasis == "balanced":
        return min(9.0, max(base, 6.0))

    return min(base, 3.0)


def _compute_goal_planning(
    current_gpa: float,
    target_gpa: Optional[float],
    tol: float,
    target_credits: int,
    max_courses: int,
) -> Tuple[str, float, int, float, int, int, float]:
    tol = min(1.0, max(0.0, float(tol)))

    if target_gpa is not None:
        try:
            tg = float(target_gpa)
        except (TypeError, ValueError):
            tg = None
    else:
        tg = None

    gpa_gap = (tg - current_gpa) if tg is not None else 0.0

    if tg is None:
        goal_mode = "tolerance_only"
    elif current_gpa < 2.5 and tg > current_gpa + 0.05:
        goal_mode = "recovery"
    elif gpa_gap > 0.35:
        goal_mode = "raise_gpa_strong"
    elif gpa_gap > 0.1:
        goal_mode = "raise_gpa"
    elif gpa_gap < -0.15:
        goal_mode = "relaxed_target"
    else:
        goal_mode = "maintain"

    credit_slack = int(round(1 + 5 * tol))

    if goal_mode in ("raise_gpa_strong", "recovery"):
        credit_slack = max(1, credit_slack - 2)
    elif goal_mode == "raise_gpa":
        credit_slack = max(1, credit_slack - 1)
    elif goal_mode == "relaxed_target" and tol >= 0.65:
        credit_slack = min(8, credit_slack + 1)

    effective_max_credits = float(target_credits)

    effective_max_courses = min(max_courses, max(3, int(3 + round(5 * tol))))

    if goal_mode in ("raise_gpa_strong", "recovery"):
        effective_max_courses = max(3, effective_max_courses - 2)
    elif goal_mode == "raise_gpa":
        effective_max_courses = max(3, effective_max_courses - 1)
    elif goal_mode == "relaxed_target" and tol >= 0.75 and current_gpa >= 3.4:
        effective_max_courses = min(max_courses, effective_max_courses + 1)

    max_hard_allowed = min(effective_max_courses, max(0, int(round(3 * tol))))

    if goal_mode in ("raise_gpa_strong", "recovery"):
        max_hard_allowed = min(max_hard_allowed, 1)
    elif goal_mode == "raise_gpa":
        max_hard_allowed = min(max_hard_allowed, 2)

    w_easy = 0.0

    if tg is not None and gpa_gap > 0.1:
        w_easy = min(1.0, 0.2 + gpa_gap * 1.1)

    if current_gpa < 2.75:
        w_easy = min(1.0, w_easy + 0.22)

    if tol < 0.35:
        w_easy = min(1.0, w_easy + 0.12)

    if goal_mode == "tolerance_only":
        w_easy = min(1.0, w_easy + (1.0 - tol) * 0.15)

    return (
        goal_mode,
        gpa_gap,
        credit_slack,
        effective_max_credits,
        effective_max_courses,
        max_hard_allowed,
        w_easy,
    )


def _course_type_to_bucket(course_type: str, subject_upper: str, student_major: str) -> str:
    ct = (course_type or "").strip().lower()
    subj = (subject_upper or "").upper()
    maj = (student_major or "").upper()

    if ct == "core":
        return "major"

    if ct == "support":
        return "support"

    if ct in ("major_elective", "general_elective"):
        return "elective"

    if subj == maj:
        return "major"

    if subj in STRICT_SUPPORT_SUBJECTS:
        return "support"

    return "elective"


def _mode_caps(em: str, include_electives: bool):
    if em == "major_first":
        return (
            1 if include_electives else 0,
            0,
            0.95,
            0.42,
            -0.18,
            -0.55,
        )

    if em == "balanced":
        return (
            2 if include_electives else 0,
            2 if include_electives else 0,
            0.78,
            0.36,
            -0.04,
            -0.02,
        )

    return (
        2 if include_electives else 0,
        2 if include_electives else 0,
        0.40,
        0.16,
        0.08,
        0.12,
    )


def _mode_targets(
    em: str,
    effective_max_courses: int,
    max_major_electives_allowed: int,
    max_general_electives_allowed: int,
):
    if em == "major_first":
        return {
            "min_core": min(2, effective_max_courses),
            "min_support": 1 if effective_max_courses >= 3 else 0,
            "min_electives": 0,
            "max_major_electives": max_major_electives_allowed,
            "max_general_electives": 0,
        }

    if em == "balanced":
        return {
            "min_core": 1 if effective_max_courses >= 2 else 0,
            "min_support": 1 if effective_max_courses >= 3 else 0,
            "min_electives": 2 if effective_max_courses >= 4 else 1,
            "min_major_electives": 1 if effective_max_courses >= 4 else 0,
            "min_general_electives": 1 if effective_max_courses >= 4 else 0,
            "max_major_electives": min(2, max_major_electives_allowed),
            "max_general_electives": min(2, max_general_electives_allowed),
        }

    return {
        "min_core": 1 if effective_max_courses >= 2 else 0,
        "min_support": 0,
        "min_electives": 2 if effective_max_courses >= 4 else 1,
        "min_general_electives": 1 if effective_max_courses >= 4 else 0,
        "max_major_electives": max_major_electives_allowed,
        "max_general_electives": max_general_electives_allowed,
    }


def recommend_courses(
    student_id: int,
    target_credits: int = 15,
    max_courses: int = 6,
    term: str = None,
    override_target_gpa: Optional[float] = None,
    override_tolerance: Optional[float] = None,
    include_electives: bool = True,
    elective_emphasis: str = "balanced",
    override_max_hard: Optional[int] = None,
) -> Dict[str, Any]:
    db = get_db()

    try:
        student = db.query(Student).filter(Student.id == student_id).first()

        if not student:
            return {
                "recommendations": [],
                "semester_workload": None,
                "academic_risk": None,
                "planning_params": {},
                "alternatives": [],
            }

        current_gpa = float(student.gpa or 0.0)

        tol = float(student.workload_tolerance if student.workload_tolerance is not None else 0.5)
        tol = min(1.0, max(0.0, tol))

        if override_tolerance is not None:
            tol = min(1.0, max(0.0, float(override_tolerance)))

        academic_risk = _safe_predict_academic_risk(
            student_id,
            override_tolerance=tol,
            override_gpa=current_gpa,
        )
        academic_risk_score = _risk_score_from_result(academic_risk)

        from database.models import StudentCourse

        completed_rows = db.query(Course.course_code).join(
            StudentCourse, Course.id == StudentCourse.course_id
        ).filter(
            StudentCourse.student_id == student_id,
            StudentCourse.status == "completed",
        ).all()

        completed_course_codes = {row[0] for row in completed_rows if row[0]}

        target_gpa = getattr(student, "target_semester_gpa", None)

        if target_gpa is not None:
            try:
                target_gpa = float(target_gpa)
            except (TypeError, ValueError):
                target_gpa = None

        if override_target_gpa is not None:
            try:
                target_gpa = float(override_target_gpa)
            except (TypeError, ValueError):
                pass

        (
            goal_mode,
            gpa_gap,
            credit_slack,
            effective_max_credits,
            effective_max_courses,
            max_hard_allowed,
            w_easy,
        ) = _compute_goal_planning(current_gpa, target_gpa, tol, target_credits, max_courses)

        max_hard_source = "auto"

        if override_max_hard is not None:
            try:
                mh = int(override_max_hard)
                max_hard_allowed = max(0, min(mh, effective_max_courses))
                max_hard_source = "override"
            except (TypeError, ValueError):
                pass

        em = (elective_emphasis or "balanced").strip().lower()

        if em not in ("major_first", "balanced", "include_electives"):
            em = "balanced"

        (
            max_major_electives_allowed,
            max_general_electives_allowed,
            CORE_W,
            SUPPORT_W,
            MAJ_ELEC_W,
            GEN_ELEC_W,
        ) = _mode_caps(em, include_electives)

        mode_targets = _mode_targets(
            em,
            effective_max_courses,
            max_major_electives_allowed,
            max_general_electives_allowed,
        )

        if em == "balanced":
            if tol <= 0.35:
                mode_targets["min_major_electives"] = 0
                mode_targets["min_general_electives"] = 1 if effective_max_courses >= 4 else 0
            else:
                mode_targets["min_major_electives"] = 1 if effective_max_courses >= 4 else 0
                mode_targets["min_general_electives"] = 1 if effective_max_courses >= 4 else 0

        sort_mode = "balanced" if em in ("balanced", "include_electives") else "major_first"
        pool_limit = 320 if em == "include_electives" else 260

        unlocked = get_unlocked_courses(
            student_id,
            filter_by_major=True,
            limit=pool_limit,
            sort_mode=sort_mode,
        )

        major_u = (student.major or "").upper()
        elective_cap = _effective_elective_credit_cap(major_u, include_electives, em)

        valid_courses: List[Dict[str, Any]] = []

        for c in unlocked:
            course_code = c.get("course_code", "")
            credit_hours = float(c.get("credit_hours", 0) or 0)

            if not course_code or course_code in completed_course_codes:
                continue

            if credit_hours <= 0:
                continue

            subj = str(c.get("subject", "") or "").upper()
            course_type = str(c.get("course_type", "") or "").strip().lower()

            if not course_type:
                if subj == major_u:
                    course_type = "core"
                elif subj in STRICT_SUPPORT_SUBJECTS:
                    course_type = "support"
                else:
                    course_type = "general_elective"

            bucket = _course_type_to_bucket(course_type, subj, student.major)

            if not include_electives and bucket == "elective":
                continue

            if em == "major_first" and subj != major_u and subj not in STRICT_SUPPORT_SUBJECTS:
                continue

            row = {
                **c,
                "course_type": course_type,
                "catalog_bucket": bucket,
                "role_label": "Major" if bucket == "major" else ("Support" if bucket == "support" else "Elective"),
            }

            valid_courses.append(row)

        if not valid_courses:
            return {
                "recommendations": [],
                "semester_workload": None,
                "academic_risk": academic_risk,
                "alternatives": [],
                "planning_params": {
                    "goal_mode": goal_mode,
                    "current_gpa": current_gpa,
                    "credit_slack": credit_slack,
                    "effective_max_credits": effective_max_credits,
                    "effective_max_courses": effective_max_courses,
                    "requested_max_courses": max_courses,
                    "target_credits_requested": target_credits,
                    "total_credits_scheduled": 0,
                    "credit_shortfall": float(target_credits),
                    "credit_warning": "No unlocked courses in the pool for this major.",
                    "elective_credits_in_plan": 0,
                    "elective_credit_cap": round(float(elective_cap), 2),
                    "include_electives": include_electives,
                    "elective_emphasis": em,
                    "workload_tolerance": tol,
                    "target_semester_gpa": target_gpa,
                    "gpa_gap": gpa_gap,
                    "max_hard_courses": max_hard_allowed,
                    "max_hard_source": max_hard_source,
                    "easy_preference_weight": round(w_easy, 3),
                    "ranking_mode": "ml_centered_hybrid_recommender",
                    "workload_model": "Academic rules validate eligibility; ML predicts course difficulty, workload, and academic risk.",
                    "ml_models_used": [
                        "Model 1: Course Difficulty Prediction",
                        "Model 2: Semester Workload Estimation",
                        "Model 3: Academic Risk Prediction",
                    ],
                    "academic_risk_score": round(academic_risk_score, 4),
                    "academic_risk_level": academic_risk.get("risk_level", "Medium"),
                },
            }

        core_courses = [c for c in valid_courses if c.get("course_type") == "core"]
        support_courses = [c for c in valid_courses if c.get("course_type") == "support"]
        major_elective_courses = [c for c in valid_courses if c.get("course_type") == "major_elective"]
        general_elective_courses = [c for c in valid_courses if c.get("course_type") == "general_elective"]

        courses_to_process = _build_candidate_pool(
            em=em,
            effective_max_courses=effective_max_courses,
            core_courses=core_courses,
            support_courses=support_courses,
            major_elective_courses=major_elective_courses,
            general_elective_courses=general_elective_courses,
        )

        scored_courses: List[Dict[str, Any]] = []

        for course_data in courses_to_process:
            course_code = course_data.get("course_code", "")

            if not course_code:
                continue

            cache_course = get_course_by_code(course_code)

            if not cache_course:
                continue

            difficulty_score, category = get_course_difficulty(course_code)
            original_category = category

            ml_difficulty_score = None
            ml_model_used = None
            ml_source = "cache"

            db_course = db.query(Course).filter(Course.course_code == course_code).first()

            if db_course:
                try:
                    pred = predict_course_difficulty(
                        student_id,
                        db_course.id,
                        override_tolerance=tol,
                        override_gpa=current_gpa,
                    )
                except TypeError:
                    pred = predict_course_difficulty(student_id, db_course.id)

                if pred and pred.get("difficulty_score") is not None:
                    ml_difficulty_score = float(pred["difficulty_score"])
                    ml_model_used = pred.get("model_used", "Model 1")
                    ml_source = pred.get("source", "ml_model")

                    difficulty_score = 0.75 * ml_difficulty_score + 0.25 * float(difficulty_score)

            gpa_val = float(student.gpa or 0.0)

            if gpa_val < 2.5 and category != "Hard":
                difficulty_score = min(1.0, difficulty_score + 0.10)
            elif gpa_val > 3.5 and category != "Hard":
                difficulty_score = max(0.0, difficulty_score - 0.08)

            if gpa_gap > 0.35:
                difficulty_score = min(1.0, difficulty_score * 1.12)
            elif gpa_gap > 0.15:
                difficulty_score = min(1.0, difficulty_score * 1.06)
            elif gpa_gap < -0.2:
                difficulty_score = max(0.0, difficulty_score * 0.92)

            difficulty_score = min(1.0, max(0.0, difficulty_score * (1.13 - 0.30 * tol)))

            subj = str(course_data.get("subject", "") or "").upper()
            cb = course_data.get("catalog_bucket") or _course_type_to_bucket(
                course_data.get("course_type", ""),
                subj,
                student.major,
            )

            difficulty_score = _apply_role_based_difficulty(
                difficulty_score,
                cb,
                int(course_data.get("course_level", 100) or 100),
                subj,
            )

            if original_category == "Hard":
                category = "Hard"
            else:
                category = _difficulty_to_category(difficulty_score)

            base_score = 1.0 - difficulty_score
            course_type = str(course_data.get("course_type", "core") or "core").strip().lower()

            if course_type == "core":
                priority_bonus = CORE_W
            elif course_type == "support":
                priority_bonus = SUPPORT_W
            elif course_type == "major_elective":
                priority_bonus = MAJ_ELEC_W
            else:
                priority_bonus = GEN_ELEC_W

            unlocks_count = int(cache_course.get("unlocks_count", 0) or 0)

            easy_boost = 1.0 + w_easy * (1.0 - difficulty_score) * 0.95
            fast_easy = 1.0 + w_easy * (1.0 - difficulty_score) * 0.48

            if student.strategy == "easy":
                score = base_score * 1.5 * easy_boost + priority_bonus
            elif student.strategy == "fast":
                unlocks_bonus = min(unlocks_count / 10.0, 0.5)
                score = (base_score + unlocks_bonus) * fast_easy + priority_bonus
            else:
                score = base_score * easy_boost + priority_bonus

            gpa_component = _clamp(gpa_val / 4.0)
            tolerance_component = _clamp(tol)
            difficulty_component = _clamp(1.0 - difficulty_score)
            risk_component = _clamp(1.0 - academic_risk_score)

            if gpa_gap > 0.10:
                goal_component = difficulty_component
            elif gpa_gap < -0.15:
                goal_component = 0.5 * difficulty_component + 0.5 * tolerance_component
            else:
                goal_component = 0.65 * difficulty_component + 0.35 * tolerance_component

            ml_fit_score = _clamp(
                0.40 * difficulty_component
                + 0.24 * tolerance_component
                + 0.16 * gpa_component
                + 0.12 * risk_component
                + 0.08 * goal_component
            )

            ml_risk_impact = _clamp(academic_risk_score * difficulty_score * (1.05 - 0.50 * tol))

            ml_score_multiplier = 1.0 + 0.24 * (ml_fit_score - 0.5) - 0.16 * ml_risk_impact
            ml_score_multiplier = max(0.78, min(1.24, ml_score_multiplier))
            score *= ml_score_multiplier

            reason = _make_recommendation_reason(
                course_data,
                category,
                difficulty_score,
                ml_fit_score,
                academic_risk,
                goal_mode,
                tol,
            )

            scored_courses.append({
                **course_data,
                "id": db_course.id if db_course else 0,
                "difficulty_score": difficulty_score,
                "difficulty_category": category,
                "recommendation_score": score,
                "catalog_bucket": cb,
                "role_label": "Major" if cb == "major" else ("Support" if cb == "support" else "Elective"),
                "term": term,

                "ml_difficulty_score": round(float(ml_difficulty_score), 4) if ml_difficulty_score is not None else round(float(difficulty_score), 4),
                "ml_difficulty_used": ml_difficulty_score is not None,
                "ml_model_used": ml_model_used or "Course cache + ML ranking",
                "ml_prediction_source": ml_source,
                "ml_fit_score": round(float(ml_fit_score), 4),
                "ml_risk_impact": round(float(ml_risk_impact), 4),
                "ml_rank_score": round(float(score), 4),
                "academic_risk_level": academic_risk.get("risk_level", "Medium"),
                "recommendation_reason": reason,
                "ai_reason": reason,
            })

        _apply_adjusted_rank_scores(scored_courses, tol, em)

        term_key = str(term or "")

        scored_courses.sort(
            key=lambda x: _rank_sort_key(
                x,
                student_id,
                term_key,
                tol,
                em,
                max_hard_allowed,
                target_credits,
            )
        )

        selected: List[Dict[str, Any]] = []
        selected_codes = set()
        total_credits = 0.0
        hard_count = 0
        subject_counts: Dict[str, int] = {}
        elective_credits_used = 0.0
        major_elective_count = 0
        general_elective_count = 0

        def try_add(course: Dict[str, Any]) -> bool:
            nonlocal total_credits, hard_count, elective_credits_used
            nonlocal major_elective_count, general_elective_count

            code = course.get("course_code", "")

            if not code or code in selected_codes:
                return False

            cat = course.get("difficulty_category", "Medium")

            if cat == "Hard" and hard_count >= max_hard_allowed:
                return False

            credit_hours = float(course.get("credit_hours", 0) or 0)

            if credit_hours <= 0:
                return False

            if total_credits + credit_hours > effective_max_credits + 1e-6:
                return False

            subj = str(course.get("subject", "") or "").upper() or "UNK"
            subj_cap = effective_max_courses if major_u and subj == major_u else _MAX_PER_NON_MAJOR_SUBJECT

            if subject_counts.get(subj, 0) >= subj_cap:
                return False

            bucket = course.get("catalog_bucket") or "major"
            course_type = str(course.get("course_type", "") or "").strip().lower()

            if bucket == "elective" and subj != major_u:
                elective_subject_cap = 1 if em in {"balanced", "major_first"} else 2
                if subject_counts.get(subj, 0) >= elective_subject_cap:
                    return False

            non_elective_selected = sum(
                1 for x in selected
                if str(x.get("catalog_bucket", "") or "") in {"major", "support"}
            )

            if course_type == "major_elective":
                if major_elective_count >= max_major_electives_allowed:
                    return False
                if em in {"major_first", "balanced"} and non_elective_selected < 2:
                    return False

            if course_type == "general_elective":
                if general_elective_count >= max_general_electives_allowed:
                    return False
                if em in {"major_first", "balanced"} and non_elective_selected < 2:
                    return False

            if bucket == "elective":
                if elective_credits_used + credit_hours > elective_cap + 1e-6:
                    return False

            selected.append(course)
            selected_codes.add(code)
            total_credits += credit_hours
            subject_counts[subj] = subject_counts.get(subj, 0) + 1

            if bucket == "elective":
                elective_credits_used += credit_hours
            if course_type == "major_elective":
                major_elective_count += 1
            if course_type == "general_elective":
                general_elective_count += 1
            if cat == "Hard":
                hard_count += 1

            return True

        core_sorted = sorted(
            [c for c in scored_courses if str(c.get("course_type", "")).strip().lower() == "core"],
            key=_bucket_order_key,
        )
        support_sorted = sorted(
            [c for c in scored_courses if str(c.get("course_type", "")).strip().lower() == "support"],
            key=_bucket_order_key,
        )
        major_elective_sorted = sorted(
            [c for c in scored_courses if str(c.get("course_type", "")).strip().lower() == "major_elective"],
            key=_bucket_order_key,
        )
        general_elective_sorted = sorted(
            [c for c in scored_courses if str(c.get("course_type", "")).strip().lower() == "general_elective"],
            key=_bucket_order_key,
        )

        def add_from_pool(pool, limit=None):
            added = 0

            for course in pool:
                if len(selected) >= effective_max_courses:
                    break

                if limit is not None and added >= limit:
                    break

                if try_add(course):
                    added += 1

            return added

        add_from_pool(core_sorted, mode_targets["min_core"])
        add_from_pool(support_sorted, mode_targets["min_support"])

        if em == "balanced":
            min_major = mode_targets.get("min_major_electives", 0)
            min_general = mode_targets.get("min_general_electives", 0)

            if min_major > 0:
                add_from_pool(
                    major_elective_sorted,
                    min(min_major, mode_targets["max_major_electives"]),
                )

            if min_general > 0:
                add_from_pool(
                    general_elective_sorted,
                    min(min_general, mode_targets["max_general_electives"]),
                )

        if em == "include_electives":
            min_general = mode_targets.get("min_general_electives", 0)

            if min_general > 0:
                add_from_pool(
                    general_elective_sorted,
                    min(min_general, mode_targets["max_general_electives"]),
                )

            electives_needed = mode_targets["min_electives"]

            already_selected_electives = sum(
                1 for x in selected
                if str(x.get("catalog_bucket", "") or "") == "elective"
            )

            electives_needed = max(0, electives_needed - already_selected_electives)

            if electives_needed > 0:
                added_major_el = add_from_pool(
                    major_elective_sorted,
                    min(electives_needed, mode_targets["max_major_electives"]),
                )
                electives_needed -= added_major_el

            if electives_needed > 0:
                add_from_pool(
                    general_elective_sorted,
                    min(electives_needed, mode_targets["max_general_electives"]),
                )

        if em == "major_first":
            preferred_order = [
                core_sorted,
                support_sorted,
                major_elective_sorted,
                general_elective_sorted,
            ]

        elif em == "balanced":
            preferred_order = [
                core_sorted,
                support_sorted,
                major_elective_sorted,
                general_elective_sorted,
                support_sorted,
                core_sorted,
            ]

        else:
            preferred_order = [
                major_elective_sorted,
                core_sorted,
                general_elective_sorted,
                support_sorted,
                core_sorted,
            ]

        loop_guard = 0

        while len(selected) < effective_max_courses and loop_guard < 40:
            loop_guard += 1
            progressed = False

            for pool in preferred_order:
                before = len(selected)
                add_from_pool(pool, 1)

                if len(selected) > before:
                    progressed = True

                if len(selected) >= effective_max_courses:
                    break

            if not progressed:
                break

        if float(target_credits) > 0 and total_credits + 1e-6 < float(target_credits):
            if em == "major_first":
                fill_order = core_sorted + support_sorted + major_elective_sorted + general_elective_sorted
            elif em == "balanced":
                fill_order = core_sorted + support_sorted + major_elective_sorted + general_elective_sorted
            else:
                fill_order = major_elective_sorted + core_sorted + general_elective_sorted + support_sorted

            for course in fill_order:
                if len(selected) >= effective_max_courses:
                    break

                if total_credits + 1e-6 >= float(target_credits):
                    break

                try_add(course)

        semester_workload: Optional[Dict[str, Any]] = None
        ids: List[int] = []

        for c in selected:
            cid = c.get("id") or 0

            if cid:
                ids.append(int(cid))

        if ids:
            try:
                semester_workload = predict_semester_workload(
                    student_id,
                    ids,
                    override_tolerance=tol,
                    override_gpa=current_gpa,
                )
            except TypeError:
                semester_workload = predict_semester_workload(student_id, ids)
            except Exception as e:
                print(f"[ML WARNING] Semester workload prediction failed: {e}")
                semester_workload = None

        shortfall = max(0.0, float(target_credits) - float(total_credits))
        credit_warning = None

        if shortfall >= 1.0 and total_credits + 1e-6 < float(target_credits):
            credit_warning = (
                f"Plan uses {total_credits:.1f} credits toward your {target_credits} target "
                f"({shortfall:.1f} short). Fewer distinct courses may be unlocked, limits on hard courses, "
                f"elective caps, or the per-subject cap may apply."
            )

        alternatives: List[Dict[str, Any]] = []
        alt_subject_counts: Dict[str, int] = {}

        for c in scored_courses:
            code = c.get("course_code", "")

            if not code or code in selected_codes:
                continue

            subj_a = str(c.get("subject", "")).upper() or "UNK"

            if alt_subject_counts.get(subj_a, 0) >= 2:
                continue

            alt_subject_counts[subj_a] = alt_subject_counts.get(subj_a, 0) + 1

            alternatives.append({
                "course_code": code,
                "name": c.get("name", ""),
                "credit_hours": float(c.get("credit_hours", 0) or 0),
                "difficulty_score": round(float(c.get("difficulty_score", 0) or 0), 4),
                "difficulty_category": c.get("difficulty_category"),
                "catalog_bucket": c.get("catalog_bucket"),
                "role_label": c.get("role_label", "Elective"),
                "subject": c.get("subject", ""),
                "ml_fit_score": c.get("ml_fit_score"),
                "ml_rank_score": c.get("ml_rank_score"),
                "academic_risk_level": c.get("academic_risk_level"),
                "recommendation_reason": c.get("recommendation_reason"),
            })

            if len(alternatives) >= 8:
                break

        planning_params = {
            "goal_mode": goal_mode,
            "current_gpa": current_gpa,
            "credit_slack": credit_slack,
            "effective_max_credits": effective_max_credits,
            "effective_max_courses": effective_max_courses,
            "requested_max_courses": max_courses,
            "target_credits_requested": target_credits,
            "total_credits_scheduled": round(float(total_credits), 2),
            "credit_shortfall": round(float(shortfall), 2),
            "credit_warning": credit_warning,
            "elective_credits_in_plan": round(float(elective_credits_used), 2),
            "elective_credit_cap": round(float(elective_cap), 2),
            "include_electives": include_electives,
            "elective_emphasis": em,
            "workload_tolerance": tol,
            "target_semester_gpa": target_gpa,
            "gpa_gap": gpa_gap,
            "max_hard_courses": max_hard_allowed,
            "max_hard_source": max_hard_source,
            "easy_preference_weight": round(w_easy, 3),

            "ranking_mode": "ml_centered_hybrid_recommender",
            "workload_model": "Academic rules validate eligibility; ML predicts course difficulty, semester workload, and academic risk.",
            "ml_models_used": [
                "Model 1: Course Difficulty Prediction",
                "Model 2: Semester Workload Estimation",
                "Model 3: Academic Risk Prediction",
            ],
            "academic_risk_score": round(float(academic_risk_score), 4),
            "academic_risk_level": academic_risk.get("risk_level", "Medium"),
            "academic_risk_model": academic_risk.get("model_used", "Model 3"),
            "ai_engine_summary": (
                "This recommendation is generated by an ML-centered hybrid engine: "
                "rules first remove invalid courses, then ML personalizes ranking using predicted "
                "difficulty, workload tolerance, GPA goal, and academic risk."
            ),
        }

        return {
            "recommendations": selected,
            "semester_workload": semester_workload,
            "academic_risk": academic_risk,
            "planning_params": planning_params,
            "alternatives": alternatives,
        }

    finally:
        db.close()


def optimize_semester_plan(student_id: int, course_ids: List[int]) -> Dict[str, Any]:
    workload = predict_semester_workload(student_id, course_ids)

    if not workload:
        return None

    difficulty = workload["semester_difficulty"]

    if difficulty < 0.33:
        difficulty_category = "Easy"
    elif difficulty < 0.67:
        difficulty_category = "Moderate"
    else:
        difficulty_category = "Challenging"

    risk = workload["overload_risk"]

    if risk < 0.3:
        risk_category = "Low"
    elif risk < 0.6:
        risk_category = "Medium"
    else:
        risk_category = "High"

    return {
        **workload,
        "difficulty_category": difficulty_category,
        "risk_category": risk_category,
    }
