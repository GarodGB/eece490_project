import csv
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"

COURSES_FILE = DATA_DIR / "merged_courses.csv"
PREREQ_FILE = DATA_DIR / "prerequisites.csv"
COURSES_INDEX_FILE = DATA_DIR / "courses_index.json"
PREREQ_INDEX_FILE = DATA_DIR / "prerequisites_index.json"
MAJORS_FILE = DATA_DIR / "majors.json"

COURSE_COLUMNS = [
    "course_code", "subject", "number", "name", "description", "credit_hours",
    "course_level", "is_lab", "is_major_course", "prerequisite_count",
    "prerequisite_depth", "graph_centrality", "unlocks_count", "course_type",
]


def course(code, subject, number, name, desc, credits, is_lab, is_major, course_type):
    return {
        "course_code": code,
        "subject": subject,
        "number": number,
        "name": name,
        "description": desc,
        "credit_hours": credits,
        "course_level": (number // 100) * 100,
        "is_lab": str(bool(is_lab)),
        "is_major_course": str(bool(is_major)),
        "course_type": course_type,
    }


COURSES = [
    # Required engineering / math / science / English support
    # course_type="support" means required non-EECE support, not optional.
    course("FEAA200", "FEAA", 200, "Introduction to Engineering and Architecture", "Required first-term engineering design, teamwork, ethics, and problem solving.", 3, False, True, "support"),
    course("INDE301", "INDE", 301, "Engineering Economy", "Required engineering economic analysis and decision making.", 3, False, True, "support"),
    course("INDE410", "INDE", 410, "Engineering Management / Human Values", "Required engineering management and human values component.", 3, False, True, "support"),
    course("MATH201", "MATH", 201, "Calculus III", "Required multivariable calculus and vector calculus for engineering.", 3, False, True, "support"),
    course("MATH202", "MATH", 202, "Differential Equations", "Required ordinary differential equations and engineering applications.", 3, False, True, "support"),
    course("MATH211", "MATH", 211, "Discrete Structures", "Required/allowed discrete mathematics option for computing-oriented programs.", 3, False, True, "support"),
    course("CMPS211", "CMPS", 211, "Discrete Structures", "Discrete structures option used in computing-oriented engineering paths.", 3, False, True, "support"),
    course("MATH218", "MATH", 218, "Linear Algebra with Applications", "Required/allowed linear algebra with engineering applications.", 3, False, True, "support"),
    course("MATH251", "MATH", 251, "Numerical Computing", "Numerical methods and computational problem solving.", 3, False, True, "support"),
    course("STAT230", "STAT", 230, "Probability and Random Variables", "Required probability, random variables, and engineering statistics.", 3, False, True, "support"),
    course("PHYS210", "PHYS", 210, "Introductory Physics II", "Required electricity, magnetism, waves, and engineering physics.", 3, False, True, "support"),
    course("PHYS210L", "PHYS", 210, "Introductory Physics II Laboratory", "Required physics laboratory accompanying PHYS 210.", 1, True, True, "support"),
    course("CHEM201", "CHEM", 201, "General Chemistry for Engineers", "Chemistry principles for engineering students, including bonding, materials, and reactions.", 3, False, True, "support"),
    course("CHEM203", "CHEM", 203, "Introductory Chemistry Laboratory", "Laboratory experiments supporting general chemistry.", 1, True, True, "support"),
    course("ENGL203", "ENGL", 203, "Academic English", "Required academic reading, writing, argumentation, and research.", 3, False, False, "general_elective"),
    course("ENGL206", "ENGL", 206, "Technical English", "Required technical communication, research writing, and presentations.", 3, False, False, "general_elective"),
    course("ARAB201", "ARAB", 201, "Arabic Communication", "Arabic communication / understanding communication elective.", 3, False, False, "general_elective"),

    # EECE required core - no fake EECE200. EECE210 and EECE230 are entry courses.
    course("EECE210", "EECE", 210, "Electric Circuits", "Required entry course in circuit variables, resistive circuits, transient response, and AC steady state.", 3, False, True, "core"),
    course("EECE211", "EECE", 211, "Electric Circuits Laboratory", "Circuit measurement and laboratory experiments.", 1, True, True, "core"),
    course("EECE230", "EECE", 230, "Introduction to Programming", "Required programming foundations for ECE/CCE/CSE students.", 3, False, True, "core"),
    course("EECE290", "EECE", 290, "Digital Systems", "Required digital logic, combinational circuits, sequential circuits, and digital design.", 3, False, True, "core"),
    course("EECE310", "EECE", 310, "Signals and Systems", "Required signals, convolution, Fourier analysis, and system response.", 3, False, True, "core"),
    course("EECE310L", "EECE", 310, "Signals and Systems Laboratory", "Laboratory experiments for signals and systems.", 1, True, True, "core"),
    course("EECE311", "EECE", 311, "Electronic Circuits", "Required electronics fundamentals, devices, amplifiers, and circuit design.", 3, False, True, "core"),
    course("EECE320", "EECE", 320, "Digital Systems Design", "Required digital system design, datapath/control, and hardware organization.", 3, False, True, "core"),
    course("EECE321", "EECE", 321, "Computer Organization", "Required computer organization, instruction sets, datapath, memory, and interfacing.", 3, False, True, "core"),
    course("EECE321L", "EECE", 321, "Computer Organization Laboratory", "Laboratory experiments in computer organization and interfacing.", 1, True, True, "core"),
    course("EECE330", "EECE", 330, "Data Structures and Algorithms", "Required data structures, algorithm analysis, trees, graphs, hashing, and sorting.", 3, False, True, "core"),
    course("EECE331", "EECE", 331, "Software Engineering", "Required software lifecycle, requirements, design, testing, and team development.", 3, False, True, "core"),
    course("EECE332", "EECE", 332, "Database Systems", "Required relational databases, SQL, normalization, and transactions.", 3, False, True, "core"),
    course("EECE334", "EECE", 334, "Computer Architecture", "Required architecture, pipelining, cache, memory systems, and processor design.", 3, False, True, "core"),
    course("EECE338", "EECE", 338, "Theory of Computation", "Required computing theory, automata, formal languages, and computability.", 3, False, True, "core"),
    course("EECE340", "EECE", 340, "Signals and Communications", "Required Fourier transform, sampling, modulation, and communication fundamentals.", 3, False, True, "core"),
    course("EECE350", "EECE", 350, "Computer Networks", "Required CCE/computing networks course covering protocols, routing, TCP/IP, and applications.", 3, False, True, "core"),
    course("EECE351", "EECE", 351, "Operating Systems", "Required operating systems: processes, threads, memory, synchronization, and file systems.", 3, False, True, "core"),
    course("EECE370", "EECE", 370, "Electronics", "Required ECE electronics course covering diodes, transistors, MOSFETs, amplifiers, and design.", 3, False, True, "core"),
    course("EECE380", "EECE", 380, "Electromagnetic Fields and Waves", "Required fields, Maxwell equations, and wave propagation.", 3, False, True, "core"),
    course("EECE410L", "EECE", 410, "Electronics Laboratory", "Required/elective electronics laboratory experiments and instrumentation.", 1, True, True, "core"),
    course("EECE430", "EECE", 430, "Web and Mobile Applications", "Required/elective software engineering for modern web and mobile applications.", 3, False, True, "core"),
    course("EECE432", "EECE", 432, "Data Science for Engineers", "Required/elective data processing, visualization, and predictive modeling.", 3, False, True, "core"),
    course("EECE442", "EECE", 442, "Communication Systems", "Required CCE communications course: analog/digital communication, modulation, noise, and performance.", 3, False, True, "core"),
    course("EECE455", "EECE", 455, "Information Theory", "Required/elective entropy, coding, compression, and communication limits.", 3, False, True, "core"),
    course("EECE490", "EECE", 490, "Special Topics / Project Preparation", "Required selected topics or project preparation course in EECE.", 3, False, True, "core"),
    course("EECE500", "EECE", 500, "Approved Experience", "Required approved practical experience, internship, or professional exposure.", 1, True, True, "core"),
    course("EECE501", "EECE", 501, "Final Year Project I", "Required first part of senior capstone project.", 3, True, True, "core"),
    course("EECE502", "EECE", 502, "Final Year Project II", "Required second part of senior capstone project.", 3, True, True, "core"),

    # EECE restricted / technical electives
    course("EECE412", "EECE", 412, "Computer Hardware Systems", "Advanced digital systems, hardware organization, and design methodology.", 3, False, True, "major_elective"),
    course("EECE420", "EECE", 420, "Embedded Systems Design", "Real-time embedded systems and hardware-software integration.", 3, True, True, "major_elective"),
    course("EECE435", "EECE", 435, "Machine Learning for Engineers", "Supervised learning, classification, regression, and model evaluation.", 3, False, True, "major_elective"),
    course("EECE437", "EECE", 437, "Artificial Intelligence", "Search, reasoning, knowledge representation, and intelligent systems.", 3, False, True, "major_elective"),
    course("EECE438", "EECE", 438, "Cybersecurity", "Cryptography, network security, secure systems, and vulnerability analysis.", 3, False, True, "major_elective"),
    course("EECE439", "EECE", 439, "Cloud Computing", "Cloud platforms, virtualization, containers, and distributed services.", 3, False, True, "major_elective"),
    course("EECE441", "EECE", 441, "Digital Signal Processing", "Discrete-time signals, FFT, digital filters, and DSP applications.", 3, False, True, "major_elective"),
    course("EECE450", "EECE", 450, "Advanced Computer Networks", "Advanced networking, routing, congestion, and network performance.", 3, False, True, "major_elective"),
    course("EECE451", "EECE", 451, "Wireless Networks", "Wireless communication networks, cellular systems, and protocols.", 3, False, True, "major_elective"),
    course("EECE460", "EECE", 460, "Control Systems", "Feedback, stability, root locus, frequency response, and PID control.", 3, False, True, "major_elective"),
    course("EECE461", "EECE", 461, "Control Systems Laboratory", "Control experiments, modeling, and controller implementation.", 1, True, True, "major_elective"),
    course("EECE462", "EECE", 462, "Robotics", "Robot modeling, sensors, actuators, and control.", 3, True, True, "major_elective"),
    course("EECE463", "EECE", 463, "Intelligent Control Systems", "Control systems with intelligent and data-driven methods.", 3, False, True, "major_elective"),
    course("EECE470", "EECE", 470, "Electronic Circuit Design", "Analog and mixed-signal circuit design.", 3, False, True, "major_elective"),
    course("EECE471", "EECE", 471, "Power Systems Analysis", "Power generation, transmission, load flow, faults, and grid operation.", 3, False, True, "major_elective"),
    course("EECE475", "EECE", 475, "Power Electronics", "Converters, inverters, rectifiers, and switching devices.", 3, False, True, "major_elective"),
    course("EECE476", "EECE", 476, "Renewable Energy Systems", "Solar, wind, storage, and grid-connected renewable energy systems.", 3, False, True, "major_elective"),
    course("EECE480", "EECE", 480, "Antennas", "Antenna fundamentals, radiation, arrays, and antenna design.", 3, False, True, "major_elective"),
    course("EECE484", "EECE", 484, "RF and Microwave Engineering", "Transmission lines, microwave networks, and RF system design.", 3, False, True, "major_elective"),

    # Pre-approved / General Education electives — all 200-level+
    course("ECON211", "ECON", 211, "Elementary Microeconomic Theory", "Consumer choice, firms, markets, and economic decision making.", 3, False, False, "general_elective"),
    course("ECON212", "ECON", 212, "Elementary Macroeconomic Theory", "GDP, inflation, unemployment, money, and macroeconomic policy.", 3, False, False, "general_elective"),
    course("SOAN201", "SOAN", 201, "Introduction to Sociology", "Social institutions, culture, inequality, and sociological thinking.", 3, False, False, "general_elective"),
    course("SOAN203", "SOAN", 203, "Introduction to Anthropology", "Culture, society, identity, and anthropological perspectives.", 3, False, False, "general_elective"),
    course("PSYC201", "PSYC", 201, "Introduction to Psychology", "Behavior, cognition, development, personality, and psychological science.", 3, False, False, "general_elective"),
    course("PHIL201", "PHIL", 201, "Ethics", "Moral reasoning, ethical theories, and applied ethical issues.", 3, False, False, "general_elective"),
    course("HIST201", "HIST", 201, "Modern History", "Modern historical developments and global transformations.", 3, False, False, "general_elective"),
    course("CHLA210", "CHLA", 210, "Human Values and Social Issues", "Human values, identity, society, and cultural debates.", 3, False, False, "general_elective"),
    course("CHLA211", "CHLA", 211, "The Normal and the Pathological", "Human condition, medicine, society, and cultural interpretations.", 3, False, False, "general_elective"),
    course("CHLA212", "CHLA", 212, "Critical Approaches to Technology and AI", "Humanities perspectives on technology, artificial intelligence, and society.", 3, False, False, "general_elective"),
    course("CHLA214", "CHLA", 214, "Human Values", "Ethics, values, social responsibility, and cultural analysis.", 3, False, False, "general_elective"),
    course("CHLA261", "CHLA", 261, "Civilization Through the Arts I", "Civilization, art, culture, and historical interpretation.", 3, False, False, "general_elective"),
    course("CHLA262", "CHLA", 262, "Civilization Through the Arts II", "Modern civilization, arts, and cultural production.", 3, False, False, "general_elective"),
    course("AROL201", "AROL", 201, "Archaeology in Lebanon", "Archaeological history and cultural heritage of Lebanon.", 3, False, False, "general_elective"),
    course("AROL210", "AROL", 210, "Introduction to Archaeology", "Methods, theory, and practice of archaeology.", 3, False, False, "general_elective"),
    course("AROL211", "AROL", 211, "Archaeological Methodology", "Archaeological survey, excavation, documentation, and interpretation.", 3, False, False, "general_elective"),
    course("AROL213", "AROL", 213, "Human History: Old Stone Age", "Prehistory, early humans, and ancient material culture.", 3, False, False, "general_elective"),
    course("AROL214", "AROL", 214, "Human Story: Neolithic Period", "Neolithic societies, agriculture, and early settlements.", 3, False, False, "general_elective"),
    course("AROL217", "AROL", 217, "Phoenicia and the Phoenicians", "Phoenician history, culture, trade, and Mediterranean networks.", 3, False, False, "general_elective"),
    course("AROL224", "AROL", 224, "Introduction to the Roman World", "Roman civilization, culture, cities, and material evidence.", 3, False, False, "general_elective"),
    course("AROL240", "AROL", 240, "Introduction to Ancient Egypt", "Ancient Egyptian history, culture, religion, and archaeology.", 3, False, False, "general_elective"),
    course("MUS201", "MUS", 201, "Music Theory and Practice", "Music notation, rhythm, harmony, and listening skills.", 3, False, False, "general_elective"),
    course("MUS203", "MUS", 203, "Music History Survey", "Western and regional music traditions through historical periods.", 3, False, False, "general_elective"),
    course("MUS204", "MUS", 204, "Music History: Romantic to Modern", "Music history from the nineteenth century to modern styles.", 3, False, False, "general_elective"),
    course("MUS205", "MUS", 205, "Introduction to Music Technology", "Digital audio, MIDI, recording, and music production basics.", 3, False, False, "general_elective"),
    course("AHIS203", "AHIS", 203, "Ancient and Classical Art", "Ancient visual culture, classical art, and historical interpretation.", 3, False, False, "general_elective"),
    course("AHIS210", "AHIS", 210, "Art and the Enlightenment", "Art, culture, and intellectual history of the Enlightenment.", 3, False, False, "general_elective"),
    course("CVSP201", "CVSP", 201, "Civilization Studies I", "Texts, ideas, and cultural traditions in global civilization.", 3, False, False, "general_elective"),
    course("CVSP202", "CVSP", 202, "Civilization Studies II", "Modern civilization, intellectual history, and social questions.", 3, False, False, "general_elective"),
    course("PSPA201", "PSPA", 201, "Introduction to Political Studies", "Political institutions, public policy, governance, and citizenship.", 3, False, False, "general_elective"),
]


PREREQUISITES = [
    # First-term entry courses have no prerequisites: FEAA200, EECE210, EECE230, EECE290,
    # ENGL203, MATH201, MATH211/CMPS211, MATH218, PHYS210, PHYS210L, CHEM201.
    ("MATH202", "MATH201"),
    ("MATH251", "MATH202"),
    ("STAT230", "MATH201"),
    ("CHEM203", "CHEM201"),
    ("ENGL206", "ENGL203"),
    ("EECE211", "EECE210"),
    ("EECE310", "MATH202"),
    ("EECE310", "EECE210"),
    ("EECE310L", "EECE310"),
    ("EECE311", "EECE210"),
    ("EECE311", "MATH202"),
    ("EECE320", "EECE290"),
    ("EECE321", "EECE320"),
    ("EECE321L", "EECE321"),
    ("EECE330", "EECE230"),
    ("EECE331", "EECE230"),
    ("EECE332", "EECE330"),
    ("EECE334", "EECE320"),
    ("EECE338", "MATH211"),
    ("EECE340", "EECE310"),
    ("EECE350", "EECE330"),
    ("EECE350", "EECE320"),
    ("EECE351", "EECE320"),
    ("EECE351", "EECE330"),
    ("EECE370", "EECE210"),
    ("EECE370", "MATH202"),
    ("EECE380", "PHYS210"),
    ("EECE380", "MATH202"),
    ("EECE410L", "EECE311"),
    ("EECE430", "EECE331"),
    ("EECE432", "EECE330"),
    ("EECE442", "EECE340"),
    ("EECE455", "EECE340"),
    ("EECE490", "EECE330"),
    ("EECE500", "EECE330"),
    ("EECE501", "EECE490"),
    ("EECE501", "EECE500"),
    ("EECE502", "EECE501"),
    ("EECE412", "EECE334"),
    ("EECE420", "EECE321"),
    ("EECE435", "EECE330"),
    ("EECE435", "STAT230"),
    ("EECE437", "EECE330"),
    ("EECE438", "EECE350"),
    ("EECE439", "EECE351"),
    ("EECE441", "EECE310"),
    ("EECE450", "EECE350"),
    ("EECE451", "EECE350"),
    ("EECE460", "EECE310"),
    ("EECE461", "EECE460"),
    ("EECE462", "EECE321"),
    ("EECE463", "EECE460"),
    ("EECE470", "EECE311"),
    ("EECE471", "EECE210"),
    ("EECE475", "EECE311"),
    ("EECE476", "EECE471"),
    ("EECE480", "EECE380"),
    ("EECE484", "EECE380"),
]


def backup(path: Path):
    if path.exists():
        b = path.with_name(path.stem + "_BACKUP_before_aub" + path.suffix)
        if not b.exists():
            b.write_bytes(path.read_bytes())
            print(f"Backup: {path.name} -> {b.name}")


def compute_depths(course_codes, prereqs):
    prereq_map = defaultdict(list)
    for c, p in prereqs:
        prereq_map[c].append(p)

    memo = {}

    def depth(c, seen=None):
        if seen is None:
            seen = set()
        if c in memo:
            return memo[c]
        if c in seen:
            return 0
        seen.add(c)
        parents = prereq_map.get(c, [])
        memo[c] = 0 if not parents else 1 + max(depth(p, seen) for p in parents)
        seen.remove(c)
        return memo[c]

    return {c: depth(c) for c in course_codes}


def main():
    DATA_DIR.mkdir(exist_ok=True)

    for p in [COURSES_FILE, PREREQ_FILE, COURSES_INDEX_FILE, PREREQ_INDEX_FILE, MAJORS_FILE]:
        backup(p)

    majors = [
        {"code": "ECE", "name": "Electrical and Computer Engineering", "display": "ECE - Electrical and Computer Engineering"},
        {"code": "CCE", "name": "Computer and Communications Engineering", "display": "CCE - Computer and Communications Engineering"},
        {"code": "CSE", "name": "Computer Science and Engineering", "display": "CSE - Computer Science and Engineering"},
    ]
    MAJORS_FILE.write_text(json.dumps(majors, indent=2), encoding="utf-8")

    course_codes = [c["course_code"] for c in COURSES]
    prereq_count = defaultdict(int)
    unlocks_count = defaultdict(int)

    for c, p in PREREQUISITES:
        prereq_count[c] += 1
        unlocks_count[p] += 1

    depths = compute_depths(course_codes, PREREQUISITES)

    with COURSES_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COURSE_COLUMNS)
        writer.writeheader()
        for c in COURSES:
            code = c["course_code"]
            writer.writerow({
                **c,
                "prerequisite_count": prereq_count.get(code, 0),
                "prerequisite_depth": depths.get(code, 0),
                "graph_centrality": round(unlocks_count.get(code, 0) / max(1, len(COURSES)), 6),
                "unlocks_count": unlocks_count.get(code, 0),
            })

    with PREREQ_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["course", "prerequisite"])
        writer.writeheader()
        for c, p in PREREQUISITES:
            writer.writerow({"course": c, "prerequisite": p})

    courses_index = {
        c["course_code"]: {
            "course_code": c["course_code"],
            "subject": c["subject"],
            "number": c["number"],
            "name": c["name"],
            "description": c["description"],
            "credit_hours": c["credit_hours"],
            "course_level": c["course_level"],
            "is_lab": c["is_lab"],
            "is_major_course": c["is_major_course"],
            "course_type": c["course_type"],
        }
        for c in COURSES
    }
    COURSES_INDEX_FILE.write_text(json.dumps(courses_index, indent=2), encoding="utf-8")

    prereq_index = defaultdict(list)
    for c, p in PREREQUISITES:
        prereq_index[c].append(p)
    PREREQ_INDEX_FILE.write_text(json.dumps(prereq_index, indent=2), encoding="utf-8")

    first_unlocked = [
        "FEAA200", "EECE210", "EECE230", "EECE290", "ENGL203",
        "MATH201", "MATH211", "CMPS211", "MATH218", "PHYS210", "PHYS210L", "CHEM201", "INDE301",
    ]

    print("Corrected AUB-style ECE/CCE/CSE dataset created successfully.")
    print(f"Courses: {len(COURSES)}")
    print(f"Prerequisite edges: {len(PREREQUISITES)}")
    print("No 100-level courses included.")
    print("Removed fake EECE200.")
    print("EECE210 and EECE230 are unlocked entry courses.")
    print("Required non-EECE courses are marked as support; support means required support, not optional.")
    print("First unlocked examples:", ", ".join(first_unlocked))
    print("Updated: merged_courses.csv, prerequisites.csv, courses_index.json, prerequisites_index.json, majors.json")


if __name__ == "__main__":
    main()
