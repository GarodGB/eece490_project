#!/usr/bin/env python3
"""
Diagnostic for the "only one course recommended" scenario (e.g. ECE 106 only).

Usage (from project root):
  python3 scripts/verify_unlocked_pool.py [student_id]

Prints major, count of unlocked courses for that student, and sample codes.
If the pool has only one major course, recommendations cannot diversify.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> None:
    sid = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    from database.db import get_db
    from database.models import Student
    from services.prerequisite_service import get_unlocked_courses
    from services.recommendation_engine import recommend_courses

    db = get_db()
    try:
        st = db.query(Student).filter(Student.id == sid).first()
        if not st:
            print(f"No student id={sid}")
            return
        major = st.major or "(none)"
        print(f"Student {sid} major={major} GPA={st.gpa}")

        unlocked = get_unlocked_courses(sid, filter_by_major=True)
        major_rows = [u for u in unlocked if u.get("is_major_course")]
        print(f"Unlocked (filtered): {len(unlocked)} total, {len(major_rows)} flagged major_course")
        for i, u in enumerate(unlocked[:25]):
            print(f"  {u.get('course_code')}  subject={u.get('subject')}  major={u.get('is_major_course')}")
        if len(unlocked) > 25:
            print(f"  ... ({len(unlocked) - 25} more)")

        reco = recommend_courses(sid, target_credits=15, max_courses=6, term="Fall")
        recs = reco.get("recommendations") or []
        print(f"recommend_courses sample: {len(recs)} picks -> {[r.get('course_code') for r in recs]}")
        if reco.get("planning_params"):
            print(f"planning_params: {reco['planning_params']}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
