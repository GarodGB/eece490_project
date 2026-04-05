
import pandas as pd
from pathlib import Path
import json

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
PREREQUISITES_FILE = DATA_DIR / 'prerequisites.csv'
OUTPUT_DIR = Path(__file__).parent.parent / 'static' / 'data'
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

def create_course_index():
    
    print("Creating course index CSV...")
    
    df = pd.read_csv(COURSES_FILE)
    
    course_index = df[['course_code', 'subject', 'number', 'name', 'credit_hours', 
                      'course_level', 'is_lab', 'prerequisite_count', 
                      'prerequisite_depth', 'graph_centrality', 'unlocks_count']].copy()
    
    def safe_str(val) -> str:
        if pd.isna(val):
            return ''
        return str(val).strip()

    def safe_float(val, default=0.0) -> float:
        try:
            if pd.isna(val):
                return float(default)
            return float(val)
        except Exception:
            return float(default)

    def safe_int(val, default=0) -> int:
        try:
            if pd.isna(val):
                return int(default)
            return int(float(val))
        except Exception:
            return int(default)

    def safe_bool(val) -> bool:
        if pd.isna(val):
            return False
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ('1', 'true', 'yes', 'y', 't')

    course_index['course_code'] = course_index['course_code'].apply(safe_str)
    course_index['subject'] = course_index['subject'].apply(safe_str).str.upper()
    course_index['number'] = course_index['number'].apply(safe_str)
    course_index['name'] = course_index['name'].apply(safe_str)

    course_index['credit_hours'] = course_index['credit_hours'].apply(lambda x: safe_float(x, 0.0))
    course_index['course_level'] = course_index['course_level'].apply(lambda x: safe_int(x, 0))
    course_index['is_lab'] = course_index['is_lab'].apply(safe_bool)
    course_index['prerequisite_count'] = course_index['prerequisite_count'].apply(lambda x: safe_int(x, 0))
    course_index['prerequisite_depth'] = course_index['prerequisite_depth'].apply(lambda x: safe_int(x, 0))
    course_index['graph_centrality'] = course_index['graph_centrality'].apply(lambda x: safe_float(x, 0.0))
    course_index['unlocks_count'] = course_index['unlocks_count'].apply(lambda x: safe_int(x, 0))

    def derive_level(row):
        if row['course_level'] and row['course_level'] > 0:
            return row['course_level']
        num = row['number']
        digits = ''.join([c for c in num if c.isdigit()])
        if len(digits) >= 1:
            try:
                return int(digits[0]) * 100
            except Exception:
                return 100
        return 100

    course_index['course_level'] = course_index.apply(derive_level, axis=1)

    course_index = course_index[
        (course_index['course_code'] != '') &
        (course_index['subject'] != '') &
        (course_index['number'] != '') &
        (course_index['name'] != '') &
        (course_index['credit_hours'] > 0)
    ].copy()

    course_index = course_index.drop_duplicates(subset=['course_code'], keep='first').copy()

    course_index = course_index.fillna({
        'prerequisite_count': 0,
        'prerequisite_depth': 0,
        'graph_centrality': 0.0,
        'unlocks_count': 0
    })
    
    output_file = OUTPUT_DIR / 'courses_index.csv'
    course_index.to_csv(output_file, index=False)
    print(f"[OK] Created {output_file} with {len(course_index)} courses")
    
    courses_dict = course_index.to_dict('records')
    json_file = OUTPUT_DIR / 'courses_index.json'
    with open(json_file, 'w') as f:
        json.dump(courses_dict, f, indent=2)
    print(f"[OK] Created {json_file}")
    
    return course_index


def create_prerequisites_index():
    
    print("Creating prerequisites index CSV...")
    
    df = pd.read_csv(PREREQUISITES_FILE)

    df['course'] = df['course'].astype(str).str.strip()
    df['prerequisite'] = df['prerequisite'].astype(str).str.strip()
    df = df[(df['course'] != '') & (df['prerequisite'] != '')].copy()
    df = df.dropna(subset=['course', 'prerequisite']).copy()
    df = df.drop_duplicates().copy()

    try:
        cleaned_courses_df = pd.read_csv(OUTPUT_DIR / 'courses_index.csv')
        valid_codes = set(cleaned_courses_df['course_code'].astype(str).str.strip().tolist())
        df = df[df['course'].isin(valid_codes) & df['prerequisite'].isin(valid_codes)].copy()
    except Exception:
        pass
    
    output_file = OUTPUT_DIR / 'prerequisites_index.csv'
    df.to_csv(output_file, index=False)
    print(f"[OK] Created {output_file} with {len(df)} prerequisites")
    
    prereq_dict = {}
    for _, row in df.iterrows():
        course = str(row['course']).strip()
        prereq = str(row['prerequisite']).strip()
        if course not in prereq_dict:
            prereq_dict[course] = []
        prereq_dict[course].append(prereq)
    
    json_file = OUTPUT_DIR / 'prerequisites_index.json'
    with open(json_file, 'w') as f:
        json.dump(prereq_dict, f, indent=2)
    print(f"[OK] Created {json_file}")
    
    return df


def main():
    print("=" * 60)
    print("CREATING OPTIMIZED CSV FILES FOR LOCAL LOADING")
    print("=" * 60)
    
    course_index = create_course_index()
    prereq_index = create_prerequisites_index()
    
    print("\n" + "=" * 60)
    print("CSV FILES CREATED SUCCESSFULLY!")
    print("=" * 60)
    print(f"\nFiles created in: {OUTPUT_DIR}")
    print("  - courses_index.csv")
    print("  - courses_index.json")
    print("  - prerequisites_index.csv")
    print("  - prerequisites_index.json")
    print("\nThese files will be used for fast local loading!")

if __name__ == '__main__':
    main()
