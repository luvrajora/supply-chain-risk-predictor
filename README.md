# Supply Chain Bottleneck Predictor: Dashboard Data Layer
**Live demo:** https://supply-chain-riskpredictor.netlify.app

## Run it
```bash
pip install numpy pandas
python build_dashboard_data.py            # generate data, score risk, create views, export CSVs
python build_dashboard_data.py --keep-data  # re-score existing DB only (what the nightly job does)
```
Outputs: `supply_risk.db` (SQLite) and `dashboard_exports/*.csv`.

## How the model works
| Step | Method |
|---|---|
| Component demand | Recursive SQL CTE explodes the multi-level BOM (vehicle -> sub-assembly -> component) against the production plan |
| Lead-time variance | Empirical distribution of actual lead days (received - ordered) per part from PO history |
| Shortage probability | For each historical lead time L: P(Normal demand over L days > on_hand + on_order); averaged across samples |
| Reorder-by date | today + (days of cover - P90 lead time); floored at today (= overdue) |
| Expected loss | Expected gap days (lead time beyond cover) x stoppage cost/day of every line that consumes the part |
| Supplier score | 0-100: 60% on-time rate (1-day grace) + 40% delay consistency |

Risk bands: High >= 35%, Medium >= 12% (tunable in `risk_model.py`).

**Assumptions to review:** loss assumes a missing part halts every dependent line for the full gap; in-transit stock is counted as available; demand is treated as normally distributed. Each is a good candidate to refine with real data.

## Dashboard tabs

Connect Power BI / Tableau to the CSVs (or to `supply_risk.db` via SQLite ODBC and the `v_*` views).

| Panel | Source | Visuals |
|---|---|---|
| **Parts at Risk** | `parts_at_risk` | Table sorted by `shortage_prob`, colour by `risk_band`; KPI cards: # High-risk parts, # reorders overdue; scatter of days_of_cover vs lead_p90 |
| **Supplier Reliability** | `supplier_reliability`, `lead_time_history` | Bar of `reliability_score`; box plot / histogram of `delay_days` per supplier; map by `country` |
| **Financial Impact** | `financial_impact` | Stacked bar of `expected_stoppage_cost` by line and part; card for total probability-weighted exposure |
| **BOM Drill-down** | `bom_flat` | Tree / matrix from finished good to component |
| **Trend** | `risk_trend` | Line of `shortage_prob` by date (fills in as the nightly job runs) |

Power BI measures (DAX):
```
Total Exposure = SUM(financial_impact[prob_weighted_daily_exposure])
High Risk Parts = CALCULATE(DISTINCTCOUNT(parts_at_risk[part_id]), parts_at_risk[risk_band] = "High")
Overdue Reorders = SUM(parts_at_risk[reorder_overdue])
```
Conditional colours: High `#D62728`, Medium `#FF9F1C`, Low `#2CA02C` (reuse the same palette in the browser extension).

## Files
- `schema.sql`: ERP-style tables plus model output tables
- `generate_data.py`: synthetic data (swap for an SAP/Oracle extractor later)
- `risk_model.py`: BOM explosion, lead-time variance, shortage probability, supplier scoring
- `views.sql`: dashboard views
- `build_dashboard_data.py`: orchestrator and CSV export

## Next
The `part_risk` table is exactly what the `/api/part-risk?part_id=` endpoint will read, so the API and nightly scheduler come next.
