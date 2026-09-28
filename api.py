"""Internal REST API. Run:  uvicorn api:app --port 8000
Try:  http://localhost:8000/api/part-risk?part_id=SN-2004
Docs: http://localhost:8000/docs
"""
import os, re, sqlite3
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

DB = Path(__file__).parent / "supply_risk.db"
API_KEY = os.getenv("SUPPLY_RISK_API_KEY")      # optional: set to require an X-API-Key header

app = FastAPI(title="Supply Chain Part Risk API")
# The browser extension calls this from other origins (supplier emails, procurement portals)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

COLOURS = {"High": "#D62728", "Medium": "#FF9F1C", "Low": "#2CA02C"}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def check_key(key):
    if API_KEY and key != API_KEY:
        raise HTTPException(401, "Invalid or missing API key")


QUERY = """
SELECT r.*, p.description, p.category, s.name AS supplier
FROM part_risk r
JOIN parts p ON p.part_id = r.part_id
LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
WHERE r.run_date = (SELECT MAX(run_date) FROM part_risk)
"""


def shape(r):
    return {
        "part_id": r["part_id"],
        "description": r["description"],
        "supplier": r["supplier"],
        "shortage_probability": r["shortage_prob"],
        "risk_band": r["risk_band"],
        "color": COLOURS[r["risk_band"]],
        "recommended_reorder_date": r["reorder_by"],
        "reorder_overdue": r["reorder_by"] <= r["run_date"],
        "days_of_cover": r["days_of_cover"],
        "estimated_lead_time_days": {"typical": r["lead_p50"], "worst_case_p90": r["lead_p90"]},
        "expected_loss": r["expected_loss"],
        "model_run_date": r["run_date"],
    }


@app.get("/api/part-risk")
def part_risk(part_id: str = Query(..., min_length=2, max_length=40),
              x_api_key: str | None = Header(default=None)):
    check_key(x_api_key)
    pid = re.sub(r"[\s_]", "-", part_id.strip().upper())      # tolerate "sn 2004" / "SN_2004"
    con = db()
    row = con.execute(QUERY + " AND r.part_id = ?", (pid,)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, f"No risk score for part '{pid}'")
    return shape(row)


@app.get("/api/parts-at-risk")
def parts_at_risk(min_probability: float = 0.12, x_api_key: str | None = Header(default=None)):
    check_key(x_api_key)
    con = db()
    rows = con.execute(QUERY + " AND r.shortage_prob >= ? ORDER BY r.shortage_prob DESC",
                       (min_probability,)).fetchall()
    con.close()
    return [shape(r) for r in rows]


@app.get("/api/health")
def health():
    con = db()
    d = con.execute("SELECT MAX(run_date) FROM part_risk").fetchone()[0]
    con.close()
    return {"status": "ok", "last_model_run": d}
