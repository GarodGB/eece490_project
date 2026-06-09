
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit, train_test_split
from sklearn.ensemble import GradientBoostingRegressor

DATA_DIR = Path(__file__).parent.parent / 'Data'
COURSES_FILE = DATA_DIR / 'merged_courses.csv'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
REPORTS_DIR = Path(__file__).parent.parent / 'reports' / 'ml'
MODELS_DIR.mkdir(exist_ok=True, parents=True)
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

MODEL1_RF_FILE = MODELS_DIR / 'model1_random_forest.pkl'
MODEL1_XGB_FILE = MODELS_DIR / 'model1_xgboost.pkl'
INFO_FILE = MODELS_DIR / 'model1_info.pkl'


def _safe_series(df, col, default):
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce').fillna(default)
    return pd.Series(default, index=df.index)


def create_training_features():
    students = pd.read_csv(STUDENTS_FILE)
    attempts = pd.read_csv(STUDENT_COURSES_FILE)
    df = attempts.merge(students[['student_id','workload_tolerance']], on='student_id', how='left')
    # Personalized difficulty = how difficult the course was expected to feel before taking it.
    # Lower grade points imply more experienced difficulty, but we use only pre-attempt features.
    df['target_difficulty'] = 1.0 - (pd.to_numeric(df['grade_points'], errors='coerce').fillna(2.7) / 4.0)
    df['course_pressure'] = _safe_series(df, 'course_pressure', 0.5)
    df['prior_gpa_norm'] = _safe_series(df, 'prior_gpa', 3.0) / 4.0
    df['recent_avg_norm'] = _safe_series(df, 'recent_grade_avg_before', 3.0) / 4.0
    df['prereq_avg_norm'] = _safe_series(df, 'prereq_avg_before', 3.0) / 4.0
    df['workload_tolerance'] = _safe_series(df, 'workload_tolerance', 0.5)
    df['course_level_norm'] = _safe_series(df, 'course_level', 100) / 500.0
    df['credit_norm'] = _safe_series(df, 'credit_hours', 3.0) / 4.0
    df['prereq_count_norm'] = _safe_series(df, 'prerequisite_count', 0) / 10.0
    df['prereq_depth_norm'] = _safe_series(df, 'prerequisite_depth', 0) / 10.0
    df['centrality_norm'] = _safe_series(df, 'graph_centrality', 0.0)
    df['is_lab'] = df['is_lab'].astype(str).str.lower().isin(['true','1','yes']).astype(int)
    df['prior_credits_norm'] = _safe_series(df, 'prior_credits', 0.0) / 150.0
    df['completed_before_norm'] = _safe_series(df, 'completed_courses_before', 0.0) / 50.0
    df['term_load_norm'] = _safe_series(df, 'term_credit_load', 15.0) / 18.0
    df['prereq_completed_ratio'] = _safe_series(df, 'prerequisite_completed_ratio', 1.0)

    feature_columns = [
        'course_level_norm','credit_norm','prereq_count_norm','prereq_depth_norm','centrality_norm','is_lab',
        'course_pressure','prior_gpa_norm','recent_avg_norm','prereq_avg_norm','workload_tolerance',
        'prior_credits_norm','completed_before_norm','term_load_norm','prereq_completed_ratio'
    ]
    return df[feature_columns].fillna(0.0), df['target_difficulty'].clip(0,1), feature_columns, df['student_id']


def _group_split(X, y, groups):
    try:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, test_idx = next(splitter.split(X, y, groups=groups))
        return X.iloc[train_idx], X.iloc[test_idx], y.iloc[train_idx], y.iloc[test_idx]
    except Exception:
        return train_test_split(X, y, test_size=0.2, random_state=42)


def train_model1():
    print('='*70)
    print('MODEL 1: PERSONALIZED COURSE DIFFICULTY')
    print('='*70)
    X, y, feature_columns, groups = create_training_features()
    X_train, X_test, y_train, y_test = _group_split(X, y, groups)

    baseline_pred = np.repeat(y_train.mean(), len(y_test))
    baseline_mae = mean_absolute_error(y_test, baseline_pred)

    rf = RandomForestRegressor(n_estimators=100, max_depth=10, min_samples_leaf=5, random_state=42, n_jobs=-1)
    xgbr = GradientBoostingRegressor(n_estimators=90, max_depth=3, learning_rate=0.055, subsample=0.85, random_state=42)

    results = {}
    for name, model in [('Random Forest', rf), ('Gradient Boosting', xgbr)]:
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test), 0, 1)
        results[name] = {
            'model': model,
            'mae': float(mean_absolute_error(y_test, pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, pred))),
            'r2': float(r2_score(y_test, pred)),
        }
        print(f"{name}: MAE={results[name]['mae']:.4f} RMSE={results[name]['rmse']:.4f} R2={results[name]['r2']:.4f}")

    best_name = min(results, key=lambda k: results[k]['mae'])
    with open(MODEL1_RF_FILE, 'wb') as f: pickle.dump(rf, f)
    with open(MODEL1_XGB_FILE, 'wb') as f: pickle.dump(xgbr, f)
    info = {
        'model_name': 'Model 1: Personalized Course Difficulty',
        'target': '1 - grade_points / 4 using pre-attempt features only',
        'best_model': best_name,
        'feature_columns': feature_columns,
        'baseline_mae': round(float(baseline_mae),4),
        'models': {k:{kk:round(vv,4) for kk,vv in vals.items() if kk!='model'} for k,vals in results.items()},
    }
    with open(INFO_FILE, 'wb') as f: pickle.dump(info, f)
    (REPORTS_DIR/'model1_course_difficulty_metrics.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print(f'[OK] best={best_name}, baseline MAE={baseline_mae:.4f}')
    return info

if __name__ == '__main__':
    train_model1()
