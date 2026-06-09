import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / 'Data'
SYNTHETIC_DIR = DATA_DIR / 'synthetic'
STUDENTS_FILE = SYNTHETIC_DIR / 'synthetic_students.csv'
STUDENT_COURSES_FILE = SYNTHETIC_DIR / 'synthetic_student_courses.csv'

print('=' * 80)
print('TRAINING ALL ML MODELS - IMPROVED RIGOR VERSION')
print('=' * 80)

force_regenerate = '--regenerate' in sys.argv
if force_regenerate or not STUDENTS_FILE.exists() or not STUDENT_COURSES_FILE.exists():
    print('\nRegenerating strength/weakness synthetic data (600 students / ~13k attempts)...\n')
    from scripts.generate_synthetic_data import generate_training_data
    generate_training_data(num_students=600)
    print('\n[OK] Improved synthetic data generated.\n')
else:
    print('\n[OK] Existing improved synthetic files found. Skipping regeneration.')
    print('     Use: python ml/train_all_models.py --regenerate  to rebuild the synthetic dataset.\n')

models_to_train = [
    ('Model 1: Personalized Course Difficulty', 'model1_course_difficulty'),
    ('Model 2: Semester Workload Estimation', 'model2_semester_workload'),
    ('Model 3: Future Academic Risk', 'model3_academic_risk'),
    ('Model 4: Course Success Probability', 'model4_course_success_probability'),
    ('Model 5: Expected AUB Grade Points', 'model5_expected_grade'),
]

for model_name, module_name in models_to_train:
    print(f"\n{'=' * 80}")
    print(f'Training {model_name}')
    print(f"{'=' * 80}\n")
    module = __import__(f'ml.{module_name}', fromlist=[module_name])
    model_number = module_name.split('_')[0].replace('model', '')
    train_func = getattr(module, f'train_model{model_number}')
    train_func()
    print(f'\n[OK] {model_name} completed.\n')

print('\n' + '=' * 80)
print('ALL MODELS TRAINING COMPLETE')
print('=' * 80)
