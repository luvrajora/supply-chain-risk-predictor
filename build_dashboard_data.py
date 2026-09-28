"""One command: (re)generate data -> run risk model -> create views -> export CSVs for Tableau / Power BI."""
import sqlite3, sys
from pathlib import Path
import pandas as pd
import generate_data, risk_model

HERE = Path(__file__).parent
OUT = HERE / "dashboard_exports"
VIEWS = ["v_parts_at_risk", "v_supplier_reliability", "v_financial_impact",
         "v_lead_time_history", "v_bom_flat", "v_risk_trend"]


def main(regenerate=True):
    if regenerate or not (HERE / "supply_risk.db").exists():
        generate_data.main()
    risk_model.run()
    con = sqlite3.connect(HERE / "supply_risk.db")
    con.executescript((HERE / "views.sql").read_text())
    OUT.mkdir(exist_ok=True)
    for v in VIEWS:
        df = pd.read_sql(f"SELECT * FROM {v}", con)
        df.to_csv(OUT / f"{v[2:]}.csv", index=False)
        print(f"  exported {v[2:]}.csv ({len(df)} rows)")
    con.close()


if __name__ == "__main__":
    main(regenerate="--keep-data" not in sys.argv)
