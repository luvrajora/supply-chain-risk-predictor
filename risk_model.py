"""Nightly risk model.

For every component:
  1. Explode the multi-level BOM (recursive CTE) into daily component demand.
  2. Build an empirical lead-time distribution from historical PO receipts.
  3. P(shortage) = P(demand during replenishment lead time > on_hand + on_order),
     averaged over the empirical lead-time samples (demand ~ Normal per lead time).
  4. Derive recommended reorder date and expected financial loss.
Also scores each supplier's reliability.
"""
import sqlite3, sys
from datetime import date, timedelta
from math import erf, sqrt
from pathlib import Path
import numpy as np
import pandas as pd

DB = Path(__file__).parent / "supply_risk.db"
HIGH, MEDIUM = 0.35, 0.12          # shortage-probability thresholds for risk bands


def phi(z):                        # standard normal CDF
    return 0.5 * (1 + erf(z / sqrt(2)))


EXPLODE_CTE = """
WITH RECURSIVE ex(root, part, qty) AS (
    SELECT part_id, part_id, 1.0 FROM parts WHERE part_type = 'FINISHED'
    UNION ALL
    SELECT ex.root, b.child_part_id, ex.qty * b.qty_per
    FROM ex JOIN bom b ON b.parent_part_id = ex.part
)
"""


def component_demand(con, today):
    """Return per-component daily demand series (mean, std) and dependent-line cost per day."""
    df = pd.read_sql(EXPLODE_CTE + """
        SELECT pp.plan_date, ex.part AS part_id, ex.root, SUM(ex.qty * pp.units) AS demand
        FROM ex JOIN production_plan pp ON pp.part_id = ex.root
        JOIN parts p ON p.part_id = ex.part AND p.supplier_id IS NOT NULL
        WHERE pp.plan_date >= ? GROUP BY pp.plan_date, ex.part, ex.root""", con, params=(today.isoformat(),))
    daily = df.groupby(["part_id", "plan_date"]).demand.sum().reset_index()
    stats = daily.groupby("part_id").demand.agg(mu="mean", sigma="std").reset_index()
    lines = pd.read_sql("SELECT part_id AS root, stoppage_cost_per_hour * hours_per_day AS cost_day FROM line_costs", con)
    dep = df[["part_id", "root"]].drop_duplicates().merge(lines, on="root")
    stop_cost = dep.groupby("part_id").cost_day.sum().rename("stop_cost_day").reset_index()
    return stats.merge(stop_cost, on="part_id")


def lead_times(con):
    po = pd.read_sql("SELECT part_id, supplier_id, order_date, promised_date, received_date FROM purchase_orders",
                     con, parse_dates=["order_date", "promised_date", "received_date"])
    po["lead_days"] = (po.received_date - po.order_date).dt.days
    po["delay_days"] = (po.received_date - po.promised_date).dt.days
    return po


def score_suppliers(po, run_date):
    rows = []
    for sid, g in po.groupby("supplier_id"):
        on_time = (g.delay_days <= 1).mean()          # 1-day grace
        mean_d, std_d = g.delay_days.mean(), g.delay_days.std()
        score = 100 * (0.6 * on_time + 0.4 * max(0.0, 1 - std_d / 12))
        rows.append((run_date, sid, round(on_time, 3), round(mean_d, 2), round(std_d, 2), round(score, 1), len(g)))
    return rows


def run(run_date=None):
    run_date = run_date or date.today()
    con = sqlite3.connect(DB)
    demand = component_demand(con, run_date).set_index("part_id")
    po = lead_times(con)
    inv = pd.read_sql("""SELECT i.part_id, i.on_hand, i.on_order FROM inventory_snapshots i
        JOIN (SELECT part_id, MAX(snapshot_date) d FROM inventory_snapshots GROUP BY part_id) m
        ON m.part_id = i.part_id AND m.d = i.snapshot_date""", con).set_index("part_id")

    rows = []
    for pid, d in demand.iterrows():
        if pid not in inv.index:
            continue
        samples = po[po.part_id == pid].lead_days.to_numpy()
        if len(samples) < 5:                                   # thin history: fall back to wide prior
            samples = np.array([30] * 5)
        avail = inv.loc[pid, "on_hand"] + inv.loc[pid, "on_order"]
        mu, sigma = d.mu, max(d.sigma, 1e-6)
        cover = avail / mu

        # shortage prob: averaged over historical lead-time samples
        probs = [1 - phi((avail - mu * L) / (sigma * sqrt(L))) for L in samples]
        p_short = float(np.mean(probs))
        gap_days = float(np.mean(np.maximum(0, samples - cover)))
        p50, p90 = np.percentile(samples, [50, 90])
        reorder_by = run_date + timedelta(days=int(max(0, cover - p90)))
        loss = gap_days * d.stop_cost_day
        band = "High" if p_short >= HIGH else "Medium" if p_short >= MEDIUM else "Low"
        rows.append((run_date.isoformat(), pid, round(p_short, 4), round(cover, 1), float(p50), float(p90),
                     reorder_by.isoformat(), round(gap_days, 2), round(loss, 0), band))

    con.execute("DELETE FROM part_risk WHERE run_date = ?", (run_date.isoformat(),))
    con.executemany("INSERT INTO part_risk VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    con.execute("DELETE FROM supplier_scores WHERE run_date = ?", (run_date.isoformat(),))
    con.executemany("INSERT INTO supplier_scores VALUES (?,?,?,?,?,?,?)",
                    score_suppliers(po, run_date.isoformat()))
    con.commit()
    con.close()
    print(f"[{run_date}] scored {len(rows)} parts")


if __name__ == "__main__":
    run()
