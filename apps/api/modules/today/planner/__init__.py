"""
The R2 study planner (F-13 PRD section 6.F, ERD "Planner"): pure functions, no Django, no clock, no database.

capacity    how much reading the days before the deadline can hold, and how much reading is left
milestones  dates for finish reading, first revision, mock and exam week
health      on track, slightly behind or at risk, from the shortfall
options     what the student can choose when the plan does not fit
replan      when to re-plan, what moved, and the whole computation (`build_plan`)

Services (W8) load the data, call these and store the result. Every tunable number is in `constants.py`.
"""
