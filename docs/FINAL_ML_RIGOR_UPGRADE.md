# Final ML Rigor Upgrade

This version improves the ML recommendation engine without using real student grades. It adds course-topic profiling from course titles/descriptions, student strength/weakness profiling from completed courses only, expected grade + success + difficulty driven ranking, and GPA feasibility checks.

Rules are used only as academic constraints: passed courses are not repeated, failed courses may be retaken, and courses must fit the degree plan. ML is used to rank the valid choices and estimate fit, expected grade, success probability, and difficulty.

Limitation: student outcomes remain synthetic, so results demonstrate a rigorous prototype rather than validated real AUB performance.
