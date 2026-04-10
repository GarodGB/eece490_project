
import pandas as pd
from pathlib import Path
import json

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
OUTPUT_FILE = Path(__file__).parent.parent / 'static' / 'majors.json'
OUTPUT_FILE_DATA = DATA_DIR / 'majors.json'

def extract_majors():
    
    print("Extracting majors from course data...")
    
    df = pd.read_csv(COURSES_FILE)
    
    majors = sorted(df['subject'].dropna().unique())
    
    major_names = {
        'CS': 'Computer Science',
        'ECE': 'Electrical & Computer Engineering',
        'MATH': 'Mathematics',
        'PHYS': 'Physics',
        'CHEM': 'Chemistry',
        'BIO': 'Biology',
        'ENGR': 'Engineering',
        'STAT': 'Statistics',
        'ECON': 'Economics',
        'PSYC': 'Psychology',
        'BUS': 'Business',
        'PHIL': 'Philosophy',
        'HIST': 'History',
        'ENGL': 'English',
        'ART': 'Art',
        'MED': 'Medicine/Pre-Med',
        'LAW': 'Law',
        'MUS': 'Music',
        'SOC': 'Sociology',
        'POL': 'Political Science',
        'MECH': 'Mechanical Engineering',
        'CIV': 'Civil Engineering',
        'AERO': 'Aerospace Engineering',
        'BIOE': 'Bioengineering',
        'IE': 'Industrial Engineering',
        'MATSE': 'Materials Science & Engineering',
        'NPRE': 'Nuclear, Plasma & Radiological Engineering',
        'GEO': 'Geology',
        'ARCH': 'Architecture',
        'ACCY': 'Accountancy',
        'FIN': 'Finance',
        'AAS': 'Asian American Studies',
        'AFRO': 'African American Studies',
        'ANTH': 'Anthropology',
        'ARTD': 'Art & Design',
        'BADM': 'Business Administration',
        'BIOL': 'Biology',
        'BTW': 'Business & Technical Writing',
        'CMN': 'Communication',
        'CWL': 'Comparative & World Literature',
        'DANC': 'Dance',
        'EALC': 'East Asian Languages & Cultures',
        'EDUC': 'Education',
        'ENG': 'Engineering',
        'FR': 'French',
        'GER': 'German',
        'GWS': 'Gender & Women\'s Studies',
        'HDFS': 'Human Development & Family Studies',
        'ITAL': 'Italian',
        'JOUR': 'Journalism',
        'KIN': 'Kinesiology',
        'LING': 'Linguistics',
        'LLS': 'Latina/Latino Studies',
        'PS': 'Political Science',
        'REL': 'Religion',
        'RST': 'Recreation, Sport & Tourism',
        'SOCW': 'Social Work',
        'SPAN': 'Spanish',
        'THEA': 'Theatre',
        'TSM': 'Technology & Management'
    }
    
    majors_list = []
    for major in majors:
        name = major_names.get(major, major)
        majors_list.append({
            'code': major,
            'name': name,
            'display': f'{major} - {name}'
        })
    
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(majors_list, f, indent=2)
    
    OUTPUT_FILE_DATA.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE_DATA, 'w') as f:
        json.dump(majors_list, f, indent=2)
    
    print(f"[OK] Extracted {len(majors_list)} majors")
    print(f"[OK] Saved to {OUTPUT_FILE}")
    print(f"[OK] Saved to {OUTPUT_FILE_DATA}")
    
    return majors_list

if __name__ == '__main__':
    majors = extract_majors()
    print("\nMajors found:")
    for m in majors[:20]:
        print(f"  {m['code']} - {m['name']}")
    if len(majors) > 20:
        print(f"  ... and {len(majors) - 20} more")
