import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / 'Data'
SYNTHETIC_DIR = DATA_DIR / 'synthetic'
STUDENTS_FILE = SYNTHETIC_DIR / 'synthetic_students.csv'
STUDENT_COURSES_FILE = SYNTHETIC_DIR / 'synthetic_student_courses.csv'

print("=" * 80)
print("TRAINING ALL ML MODELS")
print("=" * 80)
print("\nThis will train 3 ML models (Models 1–3 in usage order).\n")

if not STUDENTS_FILE.exists() or not STUDENT_COURSES_FILE.exists():
    print("=" * 80)
    print("SYNTHETIC DATA NOT FOUND - GENERATING NOW")
    print("=" * 80)
    print("\nGenerating synthetic student data (this may take a few minutes)...\n")
    
    try:
        from scripts.generate_synthetic_data import generate_training_data
        generate_training_data(num_students=5000)
        print("\n[OK] Synthetic data generated successfully!\n")
    except Exception as e:
        print(f"\n[ERROR] Failed to generate synthetic data: {e}\n")
        import traceback
        traceback.print_exc()
        print("\n[WARNING] Continuing anyway - models may fail if data is required...\n")
else:
    print("[OK] Synthetic data files found, skipping generation.\n")

models_to_train = [
    ("Model 1: Course Difficulty Prediction", "model1_course_difficulty"),
    ("Model 2: Semester Workload Estimation", "model2_semester_workload"),
    ("Model 3: Academic Risk Prediction", "model3_academic_risk"),
]

for model_name, module_name in models_to_train:
    print(f"\n{'=' * 80}")
    print(f"Training {model_name}")
    print(f"{'=' * 80}\n")
    
    try:
        module = __import__(f"ml.{module_name}", fromlist=[module_name])
        model_number = module_name.split('_')[0].replace('model', '')
        train_func_name = f"train_model{model_number}"
        train_func = getattr(module, train_func_name)
        train_func()
        print(f"\n[OK] {model_name} training completed successfully!\n")
    except Exception as e:
        print(f"\n[ERROR] Failed to train {model_name}: {e}\n")
        import traceback
        traceback.print_exc()
        continue

print("\n" + "=" * 80)
print("ALL MODELS TRAINING COMPLETE!")
print("=" * 80)
