import pandas as pd
import numpy as np
from pathlib import Path
import pickle
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, mean_absolute_error
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
MODELS_DIR.mkdir(exist_ok=True)

MODEL2_GB_FILE = MODELS_DIR / 'model2_gradient_boosting.pkl'
MODEL2_NN_FILE = MODELS_DIR / 'model2_neural_network.pkl'
MODEL1_XGB_FILE = MODELS_DIR / 'model1_xgboost.pkl'


def load_data():
    print("Loading data...")
    courses_df = pd.read_csv(COURSES_FILE)
    students_df = pd.read_csv(STUDENTS_FILE)
    student_courses_df = pd.read_csv(STUDENT_COURSES_FILE)
    
    return courses_df, students_df, student_courses_df


def predict_course_difficulties(student_id, semester_courses, courses_df, students_df, student_courses_df):
    with open(MODEL1_XGB_FILE, 'rb') as f:
        model1 = pickle.load(f)
    
    with open(MODELS_DIR / 'model1_info.pkl', 'rb') as f:
        model1_info = pickle.load(f)
    
    feature_columns = model1_info['feature_columns']
    
    student = students_df[students_df['student_id'] == student_id].iloc[0]
    
    prereq_courses = student_courses_df[
        (student_courses_df['student_id'] == student_id) &
        (student_courses_df['semester_taken'] < 999)
    ]
    prereq_grades = prereq_courses['grade_points'].tolist() if len(prereq_courses) > 0 else []
    avg_prereq_grade = np.mean(prereq_grades) if prereq_grades else 3.0
    min_prereq_grade = np.min(prereq_grades) if prereq_grades else 3.0
    
    difficulties = []
    
    for course_code in semester_courses:
        course = courses_df[courses_df['course_code'] == course_code]
        if course.empty:
            continue
        course = course.iloc[0]
        
        features = np.array([[
            course['course_level'] / 500.0,
            course['prerequisite_count'] / 10.0,
            course['prerequisite_depth'] / 10.0,
            course['graph_centrality'],
            course['credit_hours'] / 4.0,
            1 if course['is_lab'] else 0,
            student['gpa'] / 4.0,
            student['academic_ability'],
            student['workload_tolerance'],
            student['total_courses_completed'] / 50.0,
            avg_prereq_grade / 4.0,
            min_prereq_grade / 4.0,
            len(prereq_grades) / 10.0
        ]])
        
        difficulty = model1.predict(features)[0]
        difficulties.append(difficulty)
    
    return difficulties


def create_training_features(courses_df, students_df, student_courses_df):
    print("Creating training features for semester workload...")
    
    training_data = []
    
    for student_id in student_courses_df['student_id'].unique():
        student_courses = student_courses_df[student_courses_df['student_id'] == student_id]
        student = students_df[students_df['student_id'] == student_id].iloc[0]
        
        for semester in student_courses['semester_taken'].unique():
            semester_courses = student_courses[student_courses['semester_taken'] == semester]
            
            if len(semester_courses) == 0:
                continue
            
            course_codes = semester_courses['course_code'].tolist()
            
            try:
                course_difficulties = predict_course_difficulties(
                    student_id, course_codes, courses_df, students_df, student_courses_df
                )
            except:
                course_difficulties = [1.0 - (g / 4.0) for g in semester_courses['grade_points'].tolist()]
            
            total_credits = semester_courses['credit_hours'].sum()
            num_courses = len(semester_courses)
            num_labs = semester_courses['is_lab'].sum()
            
            avg_difficulty = np.mean(course_difficulties) if course_difficulties else 0.5
            max_difficulty = np.max(course_difficulties) if course_difficulties else 0.5
            difficulty_variance = np.var(course_difficulties) if len(course_difficulties) > 1 else 0.0
            
            actual_grades = semester_courses['grade_points'].tolist()
            actual_semester_difficulty = 1.0 - (np.mean(actual_grades) / 4.0)
            
            overload_risk = min(1.0, (total_credits / 18.0) * (1 + avg_difficulty))
            
            features = {
                'avg_course_difficulty': avg_difficulty,
                'max_course_difficulty': max_difficulty,
                'difficulty_variance': difficulty_variance,
                'total_credits': total_credits / 18.0,
                'num_courses': num_courses / 6.0,
                'num_labs': num_labs / 3.0,
                'student_gpa': student['gpa'] / 4.0,
                'workload_tolerance': student['workload_tolerance'],
                'academic_ability': student['academic_ability'],
                'total_courses_completed': student['total_courses_completed'] / 50.0,
                'semester_difficulty': actual_semester_difficulty,
                'overload_risk': overload_risk
            }
            
            training_data.append(features)
    
    df = pd.DataFrame(training_data)
    print(f"Created {len(df)} semester training samples")
    
    return df


