# ML Strength/Weakness Upgrade

This version upgrades the recommendation engine so it is no longer a flat rule-like course picker.

## What changed

1. **Synthetic data generator rebuilt**
   - Generates pre-attempt features only: prior GPA, recent grades, prerequisite performance, area strength, subject strength, course pressure, and term load.
   - Adds area-specific student strengths and weaknesses: math, physics, computing, circuits, signals, communication, systems/control, lab/project, humanities/business.
   - Supports A+ as 4.3 quality points while cumulative GPA remains capped at 4.0.

2. **Model 4: Course success probability**
   - Predicts probability of C+ or above using student-level train/test split.
   - Uses strength/weakness features rather than only global GPA.
   - Includes course pressure and prerequisite coverage.

3. **Model 5: Expected grade points**
   - Predicts expected AUB quality points for each candidate course.
   - This is essential for GPA-target planning because pass probability alone cannot tell whether the course helps raise GPA.

4. **Recommendation logic improved**
   - Rules only filter invalid/repeated courses.
   - ML estimates success probability and expected grade.
   - The ranker uses target GPA feasibility, expected grade, difficulty, workload, and student strengths/weaknesses.
   - Electives can come from outside the major when the student is weak in a major area and wants GPA protection.
   - Major courses are still prioritized for degree progress, but weaker major subareas are handled more cautiously.

## Important limitation

The model is trained on synthetic outcomes, not real AUB student records. It is a rigorous ML prototype using real catalog-like structure and synthetic student performance. It should not be presented as proven on real AUB advising data.
