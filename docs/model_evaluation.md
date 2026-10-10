# Predictive models - evaluation

**Model performance measured on SYNTHETIC data; it does not establish real-world prediction accuracy.**

Validation is time-based: every origin trains only on months up to the origin; the last origin is the holdout (final 6 months). Model choice = lowest average of holdout WAPE and mean WAPE across origins, subject to a reasonableness band (12-month total within -15% / +25% of the trailing 12 months).

## 1-2, 4-5. Monthly series - holdout WAPE by method

| target                          |   Headcount x seasonal hours (model) |   Holt-Winters (damped) |   Mean of last 3 months |   Recent level x seasonal index |   SARIMAX |   Same month last year |   Seasonal naive |   XGBoost |
|:--------------------------------|-------------------------------------:|------------------------:|------------------------:|--------------------------------:|----------:|-----------------------:|-----------------:|----------:|
| billed_hours_collision          |                              nan     |                   0.092 |                 nan     |                           0.086 |     0.115 |                nan     |            0.073 |     0.09  |
| billed_hours_mechanical         |                              nan     |                   0.048 |                 nan     |                           0.077 |     0.086 |                nan     |            0.18  |     0.094 |
| parts_units_battery             |                              nan     |                   0.244 |                 nan     |                           0.245 |   nan     |                nan     |            0.274 |     0.154 |
| parts_units_clips               |                              nan     |                   0.109 |                 nan     |                           0.086 |   nan     |                nan     |            0.185 |     0.086 |
| parts_units_filter              |                              nan     |                   0.082 |                 nan     |                           0.088 |   nan     |                nan     |            0.147 |     0.067 |
| parts_units_oil                 |                              nan     |                   0.097 |                 nan     |                           0.091 |   nan     |                nan     |            0.185 |     0.082 |
| parts_units_pads                |                              nan     |                   0.245 |                 nan     |                           0.197 |   nan     |                nan     |            0.232 |     0.193 |
| parts_units_ppf                 |                              nan     |                   3.867 |                 nan     |                         nan     |   nan     |                nan     |            0.65  |     0.308 |
| parts_units_resin               |                              nan     |                   0.204 |                 nan     |                           0.334 |   nan     |                nan     |            0.197 |     0.291 |
| parts_units_rotors              |                              nan     |                   0.199 |                 nan     |                           0.255 |   nan     |                nan     |            0.16  |     0.143 |
| parts_units_tire                |                              nan     |                   0.119 |                 nan     |                           0.203 |   nan     |                nan     |            0.29  |     0.464 |
| parts_units_tpms                |                              nan     |                   0.252 |                 nan     |                           0.38  |   nan     |                nan     |            0.303 |     0.424 |
| parts_units_urethane            |                              nan     |                   0.19  |                 nan     |                           0.224 |   nan     |                nan     |            0.225 |     0.157 |
| parts_units_wipers              |                              nan     |                   0.233 |                 nan     |                           0.218 |   nan     |                nan     |            0.114 |     0.071 |
| revenue_collision               |                              nan     |                   0.144 |                 nan     |                           0.169 |     0.193 |                nan     |            0.12  |     0.218 |
| revenue_detailing               |                              nan     |                   0.22  |                 nan     |                           0.356 |     0.369 |                nan     |            0.445 |     0.37  |
| revenue_glass                   |                              nan     |                   0.179 |                 nan     |                           0.226 |     0.19  |                nan     |            0.23  |     0.207 |
| revenue_mechanical              |                              nan     |                   0.092 |                 nan     |                           0.119 |     0.108 |                nan     |            0.21  |     0.199 |
| revenue_other                   |                              nan     |                   0.637 |                 nan     |                           0.617 |     0.464 |                nan     |            0.547 |     0.39  |
| revenue_total                   |                              nan     |                   0.111 |                 nan     |                           0.099 |     0.126 |                nan     |            0.177 |     0.115 |
| ros_collision                   |                              nan     |                   0.108 |                 nan     |                           0.113 |     0.049 |                nan     |            0.159 |     0.134 |
| ros_detailing                   |                              nan     |                   0.23  |                 nan     |                           0.241 |     0.328 |                nan     |            0.434 |     0.349 |
| ros_glass                       |                              nan     |                   0.228 |                 nan     |                           0.25  |     0.186 |                nan     |            0.233 |     0.154 |
| ros_mechanical                  |                              nan     |                   0.052 |                 nan     |                           0.084 |     0.074 |                nan     |            0.171 |     0.133 |
| ros_other                       |                              nan     |                   0.431 |                 nan     |                           0.402 |     0.369 |                nan     |            0.463 |     0.297 |
| tech_available_hours_collision  |                                0.046 |                 nan     |                   0.065 |                         nan     |   nan     |                  0.059 |          nan     |   nan     |
| tech_available_hours_mechanical |                                0.025 |                 nan     |                   0.08  |                         nan     |   nan     |                  0.086 |          nan     |   nan     |

Chosen models:

- revenue_total: Holt-Winters (damped)
- revenue_collision: Holt-Winters (damped)
- revenue_mechanical: Holt-Winters (damped)
- revenue_detailing: Holt-Winters (damped)
- revenue_glass: Holt-Winters (damped)
- revenue_other: Seasonal naive
- ros_collision: SARIMAX
- ros_mechanical: Holt-Winters (damped)
- ros_detailing: Holt-Winters (damped)
- ros_glass: XGBoost
- ros_other: Recent level x seasonal index
- billed_hours_collision: Seasonal naive
- billed_hours_mechanical: Holt-Winters (damped)
- tech_available_hours_collision: Headcount x seasonal hours (model)
- tech_available_hours_mechanical: Headcount x seasonal hours (model)

## 3. Repair cycle-time prediction (collision, approval -> delivery days; test = approvals in 2026)

| model                            |   MAE_days |   RMSE_days |   within_3_days |    R2 |   n_test |
|:---------------------------------|-----------:|------------:|----------------:|------:|---------:|
| Baseline: median by service type |      6.506 |       9.053 |           0.366 | 0.279 |     1181 |
| Ridge regression                 |      6.078 |       7.937 |           0.329 | 0.446 |     1181 |
| XGBoost                          |      7.816 |       9.744 |           0.219 | 0.165 |     1181 |

Features are known at approval time only (estimate hours and value, special-order lines, luxury / aftermarket suppliers, ADAS, towed, payer, vehicle category, branch, month, open collision jobs at the branch). Supplements and backorders are NOT used as inputs (unknown at approval).

## 6. Expected cash collections (insurer & fleet receivables collected within 30 days)

| target               | method                                            |   WAPE |      MAE |     RMSE |   bias_pct |
|:---------------------|:--------------------------------------------------|-------:|---------:|---------:|-----------:|
| cash_collections_30d | Payment-lag curves by insurer (model)             |  0.029 |  14529.3 |  17227   |     -0.449 |
| cash_collections_30d | Average 30-day collection rate (baseline)         |  0.32  | 162909   | 166438   |    -31.973 |
| cash_collections_30d | Terms-based: everything due by 30 days (baseline) |  0.074 |  37458   |  45558.8 |      2.19  |

