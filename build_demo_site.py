"""Builds demo-site/index.html (static, for Netlify) from the latest dashboard exports."""
import json
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
parts = pd.read_csv(HERE / "dashboard_exports/parts_at_risk.csv").sort_values("shortage_prob", ascending=False)
sups = pd.read_csv(HERE / "dashboard_exports/supplier_reliability.csv").sort_values("reliability_score")
fin = pd.read_csv(HERE / "dashboard_exports/financial_impact.csv").groupby("line_name").expected_stoppage_cost.sum().reset_index()

data = {
    "run_date": str(parts.run_date.iloc[0]),
    "parts": parts[["part_id", "description", "supplier", "shortage_prob", "risk_band", "days_of_cover",
                    "lead_p50", "lead_p90", "reorder_by", "expected_loss"]].round(3).to_dict("records"),
    "suppliers": sups[["name", "country", "on_time_rate", "mean_delay_days", "reliability_score"]].to_dict("records"),
    "lines": fin.round(0).to_dict("records"),
}
html = (HERE / "demo-site/template.html").read_text().replace("__DATA__", json.dumps(data))
(HERE / "demo-site/index.html").write_text(html)
print("demo-site/index.html written")
