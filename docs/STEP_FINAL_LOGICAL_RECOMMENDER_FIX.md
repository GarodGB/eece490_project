# Final logical recommender fix

This update fixes the main recommendation problems observed during UI testing.

## What was wrong

1. EECE courses were being misclassified as electives for ECE/CCE/CSE students because the raw subject code is EECE while the student program is ECE/CCE/CSE.
2. Because of that role mismatch, the recommender sometimes selected only one support course instead of building a realistic semester.
3. The UI did not clearly flag when a target GPA was not reachable.
4. Completed-course cards showed `--` for difficulty unless the student manually rated difficulty.

## What was fixed

- EECE courses are now treated as major-path courses for ECE, CCE, and CSE students.
- Course role logic was corrected so major relationship overrides raw course type.
- A final fill pass was added so the system builds a real semester plan when valid unlocked courses exist, instead of returning a one-course plan.
- Target GPA feasibility now includes a clear flag when the target cannot be reached with the current safest plan.
- Cumulative GPA feasibility now warns if a target is mathematically impossible in one semester even with a 4.0-capped semester GPA.
- Completed-course cards now show predicted course difficulty from the catalogue/ML cache, while keeping the student's optional rating separate.

## ML design principle

Rules are only used to validate eligibility and enforce academic constraints. ML predictions are used to score and rank valid course options using difficulty, expected grade, success probability, workload tolerance, risk, course area, and the student strength/weakness profile.
