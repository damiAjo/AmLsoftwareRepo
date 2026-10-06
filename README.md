# MapleFreight Delivery Delay Prediction & Slack Alerts

Predicts which in-transit shipments will be delivered late and alerts dispatch in Slack while there is still time to re-route or warn the customer.

## Problem

MapleFreight Logistics moves about 8,000 shipments a week across Ontario, Quebec and the Prairies, under contracts with on-time guarantees. On-time performance has dropped from 94% to 88% this year, and delays are only discovered after the delivery window has passed, usually when the customer calls. By then the service credits and expedited re-delivery costs are already incurred.

This project builds an end-to-end system that:

1. identifies the main drivers of late delivery,
2. predicts whether a shipment will be late using only information available at dispatch,
3. posts a ranked alert of high-risk shipments to the `#dispatch-alerts` Slack channel, and
4. recommends operational changes to improve on-time performance.

## Dataset

`maplefreight_delivery_delay_dataset.csv` (included in this repo): 6,035 shipments, 23 columns covering route, carrier, service level, goods type, driver, vehicle, weather, traffic and carrier history. The target is `delivered_late` (1 = missed the promised window), with about 21% late.

The raw export needed cleaning:

- 35 duplicate shipments (exact copies and copies differing only in `service_level` casing), leaving 6,000 shipments
- inconsistent casing in `service_level` ("standard" vs "Standard")
- 40 weights recorded in grams instead of kg
- missing values in fuel cost, driver experience, weather and traffic index
- 465 shipments with identical origin and destination cities but normal long-haul distances (likely mislabelled cities; kept)

`actual_transit_hours` is recorded on delivery, so it is not available at prediction time. It was excluded from modelling as target leakage.

## Repository contents

├── MapleFreight_Delivery_Delay_Prediction.ipynb    
├── maplefreight_delivery_delay_dataset.csv                 
├── screenshots/slack_alert.png                             
├── requirements.txt
├── .env.example                                            
├── .gitignore                                              
└── README.md


 **Run the notebook**

   Open the notebook in Jupyter or VS Code, select the `.venv` kernel, and choose **Restart & Run All**. The final cell posts the alert to Slack.

## Approach

| Step | What was done |
|---|---|
| Cleaning | Standardized casing, removed duplicates, fixed gram/kg unit errors, filled missing weather as "Unknown" |
| EDA | Late rate by every categorical feature, numeric distributions by outcome, correlations, leakage check |
| Feature engineering | Dispatch-time flags: severe weather, long haul (>800 km), late pickup, new driver (<2 yrs), winter, carrier with 3+ recent lates |
| Preparation | Stratified 80/20 split; imputation, scaling and one-hot encoding inside a scikit-learn pipeline fitted on training data only |
| Modelling | Dummy → Logistic Regression baseline → Random Forest → XGBoost, all class-weighted for the 21% minority class; compared with 5-fold stratified CV |
| Evaluation | Precision, recall, F1, ROC-AUC, PR-AUC, confusion matrices; threshold chosen on out-of-fold predictions |
| Explainability | Coefficients and SHAP values grouped by original feature; per-shipment top risk factors |
| Alerting | Ranked summary of high-risk shipments posted to Slack via an Incoming Webhook |

## Key findings

**Drivers of late delivery**

- **Weather:** storm forecasts → 47% late, snow → 34%, clear → 14%.
- **Carrier:** Contract Owner-Ops are late 36% of the time vs 13% for the in-house MapleFreight Fleet. Carriers with more late deliveries in the past 30 days keep being late.
- **Route design:** late rate rises from 12% at 0 stops to 29% at 5; long-haul shipments are late 31% of the time.
- **Pickup punctuality:** late pickups lead to late delivery 23% of the time vs 15% for on-time pickups.
- **Service level:** Economy 27% late vs Express 15%.
- **Customer priority tier has no effect:** Gold, Silver and Bronze are all ~21% late, so priority accounts get no better service.

**Model results**

Cross-validated on the training set (5-fold):

| Model | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---|---|---|---|---|
| Dummy (all on time) | 0.000 | 0.000 | 0.000 | 0.500 | 0.206 |
| **Logistic Regression (baseline)** | 0.417 | 0.723 | 0.529 | 0.809 | **0.561** |
| Random Forest | 0.582 | 0.411 | 0.480 | 0.795 | 0.531 |
| XGBoost | 0.433 | 0.670 | 0.526 | 0.802 | 0.548 |

