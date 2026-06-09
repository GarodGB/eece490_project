
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report, brier_score_loss
from sklearn.model_selection import GroupShuffleSplit
from sklearn.calibration import calibration_curve

BASE_DIR = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = BASE_DIR / 'Data' / 'synthetic'
MODELS_DIR = BASE_DIR / 'ml' / 'models'
REPORTS_DIR = BASE_DIR / 'reports' / 'ml'
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

STUDENTS_FILE = SYNTHETIC_DIR / 'synthetic_students.csv'
ATTEMPTS_FILE = SYNTHETIC_DIR / 'synthetic_student_courses.csv'
MODEL4_RF_FILE = MODELS_DIR / 'model4_random_forest_success.pkl'
MODEL4_GB_FILE = MODELS_DIR / 'model4_gradient_boosting_success.pkl'
MODEL4_INFO_FILE = MODELS_DIR / 'model4_info.pkl'

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

    df['success'] = (pd.to_numeric(df['grade_points'], errors='coerce').fillna(0) >= 2.3).astype(int)
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
    y = df['success']
    groups = df['student_id']
    return X, y, FEATURE_COLUMNS, groups


def train_model4():
    print('='*80)
    print('MODEL 4: COURSE SUCCESS PROBABILITY - STRENGTH/WEAKNESS FEATURES')
    print('='*80)
    X, y, feature_columns, groups = _build_training_dataset()
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    tr, te = next(splitter.split(X, y, groups=groups))
    X_train, X_test = X.iloc[tr], X.iloc[te]
    y_train, y_test = y.iloc[tr], y.iloc[te]
    baseline_prob = np.repeat(y_train.mean(), len(y_test))
    baseline_auc = roc_auc_score(y_test, baseline_prob) if len(set(y_test)) > 1 else 0.5
    baseline_brier = brier_score_loss(y_test, baseline_prob)

    rf = RandomForestClassifier(n_estimators=90, max_depth=10, min_samples_leaf=8, class_weight='balanced', random_state=42, n_jobs=-1)
    gb = GradientBoostingClassifier(n_estimators=85, learning_rate=0.055, max_depth=3, random_state=42)
    results = {}
    for name, model in [('Random Forest', rf), ('Gradient Boosting', gb)]:
        model.fit(X_train, y_train)
        pred = model.predict(X_test)
        prob = model.predict_proba(X_test)[:,1]
        auc = roc_auc_score(y_test, prob) if len(set(y_test)) > 1 else 0.5
        results[name] = {
            'model': model,
            'accuracy': float(accuracy_score(y_test, pred)),
            'roc_auc': float(auc),
            'brier': float(brier_score_loss(y_test, prob)),
        }
        print(f"{name}: accuracy={results[name]['accuracy']:.4f} AUC={auc:.4f} brier={results[name]['brier']:.4f}")
        print(classification_report(y_test, pred))
    best_name = max(results, key=lambda k: (results[k]['roc_auc'], -results[k]['brier']))
    with open(MODEL4_RF_FILE,'wb') as f: pickle.dump(rf,f)
    with open(MODEL4_GB_FILE,'wb') as f: pickle.dump(gb,f)
    info = {
        'model_name': 'Model 4: Course Success Probability',
        'success_definition': 'course grade_points >= 2.3 (C+ or above)',
        'best_model': best_name,
        'feature_columns': feature_columns,
        'split': 'student-level GroupShuffleSplit to avoid same-student leakage',
        'baseline': {'constant_success_rate_auc': round(float(baseline_auc),4), 'brier': round(float(baseline_brier),4)},
        'models': {k:{'accuracy':round(v['accuracy'],4),'roc_auc':round(v['roc_auc'],4),'brier':round(v['brier'],4)} for k,v in results.items()},
    }
    with open(MODEL4_INFO_FILE,'wb') as f: pickle.dump(info,f)
    (REPORTS_DIR/'model4_success_metrics.json').write_text(json.dumps(info,indent=2), encoding='utf-8')
    print(f'[OK] Best model: {best_name}')
    return info

if __name__ == '__main__':
    train_model4()
