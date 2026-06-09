
import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

DATA_DIR = Path(__file__).parent.parent / 'Data'
STUDENTS_FILE = DATA_DIR / 'synthetic' / 'synthetic_students.csv'
STUDENT_COURSES_FILE = DATA_DIR / 'synthetic' / 'synthetic_student_courses.csv'
MODELS_DIR = Path(__file__).parent / 'models'
REPORTS_DIR = Path(__file__).parent.parent / 'reports' / 'ml'
MODELS_DIR.mkdir(exist_ok=True, parents=True)
REPORTS_DIR.mkdir(exist_ok=True, parents=True)

MODEL2_GB_FILE = MODELS_DIR / 'model2_gradient_boosting.pkl'
MODEL2_NN_FILE = MODELS_DIR / 'model2_neural_network.pkl'  # compatibility: stores RF
MODEL2_SCALER_FILE = MODELS_DIR / 'model2_scaler.pkl'
INFO_FILE = MODELS_DIR / 'model2_info.pkl'


def _safe_series(df, col, default):
    if col in df.columns:
        return pd.to_numeric(df[col], errors='coerce').fillna(default)
    return pd.Series(default, index=df.index)


def create_training_features():
    students = pd.read_csv(STUDENTS_FILE)
    attempts = pd.read_csv(STUDENT_COURSES_FILE)
    df = attempts.merge(students[['student_id','workload_tolerance']], on='student_id', how='left')
    df['course_pressure'] = _safe_series(df, 'course_pressure', 0.5)
    df['difficulty_observed'] = 1.0 - (pd.to_numeric(df['grade_points'], errors='coerce').fillna(2.7) / 4.0)
    df['is_lab_int'] = df['is_lab'].astype(str).str.lower().isin(['true','1','yes']).astype(int)
    group_cols = ['student_id','semester_taken']
    agg = df.groupby(group_cols).agg(
        avg_difficulty=('difficulty_observed','mean'),
        max_difficulty=('difficulty_observed','max'),
        var_difficulty=('difficulty_observed','var'),
        avg_pressure=('course_pressure','mean'),
        max_pressure=('course_pressure','max'),
        total_credits=('credit_hours','sum'),
        num_courses=('course_code','count'),
        num_labs=('is_lab_int','sum'),
        avg_level=('course_level','mean'),
        prior_gpa=('prior_gpa','mean'),
        recent_avg=('recent_grade_avg_before','mean'),
        workload_tolerance=('workload_tolerance','mean'),
    ).reset_index()
    agg['var_difficulty'] = agg['var_difficulty'].fillna(0.0)
    agg['target_workload'] = (
        0.38*agg['avg_difficulty'] + 0.16*agg['max_difficulty'] + 0.20*(agg['total_credits']/18.0)
        + 0.10*(agg['num_courses']/6.0) + 0.09*(agg['num_labs']/3.0) + 0.07*agg['avg_pressure']
        - 0.14*agg['workload_tolerance']
    ).clip(0,1)
    agg['total_credits_norm'] = agg['total_credits']/18.0
    agg['num_courses_norm'] = agg['num_courses']/6.0
    agg['num_labs_norm'] = agg['num_labs']/3.0
    agg['avg_level_norm'] = agg['avg_level']/500.0
    agg['prior_gpa_norm'] = agg['prior_gpa']/4.0
    agg['recent_avg_norm'] = agg['recent_avg']/4.0
    feature_columns = [
        'avg_difficulty','max_difficulty','var_difficulty','avg_pressure','max_pressure',
        'total_credits_norm','num_courses_norm','num_labs_norm','avg_level_norm','prior_gpa_norm','recent_avg_norm','workload_tolerance'
    ]
    return agg[feature_columns].fillna(0.0), agg['target_workload'].clip(0,1), feature_columns


def train_model2():
    print('='*70)
    print('MODEL 2: SEMESTER WORKLOAD ESTIMATION')
    print('='*70)
    X,y,feature_columns = create_training_features()
    X_train,X_test,y_train,y_test = train_test_split(X,y,test_size=0.20,random_state=42)
    baseline_pred = np.repeat(y_train.mean(), len(y_test))
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    gb=GradientBoostingRegressor(n_estimators=90, max_depth=3, learning_rate=0.055, random_state=42)
    rf=RandomForestRegressor(n_estimators=120, max_depth=10, min_samples_leaf=4, random_state=42, n_jobs=-1)
    results={}
    for name,model in [('Gradient Boosting',gb),('Random Forest',rf)]:
        model.fit(X_train,y_train)
        pred=np.clip(model.predict(X_test),0,1)
        results[name]={
            'model':model,
            'mae':float(mean_absolute_error(y_test,pred)),
            'rmse':float(np.sqrt(mean_squared_error(y_test,pred))),
            'r2':float(r2_score(y_test,pred)),
        }
        print(f"{name}: MAE={results[name]['mae']:.4f} RMSE={results[name]['rmse']:.4f} R2={results[name]['r2']:.4f}")
    best_name=min(results, key=lambda k: results[k]['mae'])
    with open(MODEL2_GB_FILE,'wb') as f: pickle.dump(gb,f)
    with open(MODEL2_NN_FILE,'wb') as f: pickle.dump(rf,f)
    with open(MODEL2_SCALER_FILE,'wb') as f: pickle.dump(None,f)
    info={
        'model_name':'Model 2: Semester Workload Estimation',
        'target':'semester workload index from observed difficulty + credits + labs',
        'best_model':best_name,
        'uses_scaler':False,
        'feature_columns':feature_columns,
        'baseline_mae':round(float(baseline_mae),4),
        'models':{k:{'mae':round(v['mae'],4),'rmse':round(v['rmse'],4),'r2':round(v['r2'],4)} for k,v in results.items()},
    }
    with open(INFO_FILE,'wb') as f: pickle.dump(info,f)
    (REPORTS_DIR/'model2_workload_metrics.json').write_text(json.dumps(info,indent=2), encoding='utf-8')
    print(f'[OK] best={best_name}, baseline MAE={baseline_mae:.4f}')
    return info

if __name__ == '__main__':
    train_model2()
