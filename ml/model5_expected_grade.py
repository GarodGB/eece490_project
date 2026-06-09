
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit

BASE_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = BASE_DIR / 'Data' / 'synthetic'
MODELS_DIR = BASE_DIR / 'ml' / 'models'
REPORTS_DIR = BASE_DIR / 'reports' / 'ml'
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

STUDENTS_FILE = SYNTHETIC_DIR / 'synthetic_students.csv'
ATTEMPTS_FILE = SYNTHETIC_DIR / 'synthetic_student_courses.csv'
MODEL5_RF_FILE = MODELS_DIR / 'model5_random_forest_grade.pkl'
MODEL5_GB_FILE = MODELS_DIR / 'model5_gradient_boosting_grade.pkl'
MODEL5_INFO_FILE = MODELS_DIR / 'model5_info.pkl'

FEATURE_COLUMNS = [
    'prior_gpa_norm','recent_avg_norm','prereq_avg_norm','subject_avg_norm','area_strength_norm',
    'workload_tolerance','course_level_norm','credit_norm','prereq_count_norm','prereq_depth_norm',
    'centrality_norm','is_lab','prior_credits_norm','completed_before_norm','term_load_norm',
    'course_pressure','prereq_completed_ratio','fit_minus_pressure','weak_area_flag','strong_area_flag',
    'is_major_or_core','is_support','is_elective'
]


def _safe_series(df, col, default):
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce').fillna(default)
    return pd.Series(default, index=df.index)


def _build_training_dataset():
    students = pd.read_csv(STUDENTS_FILE)
    attempts = pd.read_csv(ATTEMPTS_FILE)
    df = attempts.merge(students[['student_id','workload_tolerance']], on='student_id', how='left')
    df['prior_gpa_norm'] = _safe_series(df,'prior_gpa',3.0) / 4.0
    df['recent_avg_norm'] = _safe_series(df,'recent_grade_avg_before',3.0) / 4.0
    df['prereq_avg_norm'] = _safe_series(df,'prereq_avg_before',3.0) / 4.0
    df['subject_avg_norm'] = _safe_series(df,'subject_avg_before',3.0) / 4.0
    df['area_strength_norm'] = _safe_series(df,'area_strength_before',3.0) / 4.0
    df['workload_tolerance'] = _safe_series(df,'workload_tolerance',0.5)
    df['course_level_norm'] = _safe_series(df,'course_level',100) / 500.0
    df['credit_norm'] = _safe_series(df,'credit_hours',3.0) / 4.0
    df['prereq_count_norm'] = _safe_series(df,'prerequisite_count',0) / 10.0
    df['prereq_depth_norm'] = _safe_series(df,'prerequisite_depth',0) / 10.0
    df['centrality_norm'] = _safe_series(df,'graph_centrality',0.0)
    df['is_lab'] = df.get('is_lab', 0).astype(str).str.lower().isin(['true','1','yes']).astype(int)
    df['prior_credits_norm'] = _safe_series(df,'prior_credits',0) / 150.0
    df['completed_before_norm'] = _safe_series(df,'completed_courses_before',0) / 50.0
    df['term_load_norm'] = _safe_series(df,'term_credit_load',15.0) / 18.0
    df['course_pressure'] = _safe_series(df,'course_pressure',0.5)
    df['prereq_completed_ratio'] = _safe_series(df,'prerequisite_completed_ratio',1.0)
    df['weak_area_flag'] = _safe_series(df,'weak_area_flag',0).clip(0,1)
    df['strong_area_flag'] = _safe_series(df,'strong_area_flag',0).clip(0,1)
    ctype = df.get('course_type', '').astype(str).str.lower()
    subj = df.get('subject', '').astype(str).str.upper()
    df['is_major_or_core'] = ((ctype == 'core') | (subj == 'EECE')).astype(int)
    df['is_support'] = (ctype == 'support').astype(int)
    df['is_elective'] = ctype.isin(['major_elective','general_elective']).astype(int)
    df['fit_minus_pressure'] = (
        0.34*df['prior_gpa_norm'] + 0.24*df['recent_avg_norm'] + 0.18*df['area_strength_norm']
        + 0.14*df['prereq_avg_norm'] + 0.10*df['workload_tolerance'] - df['course_pressure']
    )
    X = df[FEATURE_COLUMNS].fillna(0.0)
    y = pd.to_numeric(df['grade_points'], errors='coerce').fillna(2.7).clip(0, 4.3)
    groups = df['student_id']
    return X, y, FEATURE_COLUMNS, groups


def train_model5():
    print('='*80)
    print('MODEL 5: EXPECTED AUB GRADE POINTS - GPA TARGET MODEL')
    print('='*80)
    X, y, feature_columns, groups = _build_training_dataset()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    tr, te = next(splitter.split(X, y, groups=groups))
    X_train, X_test = X.iloc[tr], X.iloc[te]
    y_train, y_test = y.iloc[tr], y.iloc[te]
    baseline_pred = np.repeat(y_train.mean(), len(y_test))
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    rf = RandomForestRegressor(n_estimators=100, max_depth=11, min_samples_leaf=8, random_state=42, n_jobs=-1)
    gb = GradientBoostingRegressor(n_estimators=90, learning_rate=0.045, max_depth=3, random_state=42)
    results = {}
    for name, model in [('Random Forest', rf), ('Gradient Boosting', gb)]:
        model.fit(X_train, y_train)
        pred = np.clip(model.predict(X_test), 0, 4.3)
        results[name] = {
            'model': model,
            'mae': float(mean_absolute_error(y_test, pred)),
            'rmse': float(np.sqrt(mean_squared_error(y_test, pred))),
            'r2': float(r2_score(y_test, pred)),
        }
        print(f"{name}: MAE={results[name]['mae']:.4f} RMSE={results[name]['rmse']:.4f} R2={results[name]['r2']:.4f}")
    best_name = min(results, key=lambda k: results[k]['mae'])
    with open(MODEL5_RF_FILE,'wb') as f: pickle.dump(rf,f)
    with open(MODEL5_GB_FILE,'wb') as f: pickle.dump(gb,f)
    info = {
        'model_name': 'Model 5: Expected AUB Grade Points',
        'target': 'expected course grade points out of 4.3 using pre-attempt features only; cumulative GPA remains capped at 4.0',
        'best_model': best_name,
        'feature_columns': feature_columns,
        'split': 'student-level GroupShuffleSplit to avoid same-student leakage',
        'baseline_mae': round(float(baseline_mae),4),
        'models': {k:{'mae':round(v['mae'],4),'rmse':round(v['rmse'],4),'r2':round(v['r2'],4)} for k,v in results.items()},
    }
    with open(MODEL5_INFO_FILE,'wb') as f: pickle.dump(info,f)
    (REPORTS_DIR/'model5_expected_grade_metrics.json').write_text(json.dumps(info,indent=2), encoding='utf-8')
    print(f'[OK] Best model: {best_name}. Baseline MAE={baseline_mae:.4f}')
    return info

if __name__ == '__main__':
    train_model5()
