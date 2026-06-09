# Option A Final Alignment Notes

## Project type
Option A: Application-Oriented ML System.

## Real-world problem
Students need to plan semesters that satisfy degree requirements while avoiding overload and protecting GPA. Manual planning is difficult because the student must consider prerequisites, failed/weak courses, major progress, elective choices, workload, and GPA targets at the same time.

## Decision automated/augmented
The system augments the decision of which courses a student should take next semester.

## Non-AI baseline
Rules/heuristics are used as a baseline and eligibility layer:

- prerequisite completion;
- already-passed course exclusion;
- failed-course repair eligibility;
- credit-load caps;
- major/support/elective role;
- AUB GPA cap logic.

## ML approach
Five ML models predict personalized difficulty, workload, academic risk, course success, and expected grade. The recommender ranks valid candidates using these predictions plus student strengths/weaknesses and GPA feasibility.

## Why ML is appropriate beyond accuracy
ML provides personalized scoring that rules alone cannot provide: two students can have the same major requirements but different strengths, weak areas, recent performance, and workload tolerance. The same course can be a good fit for one student and risky for another.

## Error analysis and limitations
The main limitation is that outcomes are synthetic because real student records were unavailable. The project therefore demonstrates method, architecture, and prototype behavior, not a validated institutional deployment.

## Responsible ML
- Explainability: each recommendation includes difficulty, expected grade, success probability, role, and reason.
- Privacy: prototype uses local SQLite; production would need stronger security.
- Robustness: target GPA feasibility warnings appear when goals are unrealistic.
- Bias/fairness: synthetic data assumptions may bias results and must be disclosed.

## Production thinking
The project includes Flask UI/API, SQLite persistence, separated services, reproducible training scripts, Dockerfile, and docker-compose support.
