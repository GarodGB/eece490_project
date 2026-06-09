# AUB A+ Grade Scale Fix

This update implements the requested AUB-style grading behavior:

- `A+` is available as a course grade.
- `A+` stores `4.3` quality points for the individual course grade.
- The displayed and stored cumulative GPA is capped at `4.0`.
- GPA simulations and GPA-target calculations report capped GPA logic.
- Synthetic data generation can now produce `A+` course outcomes while final student GPA remains capped at `4.0`.
- Expected course grade outputs may reach `4.3`; cumulative/semester GPA remains capped at `4.0`.

After extracting this version, rerun:

```powershell
.\.venv\Scripts\python.exe scripts\generate_synthetic_data.py
.\.venv\Scripts\python.exe ml\train_all_models.py
.\.venv\Scripts\python.exe app.py
```

Or use the normal setup flow from the README.
