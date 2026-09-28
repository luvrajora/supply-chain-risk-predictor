"""Generate realistic synthetic automotive supply-chain data into SQLite.
Replace this with an ERP extractor (see README) for real data."""
import sqlite3, random
from datetime import date, timedelta
from pathlib import Path
import numpy as np

DB = Path(__file__).parent / "supply_risk.db"
TODAY = date.today()
rng = np.random.default_rng(42)
random.seed(42)

# name, country, tier, mean delay (days), delay std, chance of a big disruption
SUPPLIERS = [
    ("S01", "Yazaki Harness Co",   "Mexico",   1, 0.5, 1.5, 0.02),
    ("S02", "Bosch Sensortec",     "Germany",  1, 1.0, 2.0, 0.03),
    ("S03", "Delphi Connectors",   "Poland",   1, 2.5, 4.0, 0.08),
    ("S04", "Shenzhen Micro Elec", "China",    1, 4.0, 7.0, 0.15),
    ("S05", "Kolkata Cable Works", "India",    1, 3.0, 5.0, 0.10),
    ("S06", "Nagoya Precision",    "Japan",    1, 0.5, 1.0, 0.01),
]

# part_id, description, category, unit_cost, supplier, quoted lead days, daily use per vehicle set
COMPONENTS = [
    ("WH-1001", "Main wiring harness A",    "harness",   84.0, "S01", 14),
    ("WH-1002", "Door wiring harness",      "harness",   32.5, "S01", 12),
    ("WH-1003", "Engine bay harness",       "harness",   61.0, "S05", 18),
    ("SN-2001", "Wheel speed sensor",       "sensor",    14.2, "S02", 21),
    ("SN-2002", "Oxygen sensor",            "sensor",    27.9, "S02", 25),
    ("SN-2003", "Tire pressure sensor",     "sensor",     9.8, "S04", 30),
    ("SN-2004", "Radar module",             "sensor",   118.0, "S04", 45),
    ("CN-3001", "12-pin connector",         "connector",  1.6, "S03", 10),
    ("CN-3002", "Sealed ECU connector",     "connector",  4.4, "S03", 14),
    ("CN-3003", "Battery terminal",         "connector",  2.9, "S05", 12),
    ("EL-4001", "Body control module",      "electronic",96.0, "S04", 40),
    ("EL-4002", "Fuse box assembly",        "electronic",22.0, "S06", 16),
    ("EL-4003", "Relay 40A",                "electronic", 3.1, "S06", 10),
]

# Finished goods: id, name, units/day, stoppage cost per hour
FINISHED = [
    ("VH-A", "Sedan platform",   420, 38000),
    ("VH-B", "SUV platform",     310, 52000),
    ("VH-C", "EV platform",      180, 71000),
]

# BOM edges (parent, child, qty) — sub-assemblies create multi-level explosion
SUBASSY = [("SA-100", "Cockpit electronics module", 0.0)]
BOM = [
    ("VH-A", "WH-1001", 1), ("VH-A", "WH-1002", 4), ("VH-A", "SN-2001", 4), ("VH-A", "SN-2002", 1),
    ("VH-A", "SA-100", 1),  ("VH-A", "WH-1003", 1), ("VH-A", "CN-3003", 2),
    ("VH-B", "WH-1001", 1), ("VH-B", "WH-1002", 4), ("VH-B", "SN-2001", 4), ("VH-B", "SN-2003", 4),
    ("VH-B", "SN-2004", 1), ("VH-B", "SA-100", 1),  ("VH-B", "WH-1003", 1),
    ("VH-C", "WH-1001", 1), ("VH-C", "WH-1002", 4), ("VH-C", "SN-2001", 4), ("VH-C", "SN-2004", 2),
    ("VH-C", "SN-2003", 4), ("VH-C", "EL-4001", 1), ("VH-C", "SA-100", 1), ("VH-C", "CN-3003", 4),
    # sub-assembly SA-100 explodes into electronics and connectors
    ("SA-100", "EL-4001", 1), ("SA-100", "EL-4002", 1), ("SA-100", "EL-4003", 6),
    ("SA-100", "CN-3001", 8), ("SA-100", "CN-3002", 2),
]