def train_model2():
    print("=" * 60)
    print("MODEL 2: SEMESTER WORKLOAD DIFFICULTY ESTIMATION")
    print("=" * 60)
    
    if not MODEL1_XGB_FILE.exists():
        print("[ERROR] Model 1 not found. Please train Model 1 first.")
        return
    
    courses_df, students_df, student_courses_df = load_data()
    
    print("\nCreating training features (this may take a while)...")
    training_df = create_training_features(courses_df, students_df, student_courses_df)
    
    feature_columns = [
        'avg_course_difficulty', 'max_course_difficulty', 'difficulty_variance',
        'total_credits', 'num_courses', 'num_labs',
        'student_gpa', 'workload_tolerance', 'academic_ability', 'total_courses_completed'
    ]
    
    X = training_df[feature_columns]
    y = training_df['semester_difficulty']
    y_overload = training_df['overload_risk']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    _, _, y_overload_train, y_overload_test = train_test_split(X, y_overload, test_size=0.2, random_state=42)
    
    print(f"\nTraining set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("\n" + "-" * 60)
    print("Training Gradient Boosting Model...")
    print("-" * 60)
    
    gb_model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42
    )
    
    gb_model.fit(X_train, y_train)
    
    gb_train_pred = gb_model.predict(X_train)
    gb_test_pred = gb_model.predict(X_test)
    
    gb_train_rmse = np.sqrt(mean_squared_error(y_train, gb_train_pred))
    gb_test_rmse = np.sqrt(mean_squared_error(y_test, gb_test_pred))
    gb_train_r2 = r2_score(y_train, gb_train_pred)
    gb_test_r2 = r2_score(y_test, gb_test_pred)
    gb_mae = mean_absolute_error(y_test, gb_test_pred)
    
    print(f"Gradient Boosting Results:")
    print(f"  Train RMSE: {gb_train_rmse:.4f}")
    print(f"  Test RMSE: {gb_test_rmse:.4f}")
    print(f"  Train R²: {gb_train_r2:.4f}")
    print(f"  Test R²: {gb_test_r2:.4f}")
    print(f"  Test MAE: {gb_mae:.4f}")
    
    print("\n" + "-" * 60)
    print("Training Neural Network Model...")
    print("-" * 60)
    
    nn_model = MLPRegressor(
        hidden_layer_sizes=(64, 32, 16),
        activation='relu',
        solver='adam',
        alpha=0.001,
        learning_rate='adaptive',
        max_iter=500,
        random_state=42,
        early_stopping=True,
        validation_fraction=0.1
    )
    
    nn_model.fit(X_train_scaled, y_train)
    
    nn_train_pred = nn_model.predict(X_train_scaled)
    nn_test_pred = nn_model.predict(X_test_scaled)
    
    nn_train_rmse = np.sqrt(mean_squared_error(y_train, nn_train_pred))
    nn_test_rmse = np.sqrt(mean_squared_error(y_test, nn_test_pred))
    nn_train_r2 = r2_score(y_train, nn_train_pred)
    nn_test_r2 = r2_score(y_test, nn_test_pred)
    nn_mae = mean_absolute_error(y_test, nn_test_pred)
    
    print(f"Neural Network Results:")
    print(f"  Train RMSE: {nn_train_rmse:.4f}")
    print(f"  Test RMSE: {nn_test_rmse:.4f}")
    print(f"  Train R²: {nn_train_r2:.4f}")
    print(f"  Test R²: {nn_test_r2:.4f}")
    print(f"  Test MAE: {nn_mae:.4f}")
    
    if nn_test_rmse < gb_test_rmse:
        best_model = nn_model
        best_name = "Neural Network"
        best_rmse = nn_test_rmse
        print(f"\n[OK] Best model: Neural Network (RMSE: {best_rmse:.4f})")
    else:
        best_model = gb_model
        best_name = "Gradient Boosting"
        best_rmse = gb_test_rmse
        print(f"\n[OK] Best model: Gradient Boosting (RMSE: {best_rmse:.4f})")
    
    with open(MODEL2_GB_FILE, 'wb') as f:
        pickle.dump(gb_model, f)
    print(f"[OK] Saved Gradient Boosting model to {MODEL2_GB_FILE}")
    
    with open(MODEL2_NN_FILE, 'wb') as f:
        pickle.dump(nn_model, f)
    print(f"[OK] Saved Neural Network model to {MODEL2_NN_FILE}")
    
    with open(MODELS_DIR / 'model2_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    print(f"[OK] Saved scaler to {MODELS_DIR / 'model2_scaler.pkl'}")
    
    feature_info = {
        'feature_columns': feature_columns,
        'best_model': best_name,
        'test_rmse': float(best_rmse),
        'test_r2': float(nn_test_r2 if best_name == "Neural Network" else gb_test_r2),
        'uses_scaler': best_name == "Neural Network"
    }
    
    with open(MODELS_DIR / 'model2_info.pkl', 'wb') as f:
        pickle.dump(feature_info, f)
    
    print(f"\n[OK] Model 2 training complete!")
    return gb_model, nn_model, feature_columns, scaler


if __name__ == '__main__':
    train_model2()
