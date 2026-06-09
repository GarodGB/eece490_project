"""
Append a large batch of synthetic catalog rows to Data/merged_courses.csv.
Skips any course_code that already exists. Run sync_courses_index_from_merged.py after.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "Data" / "merged_courses.csv"


def load_existing_codes() -> set[str]:
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return {row["course_code"].strip() for row in r if row.get("course_code")}


def esc_field(s: str) -> str:
    if '"' in s or "," in s or "\n" in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def row(
    code: str,
    subj: str,
    num: str,
    name: str,
    desc: str,
    credits: float,
    level: int,
    is_lab: bool,
    is_major: bool,
    prereq_n: int,
) -> str:
    return ",".join(
        [
            code,
            subj,
            num,
            esc_field(name),
            esc_field(desc),
            str(credits),
            str(level),
            str(is_lab).title(),
            str(is_major).title(),
            str(prereq_n),
            "0",
            "0.0",
            "0",
        ]
    )


def main():
    existing = load_existing_codes()
    new_lines: list[str] = []

    def add_if_new(
        code: str,
        subj: str,
        num: str,
        name: str,
        desc: str,
        credits: float = 3.0,
        level: int | None = None,
        is_lab: bool = False,
        is_major: bool = False,
        prereq_n: int = 0,
    ):
        nonlocal new_lines
        if code in existing:
            return
        existing.add(code)
        if level is None:
            try:
                d = "".join(c for c in num if c.isdigit())
                level = int(d[0]) * 100 if d else 100
            except Exception:
                level = 100
        new_lines.append(
            row(code, subj, num, name, desc, credits, level, is_lab, is_major, prereq_n)
        )

    # --- Extra breadth under existing gen-ed / social subjects ---
    extras = [
        ("ECON", [(f"11{i}", f"Topics in Economics {i}", f"Selected topics in economic analysis and policy themes. Section {i}.") for i in range(1, 10)]),
        ("PSYC", [(f"15{i}", f"Applied Psychology Workshop {i}", f"Hands-on applications of psychological science to everyday problems. Module {i}.") for i in range(1, 12)]),
        ("SOC", [(f"21{i}", f"Contemporary Issues in Society {i}", f"Seminar on current social debates and evidence. Topic cluster {i}.") for i in range(1, 11)]),
        ("POL", [(f"22{i}", f"Global Affairs Seminar {i}", f"Regional politics, security, and institutions. Region focus {i}.") for i in range(1, 10)]),
        ("ENGL", [(f"21{i}", f"Literature and Culture {i}", f"Genre, period, or author studies in English. Cluster {i}.") for i in range(1, 14)]),
        ("PHIL", [(f"15{i}", f"Moral Problems in Practice {i}", f"Case-based ethics across professions and cultures. Unit {i}.") for i in range(1, 10)]),
        ("HIST", [(f"21{i}", f"Regional History Topics {i}", f"Comparative and regional historical inquiry. Area {i}.") for i in range(1, 12)]),
        ("ART", [(f"11{i}", f"Studio Topics {i}", f"Exploratory studio practice in visual arts. Section {i}.") for i in range(1, 11)]),
        ("MUS", [(f"21{i}", f"Ensemble and Performance Lab {i}", f"Small ensemble work and performance skills. Group {i}.") for i in range(1, 10)]),
        ("BUS", [(f"15{i}", f"Business Skills Studio {i}", f"Professional skills: presentations, teamwork, and analytics. Lab {i}.") for i in range(1, 11)]),
        ("BIO", [(f"11{i}", f"Biology in Society {i}", f"Biotechnology, ecology, and health from a civic perspective. Theme {i}.") for i in range(1, 10)]),
        ("STAT", [(f"21{i}", f"Data Literacy Workshop {i}", f"Interpreting charts, studies, and uncertainty in the news. Unit {i}.") for i in range(1, 12)]),
    ]
    for subj, pairs in extras:
        for num, name, desc in pairs:
            add_if_new(f"{subj}{num}", subj, num, name, desc)

    # --- New language & culture subjects ---
    lang_blocks = {
        "FREN": "French",
        "GER": "German",
        "ITAL": "Italian",
        "JAP": "Japanese",
        "KORE": "Korean",
        "ARAB": "Arabic",
        "PORT": "Portuguese",
        "RUSS": "Russian",
        "HEBR": "Hebrew",
        "LATN": "Latin",
        "GREK": "Ancient Greek",
        "SWAH": "Swahili",
    }
    for subj, lang in lang_blocks.items():
        for num, title, desc in [
            ("101", f"Elementary {lang} I", f"Introduction to {lang} grammar, vocabulary, and culture."),
            ("102", f"Elementary {lang} II", f"Continued elementary {lang} communication and culture."),
            ("201", f"Intermediate {lang} I", f"Conversation, reading, and composition at intermediate level."),
            ("202", f"Intermediate {lang} II", f"Further intermediate skills and cultural contexts."),
        ]:
            add_if_new(f"{subj}{num}", subj, num, title, desc)

    # --- Humanities / arts / media ---
    hum = [
        ("THEA", "110", "Introduction to Theatre", "Acting, directing, design, and theatre history overview."),
        ("THEA", "120", "Voice and Movement", "Physical expression and vocal technique for performance."),
        ("WGSS", "101", "Introduction to Gender Studies", "Gender, sexuality, and intersectional analysis."),
        ("WGSS", "201", "Feminist Theory", "Classic and contemporary feminist thought."),
        ("JOUR", "101", "Media and Society", "News, social media, and democratic discourse."),
        ("JOUR", "201", "Reporting Fundamentals", "Interviewing, fact-checking, and story structure."),
        ("RTVF", "105", "Introduction to Film and Television", "Narrative, documentary, and industry basics."),
        ("RTVF", "205", "Digital Media Production", "Shooting, editing, and distribution basics."),
        ("CLAS", "110", "Classical Mythology", "Greek and Roman myths in literature and art."),
        ("CLAS", "210", "Ancient Rome and Greece", "Political and cultural history of classical antiquity."),
        ("URST", "101", "Introduction to Urban Studies", "Cities, planning, and sustainability."),
        ("URST", "201", "Housing and Community Development", "Policy, equity, and neighborhood change."),
        ("CRIM", "101", "Introduction to Criminology", "Crime patterns, policing, and justice systems."),
        ("CRIM", "201", "Corrections and Rehabilitation", "Institutions, probation, and reentry."),
        ("SWRK", "101", "Introduction to Social Work", "Values, fields of practice, and helping professions."),
        ("DESN", "105", "Design Thinking", "Human-centered design for products and services."),
        ("DESN", "205", "Visual Communication Design", "Layout, typography, and digital tools."),
        ("ARCH", "101", "Introduction to Architecture", "Space, form, and architectural representation."),
        ("GAME", "110", "Introduction to Game Design", "Mechanics, narrative, and player experience."),
        ("DATA", "110", "Data Literacy for Everyone", "Spreadsheets, charts, and responsible use of data."),
        ("DATA", "210", "Introduction to Data Ethics", "Privacy, bias, and governance of data systems."),
        ("HLTH", "101", "Personal and Community Health", "Wellness, prevention, and public health basics."),
        ("PHED", "150", "Fitness and Wellness", "Exercise principles, nutrition, and habit formation."),
        ("RECR", "120", "Outdoor Recreation Leadership", "Risk management and outdoor skills."),
        ("EVSC", "101", "Introduction to Environmental Science", "Earth systems, pollution, and sustainability."),
        ("SUST", "101", "Sustainability and Society", "Climate, resources, and social change."),
        ("ENVS", "201", "Environmental Policy", "Laws, incentives, and stakeholder perspectives."),
        ("ASTR", "110", "Descriptive Astronomy", "Solar system, stars, and cosmology for non-majors."),
        ("ASTR", "210", "Life in the Universe", "Exoplanets, astrobiology, and the Drake equation."),
        ("GEOL", "110", "Physical Geology", "Rocks, plate tectonics, and Earth processes."),
        ("GEOL", "210", "Environmental Geology", "Hazards, water, and human-environment interaction."),
        ("OCEA", "101", "Introduction to Oceanography", "Physical and biological ocean systems."),
        ("METR", "105", "Weather and Climate", "Atmospheric science for everyday decision-making."),
        ("FORS", "101", "Introduction to Forensic Science", "Evidence, lab methods, and criminalistics overview."),
    ]
    for subj, num, name, desc in hum:
        add_if_new(f"{subj}{num}", subj, num, name, desc)

    # --- More STEM service / elective numbers (often "support" for engineers) ---
    stem = []
    for i in range(1, 16):
        stem.append(
            (
                "MATH",
                f"15{i}",
                f"Applied Mathematics Topics {i}",
                f"Selected applications: modeling, finance, or engineering math. Module {i}.",
            )
        )
    for j in range(1, 12):
        stem.append(
            (
                "PHYS",
                str(120 + j),
                f"Physics Concepts for Innovators {j}",
                f"Conceptual physics themes with demos and problem solving. Unit {j}.",
            )
        )
    for j in range(1, 12):
        stem.append(
            (
                "CHEM",
                str(110 + j),
                f"Chemistry and Everyday Life {j}",
                f"Molecules, reactions, and society-facing topics. Theme {j}.",
            )
        )
    for subj, num, name, desc in stem:
        add_if_new(f"{subj}{num}", subj, num, name, desc, is_major=True)

    # --- CS / CSE / ECE professional electives (sample set) ---
    tech_topics = [
        ("CS", "150", "Introduction to Web Technologies", "HTML, CSS, HTTP, and basic client-side scripting."),
        ("CS", "151", "Introduction to Databases for Applications", "SQL, ER modeling, and simple backends."),
        ("CS", "160", "Introduction to Cybersecurity Literacy", "Threat models, passwords, and safe computing."),
        ("CSE", "150", "Software Tools for Engineers", "Version control, build systems, and scripting."),
        ("CSE", "151", "Systems Programming Workshop", "C programming, memory, and debugging."),
        ("ECE", "150", "Hands-on Electronics", "Breadboards, sensors, and simple embedded projects."),
        ("ECE", "151", "Introduction to Robotics Studio", "Kinematics, control basics, and team projects."),
        ("ECE", "250", "IoT Systems Overview", "Protocols, edge devices, and cloud integration."),
        ("ECE", "251", "Hardware Description Languages Lab", "Introductory Verilog/VHDL and simulation."),
    ]
    for subj, num, name, desc in tech_topics:
        add_if_new(f"{subj}{num}", subj, num, name, desc, is_major=True, prereq_n=0)

    # --- Additional cross-disciplinary seminars ---
    for i in range(1, 21):
        n = 200 + i
        add_if_new(
            f"INTD{n}",
            "INTD",
            str(n),
            f"Interdisciplinary Seminar {i}",
            f"Team-taught topics bridging two or more fields. Seminar {i}.",
        )

    # --- Nursing / health professions (introductory) ---
    for i in range(1, 26):
        num = 100 + i
        add_if_new(
            f"NURS{num}",
            "NURS",
            str(num),
            f"Nursing Foundations Topic {i}",
            f"Foundations of nursing practice, pathophysiology, or clinical skills. Module {i}.",
        )

    # --- More CS / ECE electives (3-digit numbers so course_level maps to 100/200/300) ---
    for j in range(160, 190):
        add_if_new(
            f"CS{j}",
            "CS",
            str(j),
            f"CS Elective Topics {j - 159}",
            f"Special topics in computing: tools, domains, or project studios. Offering {j - 159}.",
            level=200,
            is_major=True,
        )
    for j in range(160, 185):
        add_if_new(
            f"ECE{j}",
            "ECE",
            str(j),
            f"ECE Elective Lab/Studio {j - 159}",
            f"Hands-on topics in circuits, signals, or embedded systems. Studio {j - 159}.",
            level=200,
            is_lab=(j % 3 == 0),
            is_major=True,
        )

    # --- Philosophy / English depth (avoid PHIL301-302, ENGL301-302) ---
    for num in range(303, 331):
        add_if_new(
            f"PHIL{num}",
            "PHIL",
            str(num),
            f"Advanced Philosophy Seminar {num - 302}",
            f"Focused readings and writing in philosophy. Section {num - 302}.",
            level=300,
            prereq_n=1,
        )
    for num in range(303, 328):
        add_if_new(
            f"ENGL{num}",
            "ENGL",
            str(num),
            f"Literature Seminar {num - 302}",
            f"Author-, genre-, or period-focused study. Seminar {num - 302}.",
            level=300,
            prereq_n=1,
        )

    # --- Extra geography / regional studies ---
    for i in range(1, 18):
        num = 200 + i
        add_if_new(
            f"GEOG{num}",
            "GEOG",
            str(num),
            f"Regional Geography {i}",
            f"Human and physical geography of world regions. Region {i}.",
        )

    if not new_lines:
        print("No new rows to append (all codes existed).")
        return

    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        for line in new_lines:
            f.write(line + "\n")

    print(f"Appended {len(new_lines)} courses to {CSV_PATH}")


if __name__ == "__main__":
    main()