def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript((Path(__file__).parent / "schema.sql").read_text())
    cur = con.cursor()

    cur.executemany("INSERT INTO suppliers VALUES (?,?,?,?)", [(s[0], s[1], s[2], s[3]) for s in SUPPLIERS])
    sup = {s[0]: s for s in SUPPLIERS}

    for pid, desc, cat, cost, sid, lead in COMPONENTS:
        cur.execute("INSERT INTO parts VALUES (?,?,?,?,?,?,?)", (pid, desc, cat, "COMPONENT", cost, sid, lead))
    cur.execute("INSERT INTO parts VALUES (?,?,?,?,?,?,?)",
                ("SA-100", "Cockpit electronics module", "subassembly", "COMPONENT", 0, None, 0))
    for pid, name, units, cost_hr in FINISHED:
        cur.execute("INSERT INTO parts VALUES (?,?,?,?,?,?,?)", (pid, name, "vehicle", "FINISHED", 0, None, 0))
        cur.execute("INSERT INTO line_costs VALUES (?,?,?)", (pid, cost_hr, 16))
    cur.executemany("INSERT INTO bom VALUES (?,?,?)", BOM)

    # Production plan: next 60 days, weekdays, with mild noise
    for d in range(-30, 61):
        day = TODAY + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        for pid, _, units, _ in FINISHED:
            cur.execute("INSERT INTO production_plan VALUES (?,?,?)",
                        (day.isoformat(), pid, int(rng.normal(units, units * 0.07))))

    # Purchase order history (~2 years) with supplier-specific delay behaviour
    po_id = 1
    for pid, _, _, _, sid, lead in COMPONENTS:
        _, _, _, _, mu, sd, p_dis = sup[sid]
        for _ in range(60):
            order = TODAY - timedelta(days=int(rng.integers(20, 730)))
            delay = rng.normal(mu, sd)
            if rng.random() < p_dis:
                delay += rng.uniform(10, 30)        # disruption event
            delay = int(round(max(-3, delay)))
            promised = order + timedelta(days=lead)
            received = promised + timedelta(days=delay)
            if received > TODAY:
                continue
            cur.execute("INSERT INTO purchase_orders VALUES (?,?,?,?,?,?,?)",
                        (po_id, pid, sid, order.isoformat(), promised.isoformat(),
                         received.isoformat(), int(rng.integers(500, 5000))))
            po_id += 1

    # Inventory snapshots: last 30 days. Stock levels are deliberately mixed
    # so some parts are safe, some tight, some critical.
    cover_targets = {"WH-1001": 20, "WH-1002": 26, "WH-1003": 11, "SN-2001": 30, "SN-2002": 34,
                     "SN-2003": 38, "SN-2004": 33, "CN-3001": 24, "CN-3002": 12, "CN-3003": 19,
                     "EL-4001": 44, "EL-4002": 28, "EL-4003": 33}
    con.commit()
    daily = dict(cur.execute("""
        WITH RECURSIVE ex(root, part, qty) AS (
            SELECT part_id, part_id, 1.0 FROM parts WHERE part_type='FINISHED'
            UNION ALL SELECT ex.root, b.child_part_id, ex.qty*b.qty_per
            FROM ex JOIN bom b ON b.parent_part_id = ex.part)
        SELECT ex.part, SUM(ex.qty * fg.units) / COUNT(DISTINCT fg.plan_date)
        FROM ex JOIN production_plan fg ON fg.part_id = ex.root
        WHERE fg.plan_date >= date('now') GROUP BY ex.part""").fetchall())
    for pid, _, _, _, sid, _ in COMPONENTS:
        use = daily[pid]
        on_hand = use * cover_targets[pid]
        on_order = use * rng.uniform(5, 15)
        for d in range(30, -1, -1):
            day = TODAY - timedelta(days=d)
            oh = on_hand + use * d * rng.uniform(0.8, 1.1)   # drawing down towards today
            cur.execute("INSERT INTO inventory_snapshots VALUES (?,?,?,?)",
                        (day.isoformat(), pid, round(oh), round(on_order)))
    con.commit()
    n = cur.execute("SELECT COUNT(*) FROM purchase_orders").fetchone()[0]
    print(f"Created {DB.name}: {len(COMPONENTS)} components, {n} historical POs")
    con.close()


if __name__ == "__main__":
    main()
