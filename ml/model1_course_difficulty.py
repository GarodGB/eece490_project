import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
MODELS_DIR.mkdir(exist_ok=True)

MODEL1_RF_FILE = MODELS_DIR / 'model1_random_forest.pkl'
MODEL1_XGB_FILE = MODELS_DIR / 'model1_xgboost.pkl'


def load_data():
    print("Loading data...")
    courses_df = pd.read_csv(COURSES_FILE)
    students_df = pd.read_csv(STUDENTS_FILE)
    student_courses_df = pd.read_csv(STUDENT_COURSES_FILE)
    
    return courses_df, students_df, student_courses_df


def create_training_features(courses_df, students_df, student_courses_df):
    print("Creating training features...")
    
    training_data = []
    
    for _, student_course in student_courses_df.iterrows():
        student_id = student_course['student_id']
        course_code = student_course['course_code']
        actual_grade_points = student_course['grade_points']
        
        student = students_df[students_df['student_id'] == student_id].iloc[0]
        
        course = courses_df[courses_df['course_code'] == course_code]
        if course.empty:
            continue
        course = course.iloc[0]
        
        prereq_grades = []
        if course['prerequisite_count'] > 0:
            prereq_courses = student_courses_df[
                (student_courses_df['student_id'] == student_id) &
                (student_courses_df['semester_taken'] < student_course['semester_taken'])
            ]
            if len(prereq_courses) > 0:
                prereq_grades = prereq_courses['grade_points'].tolist()
        
        avg_prereq_grade = np.mean(prereq_grades) if prereq_grades else 3.0
        min_prereq_grade = np.min(prereq_grades) if prereq_grades else 3.0
        
        features = {
            'course_level': course['course_level'] / 500.0,
            'prerequisite_count': course['prerequisite_count'] / 10.0,
            'prerequisite_depth': course['prerequisite_depth'] / 10.0,
            'graph_centrality': course['graph_centrality'],
            'credit_hours': course['credit_hours'] / 4.0,
            'is_lab': 1 if course['is_lab'] else 0,
            'student_gpa': student['gpa'] / 4.0,
            'academic_ability': student['academic_ability'],
            'workload_tolerance': student['workload_tolerance'],
            'total_courses_completed': student['total_courses_completed'] / 50.0,
            'avg_prereq_grade': avg_prereq_grade / 4.0,
            'min_prereq_grade': min_prereq_grade / 4.0,
            'num_prereqs_taken': len(prereq_grades) / 10.0,
            'difficulty_score': 1.0 - (actual_grade_points / 4.0)
        }
        
        training_data.append(features)
    
    df = pd.DataFrame(training_data)
    print(f"Created {len(df)} training samples")
    
    return df


def train_model1():
    print("=" * 60)
    print("MODEL 1: COURSE DIFFICULTY PREDICTION")
    print("=" * 60)
    
    courses_df, students_df, student_courses_df = load_data()
    
    training_df = create_training_features(courses_df, students_df, student_courses_df)
    
    feature_columns = [
        'course_level', 'prerequisite_count', 'prerequisite_depth', 'graph_centrality',
        'credit_hours', 'is_lab', 'student_gpa', 'academic_ability', 'workload_tolerance',
        'total_courses_completed', 'avg_prereq_grade', 'min_prereq_grade', 'num_prereqs_taken'
    ]
    
    X = training_df[feature_columns]
    y = training_df['difficulty_score']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    print("\n" + "-" * 60)
    print("Training Random Forest Model...")
    print("-" * 60)
    
    rf_model = RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    
    rf_model.fit(X_train, y_train)
    
    rf_train_pred = rf_model.predict(X_train)
    rf_test_pred = rf_model.predict(X_test)
    
    rf_train_rmse = np.sqrt(mean_squared_error(y_train, rf_train_pred))
    rf_test_rmse = np.sqrt(mean_squared_error(y_test, rf_test_pred))
    rf_train_r2 = r2_score(y_train, rf_train_pred)
    rf_test_r2 = r2_score(y_test, rf_test_pred)
    rf_mae = mean_absolute_error(y_test, rf_test_pred)
    
    print(f"Random Forest Results:")
    print(f"  Train RMSE: {rf_train_rmse:.4f}")
    print(f"  Test RMSE: {rf_test_rmse:.4f}")
    print(f"  Train R²: {rf_train_r2:.4f}")
    print(f"  Test R²: {rf_test_r2:.4f}")
    print(f"  Test MAE: {rf_mae:.4f}")
    
    print("\n" + "-" * 60)
    print("Training XGBoost Model...")
    print("-" * 60)
    
    xgb_model = xgb.XGBRegressor(
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
    
    xgb_train_rmse = np.sqrt(mean_squared_error(y_train, xgb_train_pred))
    xgb_test_rmse = np.sqrt(mean_squared_error(y_test, xgb_test_pred))
    xgb_train_r2 = r2_score(y_train, xgb_train_pred)
    xgb_test_r2 = r2_score(y_test, xgb_test_pred)
    xgb_mae = mean_absolute_error(y_test, xgb_test_pred)
    
    print(f"XGBoost Results:")
    print(f"  Train RMSE: {xgb_train_rmse:.4f}")
    print(f"  Test RMSE: {xgb_test_rmse:.4f}")
    print(f"  Train R²: {xgb_train_r2:.4f}")
    print(f"  Test R²: {xgb_test_r2:.4f}")
    print(f"  Test MAE: {xgb_mae:.4f}")
    
    if xgb_test_rmse < rf_test_rmse:
        best_model = xgb_model
        best_name = "XGBoost"
        best_rmse = xgb_test_rmse
        print(f"\n[OK] Best model: XGBoost (RMSE: {best_rmse:.4f})")
    else:
        best_model = rf_model
        best_name = "Random Forest"
        best_rmse = rf_test_rmse
        print(f"\n[OK] Best model: Random Forest (RMSE: {best_rmse:.4f})")
    
    with open(MODEL1_RF_FILE, 'wb') as f:
        pickle.dump(rf_model, f)
    print(f"[OK] Saved Random Forest model to {MODEL1_RF_FILE}")
    
    with open(MODEL1_XGB_FILE, 'wb') as f:
        pickle.dump(xgb_model, f)
    print(f"[OK] Saved XGBoost model to {MODEL1_XGB_FILE}")
    
    feature_info = {
        'feature_columns': feature_columns,
        'best_model': best_name,
        'test_rmse': float(best_rmse),
        'test_r2': float(xgb_test_r2 if best_name == "XGBoost" else rf_test_r2)
    }
    
    with open(MODELS_DIR / 'model1_info.pkl', 'wb') as f:
        pickle.dump(feature_info, f)
    
    print(f"\n[OK] Model 1 training complete!")
    return rf_model, xgb_model, feature_columns


if __name__ == '__main__':
    train_model1()
