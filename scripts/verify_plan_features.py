#!/usr/bin/env python3
"""Quick verification of plan features: prereqs, tolerance-driven params, APIs."""
import json
import sys
import time
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


def main():
    suffix = str(int(time.time()))[-6:]
    username = f"verify_{suffix}"
    email = f"{username}@test.local"

    client = app.test_client()

    # Register
    r = client.post(
        "/api/register",
        json={
            "username": username,
            "email": email,
            "password": "TestPass123!",
            "major": "ECE",
            "strategy": "balanced",
            "workload_tolerance": 0.5,
        },
        content_type="application/json",
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    assert r.get_json().get("success") is True

    # Profile: tolerance 0.1
    r = client.put(
        "/api/student/profile",
        json={"workload_tolerance": 0.1, "target_semester_gpa": 3.5},
        content_type="application/json",
    )
    assert r.status_code == 200, r.get_data(as_text=True)

    r = client.get("/api/recommendations?credits=15&max_courses=10&term=Fall")
    assert r.status_code == 200
    j1 = r.get_json()
    p1 = j1.get("planning_params") or {}
    n1 = len(j1.get("recommendations") or [])

    # Profile: tolerance 0.9
    r = client.put(
        "/api/student/profile",
        json={"workload_tolerance": 0.9},
        content_type="application/json",
    )
    assert r.status_code == 200

    r = client.get("/api/recommendations?credits=15&max_courses=10&term=Fall")
    assert r.status_code == 200
    j2 = r.get_json()
    p2 = j2.get("planning_params") or {}
    n2 = len(j2.get("recommendations") or [])

    print("=== Tolerance 0.1 vs 0.9 (max_courses request = 10) ===")
    print("planning_params @ 0.1:", json.dumps({k: p1.get(k) for k in sorted(p1)}, indent=2))
    print("planning_params @ 0.9:", json.dumps({k: p2.get(k) for k in sorted(p2)}, indent=2))
    print(f"Recommendation count @ 0.1: {n1}")
    print(f"Recommendation count @ 0.9: {n2}")

    assert p1.get("credit_slack") != p2.get("credit_slack"), "credit_slack should differ"
    assert p1.get("effective_max_credits") == p1.get("target_credits_requested") == 15
    assert p2.get("effective_max_credits") == p2.get("target_credits_requested") == 15
    assert p1.get("effective_max_courses") != p2.get("effective_max_courses"), "effective_max_courses should differ"

    # Prerequisite: locked 300-level should fail without prereqs (pick a course that has prereqs)
    from services.course_cache import get_prerequisites

    locked_code = None
    for code in ["CS301", "ECE301", "MATH301"]:
        pr = get_prerequisites(code)
        if pr:
            locked_code = code
            break
    if locked_code:
        r = client.post(
            "/api/courses/completed",
            json={
                "course_code": locked_code,
                "grade": "A",
                "semester_taken": 1,
            },
            content_type="application/json",
        )
        assert r.status_code == 400, f"Expected 400 for locked {locked_code}, got {r.status_code}"
        err = r.get_json()
        assert err.get("prerequisite_error") or err.get("missing_prerequisites"), err
        print(f"=== Prereq block OK: cannot add {locked_code} without prereqs ===")
    else:
        print("=== Skip prereq test: no sample locked course with prereqs in index ===")

    # Insights + timeline
    r = client.get("/api/student/insights")
    assert r.status_code == 200 and r.get_json().get("success")
    r = client.get("/api/student/semester-timeline")
    assert r.status_code == 200 and r.get_json().get("success")

    print("=== insights + semester-timeline: OK ===")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
