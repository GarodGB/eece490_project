
from typing import List, Dict, Set, Tuple
from services.course_cache import (
    get_prerequisites,
    get_courses_by_subject,
    get_course_by_code,
    load_prerequisites_cache,
)
from services.prerequisite_service import get_completed_courses, is_course_unlocked


def build_prerequisite_graph(student_id: int, major: str = None, limit_nodes: int = 200) -> Dict:
    
    completed = get_completed_courses(student_id)
    prereq_cache = load_prerequisites_cache()
    if not prereq_cache:
        return {"nodes": [], "edges": []}

    all_codes: Set[str] = set()
    for course_code, prereqs in prereq_cache.items():
        all_codes.add(course_code)
        all_codes.update(prereqs)

    if major:
        major_courses = {c.get("course_code") for c in get_courses_by_subject(major) if c.get("course_code")}
        reachable = set(major_courses)
        for code in list(reachable):
            reachable.update(prereq_cache.get(code, []))
        all_codes &= reachable

    all_codes = set(list(all_codes)[:limit_nodes * 2])

    nodes: List[Dict] = []
    seen_nodes: Set[str] = set()
    edges: List[Dict] = []

    for course_code in all_codes:
        if not course_code or course_code in seen_nodes:
            continue
        seen_nodes.add(course_code)
        info = get_course_by_code(course_code) or {}
        name = (info.get("name") or course_code)[:40]
        credits = float(info.get("credit_hours") or 3.0)

        if course_code in completed:
            status = "completed"
        else:
            unlocked, _ = is_course_unlocked(student_id, course_code, completed_courses=completed)
            status = "unlocked" if unlocked else "locked"

        nodes.append({
            "id": course_code,
            "label": course_code,
            "title": f"{course_code} – {name} ({credits} cr)\nStatus: {status}",
            "status": status,
            "credits": credits,
        })

    for course_code, prereqs in prereq_cache.items():
        if course_code not in seen_nodes:
            continue
        for prereq in prereqs:
            if prereq in seen_nodes and prereq != course_code:
                edges.append({"from": prereq, "to": course_code})

    def order_key(n):
        s = n["status"]
        return (0 if s == "completed" else 1 if s == "unlocked" else 2, n["id"])
    nodes.sort(key=order_key)
    if len(nodes) > limit_nodes:
        nodes = nodes[:limit_nodes]
        node_ids = {n["id"] for n in nodes}
        edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]

    return {"nodes": nodes, "edges": edges}
