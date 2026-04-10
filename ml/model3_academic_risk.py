import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, roc_auc_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
MODELS_DIR.mkdir(exist_ok=True)

MODEL3_XGB_FILE = MODELS_DIR / 'model3_xgboost_risk.pkl'
MODEL3_GB_FILE = MODELS_DIR / 'model3_gradient_boosting_risk.pkl'

def load_data():
    print("Loading data...")
    courses_df = pd.read_csv(COURSES_FILE)
    students_df = pd.read_csv(STUDENTS_FILE)
    student_courses_df = pd.read_csv(STUDENT_COURSES_FILE)
    return courses_df, students_df, student_courses_df

def calculate_risk_label(student, student_courses):
    gpa = student['gpa']
    recent_courses = student_courses[student_courses['semester_taken'] >= student['total_courses_completed'] - 10]
    
    if len(recent_courses) == 0:
        return 0
    
    recent_grades = recent_courses['grade_points'].tolist()
    avg_recent_grade = np.mean(recent_grades) if recent_grades else 3.0
    
    failed_courses = len([g for g in recent_grades if g < 1.0])
    low_grades = len([g for g in recent_grades if g < 2.0])
    
    if gpa < 2.0 or failed_courses >= 2:
        return 3
    elif gpa < 2.5 or failed_courses >= 1 or low_grades >= 3:
        return 2
    elif gpa < 3.0 or avg_recent_grade < 2.5:
        return 1
    else:
        return 0

def create_training_features(courses_df, students_df, student_courses_df):
    print("Creating training features for academic risk prediction...")
    
    training_data = []
    
    for student_id in students_df['student_id'].unique():
        student = students_df[students_df['student_id'] == student_id].iloc[0]
        student_courses = student_courses_df[student_courses_df['student_id'] == student_id]
        
        if len(student_courses) < 3:
            continue
        
        recent_courses = student_courses.tail(10)
        all_grades = student_courses['grade_points'].tolist()
        recent_grades = recent_courses['grade_points'].tolist()
        
        gpa_trend = []
        for i in range(3, len(student_courses)):
            window = student_courses.iloc[max(0, i-3):i+1]
            window_gpa = np.mean(window['grade_points'].tolist())
            gpa_trend.append(window_gpa)
        
        gpa_trend_slope = np.polyfit(range(len(gpa_trend)), gpa_trend, 1)[0] if len(gpa_trend) > 1 else 0.0
        
        avg_grade = np.mean(all_grades) if all_grades else 3.0
        avg_recent_grade = np.mean(recent_grades) if recent_grades else 3.0
        min_recent_grade = np.min(recent_grades) if recent_grades else 3.0
        
        failed_count = len([g for g in recent_grades if g < 1.0])
        low_grade_count = len([g for g in recent_grades if g < 2.0])
        
        course_difficulties = []
        for _, sc in recent_courses.iterrows():
            course = courses_df[courses_df['course_code'] == sc['course_code']]
            if not course.empty:
                difficulty = 1.0 - (sc['grade_points'] / 4.0)
                course_difficulties.append(difficulty)
        
        avg_difficulty = np.mean(course_difficulties) if course_difficulties else 0.5
        difficulty_variance = np.var(course_difficulties) if len(course_difficulties) > 1 else 0.0
        
        performance_vs_difficulty = avg_recent_grade / 4.0 - avg_difficulty
        
        risk_label = calculate_risk_label(student, student_courses)
        
        features = {
            'current_gpa': student['gpa'] / 4.0,
            'gpa_trend_slope': gpa_trend_slope,
            'avg_grade': avg_grade / 4.0,
            'avg_recent_grade': avg_recent_grade / 4.0,
            'min_recent_grade': min_recent_grade / 4.0,
            'failed_count': failed_count / 10.0,
            'low_grade_count': low_grade_count / 10.0,
            'avg_difficulty': avg_difficulty,
            'difficulty_variance': difficulty_variance,
            'performance_vs_difficulty': performance_vs_difficulty,
            'academic_ability': student['academic_ability'],
            'workload_tolerance': student['workload_tolerance'],
            'total_courses_completed': student['total_courses_completed'] / 50.0,
            'risk_level': risk_label
        }
        
        training_data.append(features)
    
    df = pd.DataFrame(training_data)
    print(f"Created {len(df)} training samples")
    return df

