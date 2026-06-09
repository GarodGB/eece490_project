# ML Rigor Upgrade

This version upgrades the adjusted AcademicPath project so the ML part is more defensible for Option A.

## Main changes

1. **Synthetic data was rebuilt** with pre-attempt features such as prior GPA, recent grade average, prerequisite average, completed credits before the course, and term credit load.
2. **Hidden synthetic variables are not used as deployment features.** Latent ability is kept only for simulation/audit; the models use observable academic-history and course features.
3. **Model 3 now predicts future academic risk** from historical performance, instead of simply learning a same-row rule label.
4. **Model 5 was added** to predict expected AUB grade points out of 4.0. This is needed because pass/fail probability alone is not enough for GPA-raising recommendations.
5. **Recommendations now use expected grade + success probability + expected difficulty + degree-role constraints.** Rules filter invalid courses; ML ranks eligible courses.
6. **Student UI now exposes expected grade and expected difficulty**, not only a vague fit score.

## Models

- Model 1: Personalized course difficulty regression
- Model 2: Semester workload regression
- Model 3: Future academic risk classification
- Model 4: Course success probability classification
- Model 5: Expected AUB grade-points regression

## Important limitation

The data is still synthetic. The project should be presented as an ML-assisted academic planning prototype, not as a validated AUB advising system trained on real student records.
