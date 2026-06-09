
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).parent.parent / 'Data'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
REPORTS_DIR = Path(__file__).parent.parent / 'reports' / 'ml'
MODELS_DIR.mkdir(exist_ok=True, parents=True)
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

MODEL3_GB_FILE = MODELS_DIR / 'model3_gradient_boosting_risk.pkl'
MODEL3_XGB_FILE = MODELS_DIR / 'model3_xgboost_risk.pkl'  # kept name for compatibility, stores RF now if XGBoost not needed
INFO_FILE = MODELS_DIR / 'model3_info.pkl'

RISK_LEVELS = {0:'Low',1:'Medium',2:'High',3:'Critical'}


def _features_from_history(hist, student):
    grades = hist['grade_points'].astype(float).tolist()
    recent = grades[-6:]
    if not grades:
        grades = [float(student.get('gpa',3.0))]
        recent = grades
    avg = float(np.mean(grades))
    recent_avg = float(np.mean(recent))
    min_recent = float(np.min(recent))
    low_count = sum(g < 2.0 for g in recent)
    fail_count = sum(g < 1.0 for g in recent)
    weak_pass_count = sum(1.0 <= g < 2.3 for g in recent)
    if len(recent) > 2:
        try:
            trend = float(np.polyfit(np.arange(len(recent)), np.array(recent), 1)[0])
        except Exception:
            trend = 0.0
    else:
        trend = 0.0
    credits_by_sem = hist.groupby('semester_taken')['credit_hours'].sum() if len(hist) else pd.Series(dtype=float)
    avg_term_credits = float(credits_by_sem.mean()) if len(credits_by_sem) else 12.0
    max_term_credits = float(credits_by_sem.max()) if len(credits_by_sem) else 12.0
    return {
        'current_gpa': avg/4.0,
        'avg_grade': avg/4.0,
        'avg_recent_grade': recent_avg/4.0,
        'min_recent_grade': min_recent/4.0,
        'gpa_trend_slope': trend,
        'failed_count': fail_count/6.0,
        'low_grade_count': low_count/6.0,
        'weak_pass_count': weak_pass_count/6.0,
        'avg_term_credits': avg_term_credits/18.0,
        'max_term_credits': max_term_credits/18.0,
        'completed_courses': len(hist)/50.0,
        'workload_tolerance': float(student.get('workload_tolerance',0.5)),
    }


def _future_label(future):
    if len(future) == 0:
        return None
    grades = future['grade_points'].astype(float).tolist()
    avg_future = float(np.mean(grades))
    fails = sum(g < 1.0 for g in grades)
    lows = sum(g < 2.0 for g in grades)
    if fails >= 1 or avg_future < 1.7:
        return 3
    if avg_future < 2.3 or lows >= 2:
        return 2
    if avg_future < 3.0:
        return 1
    return 0


def create_training_features():
    students = pd.read_csv(STUDENTS_FILE)
    attempts = pd.read_csv(STUDENT_COURSES_FILE).sort_values(['student_id','semester_taken'])
    rows=[]
    for _, student in students.iterrows():
        sid = student['student_id']
        sc = attempts[attempts['student_id']==sid]
        if sc['semester_taken'].nunique() < 3 or len(sc) < 8:
            continue
        semesters = sorted(sc['semester_taken'].unique())
        split_sem = semesters[-2]
        hist = sc[sc['semester_taken'] < split_sem]
        future = sc[sc['semester_taken'] >= split_sem]
        label = _future_label(future)
        if label is None or len(hist) < 4:
            continue
        feat = _features_from_history(hist, student)
        feat['risk_level'] = label
        rows.append(feat)
    df=pd.DataFrame(rows)
    feature_columns=[c for c in df.columns if c!='risk_level']
    return df[feature_columns].fillna(0.0), df['risk_level'].astype(int), feature_columns


def _rule_baseline(row):
    if row['current_gpa'] < 0.50 or row['failed_count'] > 0.15:
        return 3
    if row['current_gpa'] < 0.625 or row['low_grade_count'] > 0.25:
        return 2
    if row['current_gpa'] < 0.75 or row['avg_recent_grade'] < 0.70:
        return 1
    return 0


def train_model3():
    print('='*70)
    print('MODEL 3: FUTURE ACADEMIC RISK')
    print('='*70)
    X, y, feature_columns = create_training_features()
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42, stratify=y)
    baseline_pred = X_test.apply(_rule_baseline, axis=1)
    baseline_macro_f1 = f1_score(y_test, baseline_pred, average='macro')

    gb = GradientBoostingClassifier(n_estimators=80, max_depth=3, learning_rate=0.05, random_state=42)
    rf = RandomForestClassifier(n_estimators=120, max_depth=12, min_samples_leaf=4, class_weight='balanced', random_state=42, n_jobs=-1)
    results={}
    for name, model in [('Gradient Boosting',gb),('Random Forest',rf)]:
        model.fit(X_train,y_train)
        pred=model.predict(X_test)
        results[name]={
            'model': model,
            'accuracy': float(accuracy_score(y_test,pred)),
            'macro_f1': float(f1_score(y_test,pred,average='macro')),
            'report': classification_report(y_test,pred, output_dict=True, zero_division=0),
        }
        print(f"{name}: acc={results[name]['accuracy']:.4f} macroF1={results[name]['macro_f1']:.4f}")

    best_name=max(results, key=lambda k: results[k]['macro_f1'])
    with open(MODEL3_GB_FILE,'wb') as f: pickle.dump(gb,f)
    with open(MODEL3_XGB_FILE,'wb') as f: pickle.dump(rf,f)
    info={
        'model_name':'Model 3: Future Academic Risk',
        'target':'risk in future semesters, not same-row rule label',
        'best_model': best_name,
        'feature_columns': feature_columns,
        'risk_levels': RISK_LEVELS,
        'rule_baseline_macro_f1': round(float(baseline_macro_f1),4),
        'models': {k:{'accuracy':round(v['accuracy'],4),'macro_f1':round(v['macro_f1'],4)} for k,v in results.items()},
    }
    with open(INFO_FILE,'wb') as f: pickle.dump(info,f)
    (REPORTS_DIR/'model3_future_risk_metrics.json').write_text(json.dumps(info,indent=2), encoding='utf-8')
    print(f'[OK] best={best_name}, baseline macroF1={baseline_macro_f1:.4f}')
    return info

if __name__ == '__main__':
    train_model3()
