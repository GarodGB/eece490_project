#!/usr/bin/env python3
"""
Automated checks for advisor / insights / semester journey scenarios discussed for the project.

Run from project root (use the project venv if you see ``ModuleNotFoundError: flask``):

  .venv/bin/python3 scripts/verify_advisor_scenarios.py

  # or: source .venv/bin/activate && python3 scripts/verify_advisor_scenarios.py
  # or: python3 -m pip install -r requirements.txt

Uses Flask test client (no server). Registers a throwaway user, adds courses with
semester numbers, then validates APIs and rule-based chatbot paths (no OpenAI required).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    import flask  # noqa: F401 — verify deps before importing app
except ModuleNotFoundError:
    venv_python = ROOT / ".venv" / "bin" / "python3"
    print(
        "Flask is not installed for this Python interpreter.\n"
        f"  Try: {venv_python} scripts/verify_advisor_scenarios.py\n"
        "  Or:   python3 -m pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

from app import app


def _post_json(client, path: str, data: dict):
    return client.post(path, json=data, content_type="application/json")


def _assert(cond: bool, msg: str):
    if not cond:
        raise AssertionError(msg)


def main():
    suffix = str(int(time.time()))[-6:]
    username = f"adv_scen_{suffix}"
    email = f"{username}@test.local"
    client = app.test_client()

    # --- Register (session cookie set) ---
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
    _assert(r.status_code == 200, r.get_data(as_text=True))
    _assert(r.get_json().get("success") is True, "register failed")

    def add_course(code: str, grade: str, semester: int):
        rr = _post_json(
            client,
            "/api/courses/completed",
            {"course_code": code, "grade": grade, "semester_taken": semester},
        )
        _assert(
            rr.status_code == 200,
            f"add {code}: {rr.status_code} {rr.get_data(as_text=True)}",
        )
        _assert(rr.get_json().get("success") is True, rr.get_json())

    # No-prerequisite courses from the final catalogue.
    add_course("MATH201", "A", 1)
    add_course("ENGL203", "B+", 1)
    add_course("MATH202", "A-", 2)

    # --- Semester timeline API (journey visualization data) ---
    r = client.get("/api/student/semester-timeline")
    _assert(r.status_code == 200, r.get_data(as_text=True))
    tj = r.get_json()
    _assert(tj.get("success") is True, tj)
    data = tj.get("data") or {}
    semesters = data.get("semesters") or []
    _assert(len(semesters) == 2, f"expected 2 semesters, got {len(semesters)}")
    codes_s1 = {c["course_code"] for c in semesters[0].get("courses", [])}
    codes_s2 = {c["course_code"] for c in semesters[1].get("courses", [])}
    _assert("MATH201" in codes_s1 and "ENGL203" in codes_s1, f"sem1 codes: {codes_s1}")
    _assert("MATH202" in codes_s2, f"sem2 codes: {codes_s2}")
    _assert(semesters[0].get("semester") == 1, semesters[0])
    _assert(semesters[1].get("semester") == 2, semesters[1])
    print("=== semester-timeline: Semester 1 (MATH201, ENGL203), Semester 2 (MATH202) OK ===")

    # --- Insights API (path risks, recommendations preview, stats) ---
    r = client.get("/api/student/insights")
    _assert(r.status_code == 200, r.get_data(as_text=True))
    ins = r.get_json()
    _assert(ins.get("success") is True, ins)
    d = ins.get("data") or {}
    for key in (
        "stats",
        "suggestions",
        "next_semester_candidates",
        "bottleneck_courses",
        "warnings",
        "prerequisite_risks",
        "recommendation_preview",
        "delayed_foundations",
    ):
        _assert(key in d, f"missing insights key: {key}")
    _assert("major" in d and d.get("major") == "ECE", d)
    st = d.get("stats") or {}
    _assert(st.get("semesters_recorded") == 2, st)
    _assert(float(st.get("total_credits_completed") or 0) > 0, st)
    print("=== insights: stats + lists present OK ===")

    # --- Advisor chat: deterministic rule paths (no OpenAI dependency) ---
    def chat(q: str) -> str:
        rr = _post_json(client, "/api/advisor/chat", {"question": q})
        _assert(rr.status_code == 200, rr.get_data(as_text=True))
        cj = rr.get_json()
        _assert(cj.get("success") is True, cj)
        return (cj.get("response") or "").strip()

    r_gpa = chat("What is my GPA?")
    _assert("gpa" in r_gpa.lower() or "4" in r_gpa or "3" in r_gpa, r_gpa[:500])
    print("=== chat 'What is my GPA?': mentions GPA/grades OK ===")

    r_hist = chat("what did i take each semester")
    low = r_hist.lower()
    _assert("semester 1" in low or "semester 1:" in low.replace(" ", ""), r_hist[:800])
    _assert("math201" in low, r_hist[:800])
    _assert("math202" in low, r_hist[:800])
    print("=== chat semester history: lists Semester 1/2 and course codes OK ===")

    r_hi = chat("Hello!")
    _assert("ece" in r_hi.lower() or "advisor" in r_hi.lower(), r_hi[:400])
    print("=== chat hello: personalized OK ===")

    # --- Bottlenecks endpoint (used by Bottlenecks tab) ---
    r = client.get("/api/advisor/bottlenecks")
    _assert(r.status_code == 200, r.get_data(as_text=True))
    bj = r.get_json()
    _assert(bj.get("success") is True, bj)
    _assert(isinstance(bj.get("bottlenecks"), list), bj)
    print(f"=== bottlenecks: {len(bj.get('bottlenecks') or [])} items OK ===")

    # --- Course search includes catalog_tag + electives for ECE major ---
    r = client.get("/api/courses/search")
    _assert(r.status_code == 200, r.get_data(as_text=True))
    sj = r.get_json()
    _assert(sj.get("success") is True, sj)
    courses = sj.get("courses") or []
    _assert(len(courses) > 10, "browse catalog should list many courses")
    first = courses[0]
    _assert("catalog_tag" in first, first)
    tags = {c.get("catalog_tag") for c in courses[:80]}
    _assert("major" in tags or "elective" in tags, f"tags sample: {tags}")
    print("=== courses/search (empty q): major + elective catalog OK ===")

    r = client.get("/api/courses/search?q=MATH")
    _assert(r.status_code == 200, r.get_data(as_text=True))
    _assert(r.get_json().get("success") is True, r.get_json())
    codes = [c.get("course_code") for c in (r.get_json().get("courses") or [])]
    _assert(any("MATH" in (x or "") for x in codes), codes[:20])
    print("=== courses/search?q=MATH: finds mathematics courses OK ===")

    print("")
    print("ALL ADVISOR / INSIGHTS / JOURNEY SCENARIOS PASSED")


if __name__ == "__main__":
    main()
