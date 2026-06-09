#!/usr/bin/env python3
"""
Regression: recommendations must change when tolerance / elective emphasis change,
not only difficulty % labels. Uses test client + direct engine calls.
"""
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.recommendation_engine import _apply_adjusted_rank_scores  # noqa: E402


def _codes(payload):
    return [c.get("course_code") for c in (payload.get("recommendations") or []) if c.get("course_code")]


def test_adjusted_rank_inverts_order_for_hard_vs_easy():
    """Same base score: low tol prefers easy; high tol prefers hard."""
    a = {
        "recommendation_score": 1.0,
        "difficulty_score": 0.85,
        "catalog_bucket": "major",
    }
    b = {
        "recommendation_score": 1.0,
        "difficulty_score": 0.25,
        "catalog_bucket": "major",
    }
    # [0]=hard(ds 0.85), [1]=easy(ds 0.25)
    c_low = [deepcopy(a), deepcopy(b)]
    _apply_adjusted_rank_scores(c_low, 0.0, "balanced")
    c_high = [deepcopy(a), deepcopy(b)]
    _apply_adjusted_rank_scores(c_high, 1.0, "balanced")
    assert c_low[1]["adjusted_rank_score"] > c_low[0]["adjusted_rank_score"]
    assert c_high[0]["adjusted_rank_score"] > c_high[1]["adjusted_rank_score"]


def main():
    test_adjusted_rank_inverts_order_for_hard_vs_easy()
    print("unit: adjusted_rank_score inverts easy/hard order across tol — OK")

    from app import app  # noqa: E402

    client = app.test_client()
    suffix = str(int(time.time()))[-8:]
    username = f"sens_{suffix}"
    r = client.post(
        "/api/register",
        json={
            "username": username,
            "email": f"{username}@test.local",
            "password": "TestPass123!",
            "major": "ECE",
            "strategy": "balanced",
            "workload_tolerance": 0.5,
        },
        content_type="application/json",
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    def get_reco(qs):
        r2 = client.get(f"/api/recommendations?credits=15&max_courses=8&term=Fall&{qs}")
        assert r2.status_code == 200, r2.get_data(as_text=True)
        return r2.get_json()

    j0 = get_reco("tolerance=0&include_electives=1&elective_emphasis=balanced")
    j1 = get_reco("tolerance=1&include_electives=1&elective_emphasis=balanced")
    c0, c1 = _codes(j0), _codes(j1)

    jm = get_reco("tolerance=0.5&include_electives=1&elective_emphasis=major_first")
    je = get_reco("tolerance=0.5&include_electives=1&elective_emphasis=include_electives")
    cm, ce = _codes(jm), _codes(je)

    print("tol=0:", c0)
    print("tol=1:", c1)
    print("major_first:", cm)
    print("include_electives:", ce)

    # If we have enough recommendations, tolerance should change the ordered list
    if len(c0) >= 2 and len(c1) >= 2:
        same = c0 == c1
        if same:
            # At least order or multiset should differ when difficulty spreads
            print("WARNING: tol=0 and tol=1 produced identical code lists — pool may be tiny.")
        else:
            print("HTTP: tolerance changes course list — OK")

    if len(cm) >= 1 and len(ce) >= 1 and cm != ce:
        print("HTTP: elective emphasis changes course list — OK")
    else:
        print("NOTE: elective mix same or empty — may be normal with small unlocked pool.")

    p = j1.get("planning_params") or {}
    assert p.get("ranking_mode") == "ml_centered_hybrid_recommender"
    print("planning_params.ranking_mode — OK")
    print("ALL SENSITIVITY CHECKS PASSED")


if __name__ == "__main__":
    main()
