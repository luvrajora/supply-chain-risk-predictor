-- Core relational model (mirrors what you'd extract from SAP/Oracle: MARA/EKKO/EKPO/MARD, etc.)
PRAGMA foreign_keys = ON;

CREATE TABLE suppliers (
    supplier_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    country       TEXT,
    tier          INTEGER              -- 1 = direct supplier
);

CREATE TABLE parts (
    part_id       TEXT PRIMARY KEY,
    description   TEXT,
    category      TEXT,                -- harness, sensor, connector, raw...
    part_type     TEXT CHECK (part_type IN ('FINISHED','COMPONENT')),
    unit_cost     REAL,
    supplier_id   TEXT REFERENCES suppliers(supplier_id),  -- NULL for finished goods
    quoted_lead_days INTEGER
);

-- Multi-level bill of materials: parent consumes qty_per of child
CREATE TABLE bom (
    parent_part_id TEXT REFERENCES parts(part_id),
    child_part_id  TEXT REFERENCES parts(part_id),
    qty_per        REAL NOT NULL,
    PRIMARY KEY (parent_part_id, child_part_id)
);

-- Daily production plan for finished goods
CREATE TABLE production_plan (
    plan_date   DATE,
    part_id     TEXT REFERENCES parts(part_id),
    units       INTEGER,
    PRIMARY KEY (plan_date, part_id)
);

CREATE TABLE line_costs (
    part_id                TEXT PRIMARY KEY REFERENCES parts(part_id),
    stoppage_cost_per_hour REAL,        -- lost margin + idle labour
    hours_per_day          REAL
);

-- Nightly ERP inventory snapshot
CREATE TABLE inventory_snapshots (
    snapshot_date DATE,
    part_id       TEXT REFERENCES parts(part_id),
    on_hand       REAL,
    on_order      REAL,                 -- open PO quantity inbound
    PRIMARY KEY (snapshot_date, part_id)
);

-- Historical PO receipts: source of lead-time variance
CREATE TABLE purchase_orders (
    po_id          INTEGER PRIMARY KEY,
    part_id        TEXT REFERENCES parts(part_id),
    supplier_id    TEXT REFERENCES suppliers(supplier_id),
    order_date     DATE,
    promised_date  DATE,
    received_date  DATE,
    qty            REAL
);

-- Model outputs (written by risk_model.py, read by dashboards and the API)
CREATE TABLE part_risk (
    run_date            DATE,
    part_id             TEXT,
    shortage_prob       REAL,
    days_of_cover       REAL,
    lead_p50            REAL,
    lead_p90            REAL,
    reorder_by          DATE,
    expected_gap_days   REAL,
    expected_loss       REAL,
    risk_band           TEXT,
    PRIMARY KEY (run_date, part_id)
);

CREATE TABLE supplier_scores (
    run_date         DATE,
    supplier_id      TEXT,
    on_time_rate     REAL,
    mean_delay_days  REAL,
    delay_std_days   REAL,
    reliability_score REAL,
    n_orders         INTEGER,
    PRIMARY KEY (run_date, supplier_id)
);