def train_model3():
    print("=" * 60)
    print("MODEL 3: ACADEMIC RISK PREDICTION")
    print("=" * 60)
    
    courses_df, students_df, student_courses_df = load_data()
    
    training_df = create_training_features(courses_df, students_df, student_courses_df)
    
    feature_columns = [
        'current_gpa', 'gpa_trend_slope', 'avg_grade', 'avg_recent_grade',
        'min_recent_grade', 'failed_count', 'low_grade_count', 'avg_difficulty',
        'difficulty_variance', 'performance_vs_difficulty', 'academic_ability',
        'workload_tolerance', 'total_courses_completed'
    ]
    
    X = training_df[feature_columns]
    y = training_df['risk_level']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    print("\n" + "-" * 60)
    print("Training Gradient Boosting Classifier...")
    print("-" * 60)
    
    gb_model = GradientBoostingClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42
    )
    
    gb_model.fit(X_train, y_train)
    
    gb_train_pred = gb_model.predict(X_train)
    gb_test_pred = gb_model.predict(X_test)
    
    gb_train_acc = accuracy_score(y_train, gb_train_pred)
    gb_test_acc = accuracy_score(y_test, gb_test_pred)
    
    print(f"Gradient Boosting Results:")
    print(f"  Train Accuracy: {gb_train_acc:.4f}")
    print(f"  Test Accuracy: {gb_test_acc:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, gb_test_pred, target_names=['Low', 'Medium', 'High', 'Critical']))
    
    print("\n" + "-" * 60)
    print("Training XGBoost Classifier...")
    print("-" * 60)
    
    xgb_model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1
    )
    
    xgb_model.fit(X_train, y_train)
    
    xgb_train_pred = xgb_model.predict(X_train)
    xgb_test_pred = xgb_model.predict(X_test)
    
    xgb_train_acc = accuracy_score(y_train, xgb_train_pred)
    xgb_test_acc = accuracy_score(y_test, xgb_test_pred)
    
    print(f"XGBoost Results:")
    print(f"  Train Accuracy: {xgb_train_acc:.4f}")
    print(f"  Test Accuracy: {xgb_test_acc:.4f}")
    print(f"\nClassification Report:")
    print(classification_report(y_test, xgb_test_pred, target_names=['Low', 'Medium', 'High', 'Critical']))
    
    if xgb_test_acc >= gb_test_acc:
        best_model = xgb_model
        best_name = "XGBoost"
        best_acc = xgb_test_acc
        print(f"\n[OK] Best model: XGBoost (Accuracy: {best_acc:.4f})")
    else:
        best_model = gb_model
        best_name = "Gradient Boosting"
        best_acc = gb_test_acc
        print(f"\n[OK] Best model: Gradient Boosting (Accuracy: {best_acc:.4f})")
    
    with open(MODEL3_GB_FILE, 'wb') as f:
        pickle.dump(gb_model, f)
    print(f"[OK] Saved Gradient Boosting model to {MODEL3_GB_FILE}")
    
    with open(MODEL3_XGB_FILE, 'wb') as f:
        pickle.dump(xgb_model, f)
    print(f"[OK] Saved XGBoost model to {MODEL3_XGB_FILE}")
    
    feature_info = {
        'feature_columns': feature_columns,
        'best_model': best_name,
        'test_accuracy': float(best_acc),
        'risk_levels': {0: 'Low', 1: 'Medium', 2: 'High', 3: 'Critical'}
    }
    
    with open(MODELS_DIR / 'model3_info.pkl', 'wb') as f:
        pickle.dump(feature_info, f)
    
    print(f"\n[OK] Model 3 training complete!")
    return gb_model, xgb_model, feature_columns

if __name__ == '__main__':
    train_model3()
