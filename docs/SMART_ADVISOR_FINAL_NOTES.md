# Smart Advisor Final Notes

The AI Advisor is intentionally a grounded explanation layer, not the core ML model.

## What it does
- Reads the logged-in student's saved profile, completed courses, grades, GPA, and target GPA.
- Summarizes the current recommendation engine output.
- Explains GPA feasibility flags and why a target may be unrealistic.
- Lists failed/repair courses and weak/strong academic areas.
- Checks specific course codes against the loaded catalogue and prerequisite logic.

## What it does not do
- It does not invent course names from old datasets.
- It does not claim official AUB validation on real student records.
- It does not replace the five ML models. The five models remain the core ML contribution.

## Final positioning
Academic rules validate eligibility and prerequisites. ML models predict difficulty, workload, risk, success probability, and expected grade. The advisor translates those outputs into student-friendly explanations.