The dummy model reaches 79% accuracy while catching zero late shipments, which is why accuracy is not used. The class-weighted logistic regression baseline had the best cross-validated PR-AUC and was kept as the final model. Its strong performance suggests lateness risk is largely additive across factors, and it is also the easiest model to explain to dispatch.

Test set (1,200 shipments, 247 late), baseline vs final:

| | Precision | Recall | F1 | Alerts/week* |
|---|---|---|---|---|
| Baseline LR @ 0.50 | 0.446 | 0.753 | 0.560 | ~2,780 |
| **Final LR @ 0.55** | **0.482** | **0.709** | **0.574** | **~2,420** |

\*Flag rate × 8,000 weekly shipments. Test ROC-AUC 0.833, PR-AUC 0.607. Confusion matrices are in the notebook.

## Alert threshold: 0.55

The threshold was chosen on **out-of-fold predictions from the training set**, never the test set, by balancing three things:

- **Cost of a missed delay:** assumed $150 (service credit + expedited re-delivery).
- **Cost of an alert:** assumed $40 (about 20 minutes of dispatcher time or a customer call). Every alert carries this cost, true or false.
- **Alert volume:** at 0.5 the model flags ~35% of shipments, roughly 2,800 alerts a week, more than dispatch can realistically act on.

These assumptions the cost-optimal threshold is **0.55**, and the F1-optimal threshold is also **0.55**. Two independent criteria agreeing makes the choice robust. Compared with 0.5, it cuts about 360 alerts a week (~13% less workload) and improves precision and F1, at the cost of 11 more missed late shipments out of 247 in the test set.

The choice is sensitive to the cost ratio: if checking an alert cost $25 instead of $40, the cost-optimal threshold would fall to about 0.4. Because volume is still high at 0.55, the Slack message ranks shipments by risk and shows the top five, so dispatch works from the most urgent cases down.

## Slack alert

The notebook sends one summary message per batch: how many shipments are at risk, then the top five with shipment ID, destination, carrier, risk score and the main reasons (e.g. "severe weather, carrier"). The reasons tell dispatch what to do: a weather-driven risk suggests warning the customer, a carrier-driven risk suggests re-assigning the load.

![1791304610720](image/README(1)/1791304610720.jpg)

## Recommendations

1. **Tighten carrier management:** route high-risk loads to the in-house fleet, score carriers on recent lateness, and add on-time SLAs to owner-operator contracts.
2. **Weather-triggered protocol:** when severe weather is forecast, notify customers or widen the promised window before pickup instead of paying credits afterwards.
3. **Enforce pickup punctuality** and re-score shipments at pickup.
4. **Redesign high-risk routes:** cap stops on long-haul and Economy routes and review whether their promised transit times are realistic.
5. **Protect Gold accounts** in alert triage and fleet assignment.
6. **Operate alerts deliberately:** consider two tiers (immediate above ~0.80, daily digest for 0.55–0.80), log alert outcomes, and retrain monthly.
7. **Fix the data export** at the source (duplicates, units, casing, city labels).

Illustratively, if dispatch prevents 30% of the late shipments the model flags, the late rate would fall by about 4.4 percentage points (the 30% is an assumption to be measured from alert outcomes).

## Limitations

- The dollar costs behind the threshold are assumptions, not MapleFreight figures.
- The test set stands in for live in-transit shipments; in production the model would score shipments on a schedule.
- `fuel_cost_cad` appears noisy and some city labels are unreliable, which limits route-level insights.

## AI usage

**Tools used:** Claude (Anthropic) for planning the workflow, debugging environment issues, and drafting this README, e.g. GitHub Copilot in VS Code -->



**A case where the AI output was wrong:** in the cleaning step, Claude suggested applying `.str.title()` to every categorical column to fix inconsistent casing. Only `service_level` had a casing problem, and title-casing everything silently corrupted valid names: "QuebecExpress" became "Quebecexpress", "MapleFreight Fleet" became "Maplefreight Fleet", and "Toronto ON" became "Toronto On". The model still trained without errors, so nothing flagged it. 