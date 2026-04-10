
import pandas as pd
import numpy as np
from pathlib import Path
import sys
from sqlalchemy import text

sys.path.append(str(Path(__file__).parent.parent))

from database.db import get_db, init_db, close_db, engine
from database.models import Course, Prerequisite
from config import COURSES_FILE, PREREQUISITES_FILE

def safe_str(val):
    if pd.isna(val):
        return ''
    return str(val).strip()

def safe_float(val, default=0.0):
    if pd.isna(val):
        return default
    try:
        return float(val)
    except:
        return default

def safe_int(val, default=0):
    if pd.isna(val):
        return default
    try:
        return int(val)
    except:
        return default

def safe_bool(val):
    if pd.isna(val):
        return False
    try:
        return bool(val)
    except:
        return False


def load_courses_fast():
    
    print("Loading courses (fast mode)...")
    
    try:
        courses_df = pd.read_csv(COURSES_FILE)
        print(f"Loaded {len(courses_df)} courses from CSV")
        
        courses_df['course_code'] = courses_df['course_code'].apply(safe_str)
        courses_df['subject'] = courses_df['subject'].apply(safe_str)
        courses_df['number'] = courses_df['number'].apply(safe_str)
        courses_df['name'] = courses_df['name'].apply(safe_str)
        courses_df['description'] = courses_df['description'].apply(safe_str)
        courses_df['credit_hours'] = courses_df['credit_hours'].apply(lambda x: safe_float(x, 3.0))
        courses_df['course_level'] = courses_df['course_level'].apply(lambda x: safe_int(x, 100))
        if 'course_type' in courses_df.columns:
            courses_df['course_type'] = courses_df['course_type'].apply(safe_str)
        else:
            courses_df['course_type'] = ''
        courses_df['is_lab'] = courses_df['is_lab'].apply(safe_bool)
        courses_df['is_major_course'] = courses_df.get('is_major_course', pd.Series([True] * len(courses_df))).apply(safe_bool)
        courses_df['prerequisite_count'] = courses_df['prerequisite_count'].apply(lambda x: safe_int(x, 0))
        courses_df['prerequisite_depth'] = courses_df['prerequisite_depth'].apply(lambda x: safe_int(x, 0))
        courses_df['graph_centrality'] = courses_df['graph_centrality'].apply(lambda x: safe_float(x, 0.0))
        courses_df['unlocks_count'] = courses_df['unlocks_count'].apply(lambda x: safe_int(x, 0))
        
        courses_df = courses_df.drop_duplicates(subset=['course_code'])
        print(f"After deduplication: {len(courses_df)} courses")
        
        courses_data = []
        for _, row in courses_df.iterrows():
            courses_data.append({
                'course_code': safe_str(row['course_code']),
                'subject': safe_str(row['subject']),
                'number': safe_str(row['number']),
                'name': safe_str(row.get('name', '')),
                'description': safe_str(row.get('description', '')),
                'credit_hours': safe_float(row.get('credit_hours', 3.0), 3.0),
                'course_level': safe_int(row.get('course_level', 100), 100),
                'course_type': safe_str(row.get('course_type', '')),
                'is_lab': safe_bool(row.get('is_lab', False)),
                'is_major_course': safe_bool(row.get('is_major_course', True)),
                'prerequisite_count': safe_int(row.get('prerequisite_count', 0), 0),
                'prerequisite_depth': safe_int(row.get('prerequisite_depth', 0), 0),
                'graph_centrality': safe_float(row.get('graph_centrality', 0.0), 0.0),
                'unlocks_count': safe_int(row.get('unlocks_count', 0), 0)
            })
        
        db = get_db()
        try:
            print("Inserting courses into database (this may take a minute)...")
            db.bulk_insert_mappings(Course, courses_data)
            db.commit()
            print(f"[OK] Inserted {len(courses_data)} courses")
            
            print("Loading course IDs...")
            all_courses = db.query(Course).all()
            course_dict = {c.course_code: c for c in all_courses}
            print(f"[OK] Loaded {len(course_dict)} courses with IDs")
            
            return course_dict
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Bulk insert failed: {e}")
            print("Falling back to batch inserts...")
            
            batch_size = 1000
            course_dict = {}
            
            for i in range(0, len(courses_data), batch_size):
                batch = courses_data[i:i+batch_size]
                try:
                    db.bulk_insert_mappings(Course, batch)
                    db.commit()
                    
                    codes = [c['course_code'] for c in batch]
                    inserted = db.query(Course).filter(Course.course_code.in_(codes)).all()
                    for c in inserted:
                        course_dict[c.course_code] = c
                    
                    if (i // batch_size) % 10 == 0:
                        print(f"  Processed {i}/{len(courses_data)} courses...")
                except Exception as e2:
                    db.rollback()
                    print(f"  [WARNING] Batch {i} failed: {e2}")
                    continue
            
            return course_dict
        finally:
            close_db()
            
    except Exception as e:
        print(f"[ERROR] Failed to load courses: {e}")
        import traceback
        traceback.print_exc()
        raise


def load_prerequisites_fast(course_dict):
    
    print("Loading prerequisites (fast mode)...")
    
    try:
        prereq_df = pd.read_csv(PREREQUISITES_FILE)
        print(f"Loaded {len(prereq_df)} prerequisite relationships from CSV")
        
        course_code_to_id = {code: c.id for code, c in course_dict.items() if c.id}
        
        valid_prereqs = []
        skipped = 0
        
        for idx, row in prereq_df.iterrows():
            course_code = str(row['course']).strip()
            prereq_code = str(row['prerequisite']).strip()
            
            if course_code in course_code_to_id and prereq_code in course_code_to_id:
                valid_prereqs.append({
                    'course_id': course_code_to_id[course_code],
                    'prerequisite_id': course_code_to_id[prereq_code]
                })
            else:
                skipped += 1
        
        seen = set()
        unique_prereqs = []
        for p in valid_prereqs:
            key = (p['course_id'], p['prerequisite_id'])
            if key not in seen:
                seen.add(key)
                unique_prereqs.append(p)
        
        print(f"Valid prerequisites: {len(unique_prereqs)} (skipped {skipped})")
        
        db = get_db()
        try:
            print("Inserting prerequisites into database...")
            db.bulk_insert_mappings(Prerequisite, unique_prereqs)
            db.commit()
            print(f"[OK] Inserted {len(unique_prereqs)} prerequisite relationships")
        except Exception as e:
            db.rollback()
            print(f"[ERROR] Bulk insert failed: {e}")
            print("Falling back to batch inserts...")
            
            batch_size = 2000
            count = 0
            
            for i in range(0, len(unique_prereqs), batch_size):
                batch = unique_prereqs[i:i+batch_size]
                try:
                    db.bulk_insert_mappings(Prerequisite, batch)
                    db.commit()
                    count += len(batch)
                    
                    if (i // batch_size) % 5 == 0:
                        print(f"  Processed {i}/{len(unique_prereqs)} prerequisites...")
                except Exception as e2:
                    db.rollback()
                    print(f"  [WARNING] Batch {i} failed: {e2}")
                    continue
            
            print(f"[OK] Inserted {count} prerequisite relationships")
        finally:
            close_db()
            
    except Exception as e:
        print(f"[ERROR] Failed to load prerequisites: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    
    print("=" * 60)
    print("FAST DATA LOADING INTO DATABASE")
    print("=" * 60)
    
    print("\nInitializing database...")
    init_db()
    
    print("\n" + "-" * 60)
    course_dict = load_courses_fast()
    
    print("\n" + "-" * 60)
    load_prerequisites_fast(course_dict)
    
    print("\n" + "=" * 60)
    print("DATA LOADING COMPLETE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
