#!/usr/bin/env python3
"""Unit checks: major modeled harder than electives; tolerance changes adjusted rank."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from services.recommendation_engine import (  # noqa: E402
    _apply_role_based_difficulty,
    _apply_adjusted_rank_scores,
)


def test_major_harder_than_elective():
    base = 0.55
    maj = _apply_role_based_difficulty(base, "major", 300, "ECE")
    ele = _apply_role_based_difficulty(base, "elective", 300, "PSYC")
    sup = _apply_role_based_difficulty(base, "support", 200, "MATH")
    assert maj > base, (maj, base)
    assert ele < base, (ele, base)
    assert maj > sup > ele, (maj, sup, ele)
    print("OK: major > support > elective difficulty at same nominal base")


def test_tolerance_changes_adjusted_score():
    rows = [
        {
            "course_code": "ECE301",
            "recommendation_score": 0.7,
            "difficulty_score": 0.75,
            "catalog_bucket": "major",
        },
        {
            "course_code": "PSYC101",
            "recommendation_score": 0.72,
            "difficulty_score": 0.35,
            "catalog_bucket": "elective",
        },
    ]
    r_low = [dict(x) for x in rows]
    r_high = [dict(x) for x in rows]
    _apply_adjusted_rank_scores(r_low, 0.1, "balanced")
    _apply_adjusted_rank_scores(r_high, 0.9, "balanced")
    assert r_low[0]["adjusted_rank_score"] != r_high[0]["adjusted_rank_score"]
    assert r_low[1]["adjusted_rank_score"] != r_high[1]["adjusted_rank_score"]
    print("OK: tolerance changes adjusted_rank_score")


if __name__ == "__main__":
    test_major_harder_than_elective()
    test_tolerance_changes_adjusted_score()
    print("All role-model tests passed.")
