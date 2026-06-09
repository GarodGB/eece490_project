"""
Rebuild Data/courses_index.json from Data/merged_courses.csv, preserving difficulty
fields from the previous JSON when course codes match.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "Data"
MERGED = DATA / "merged_courses.csv"
JSON_PATH = DATA / "courses_index.json"


def main():
    df = pd.read_csv(MERGED)
    old_by_code = {}
    if JSON_PATH.exists():
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            old_list = json.load(f)
        old_by_code = {c["course_code"]: c for c in old_list if c.get("course_code")}

    out = []
    for _, row in df.iterrows():
        code = str(row.get("course_code", "")).strip()
        if not code:
            continue
        base = {
            "course_code": code,
            "subject": str(row.get("subject", "")).strip(),
            "number": str(row.get("number", "")).strip(),
            "name": str(row.get("name", "")).strip(),
            "description": str(row.get("description", "")).strip(),
            "credit_hours": float(row.get("credit_hours", 3) or 3),
            "course_level": int(float(row.get("course_level", 100) or 100)),
            "is_lab": bool(row.get("is_lab", False)),
            "is_major_course": bool(row.get("is_major_course", True)),
            "prerequisite_count": int(float(row.get("prerequisite_count", 0) or 0)),
            "prerequisite_depth": int(float(row.get("prerequisite_depth", 0) or 0)),
            "graph_centrality": float(row.get("graph_centrality", 0.0) or 0.0),
            "unlocks_count": int(float(row.get("unlocks_count", 0) or 0)),
        }
        if code in old_by_code:
            o = old_by_code[code]
            base["difficulty_score"] = float(o.get("difficulty_score", 0.5) or 0.5)
            base["difficulty_category"] = str(o.get("difficulty_category", "Medium") or "Medium")
            base["avg_grade_points"] = float(o.get("avg_grade_points", 2.5) or 2.5)
            base["num_students"] = int(o.get("num_students", 0) or 0)
        else:
            base["difficulty_score"] = 0.5
            base["difficulty_category"] = "Medium"
            base["avg_grade_points"] = 2.5
            base["num_students"] = 0
        out.append(base)

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wrote {len(out)} courses to {JSON_PATH}")


if __name__ == "__main__":
    main()
