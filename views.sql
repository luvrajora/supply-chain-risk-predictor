-- Views consumed directly by Power BI / Tableau (ODBC) or exported to CSV.
-- Each view always reflects the latest model run.

DROP VIEW IF EXISTS v_latest_run;
CREATE VIEW v_latest_run AS SELECT MAX(run_date) AS run_date FROM part_risk;

-- 1. "Parts at Risk" panel
DROP VIEW IF EXISTS v_parts_at_risk;
CREATE VIEW v_parts_at_risk AS
SELECT r.run_date, r.part_id, p.description, p.category,
       s.name AS supplier, s.country,
       r.shortage_prob, r.risk_band, r.days_of_cover,
       r.lead_p50, r.lead_p90, r.reorder_by,
       CASE WHEN r.reorder_by <= r.run_date THEN 1 ELSE 0 END AS reorder_overdue,
       r.expected_gap_days, r.expected_loss,
       i.on_hand, i.on_order
FROM part_risk r
JOIN v_latest_run l ON l.run_date = r.run_date
JOIN parts p ON p.part_id = r.part_id
LEFT JOIN suppliers s ON s.supplier_id = p.supplier_id
LEFT JOIN inventory_snapshots i ON i.part_id = r.part_id
     AND i.snapshot_date = (SELECT MAX(snapshot_date) FROM inventory_snapshots);

-- 2. Supplier reliability panel
DROP VIEW IF EXISTS v_supplier_reliability;
CREATE VIEW v_supplier_reliability AS
SELECT sc.run_date, sc.supplier_id, s.name, s.country,
       sc.on_time_rate, sc.mean_delay_days, sc.delay_std_days,
       sc.reliability_score, sc.n_orders,
       (SELECT COUNT(*) FROM parts p WHERE p.supplier_id = sc.supplier_id) AS parts_supplied
FROM supplier_scores sc
JOIN v_latest_run l ON l.run_date = sc.run_date
JOIN suppliers s ON s.supplier_id = sc.supplier_id;

-- 3. Financial impact by vehicle line (which lines are exposed, weighted by shortage probability)
DROP VIEW IF EXISTS v_financial_impact;
CREATE VIEW v_financial_impact AS
WITH RECURSIVE ex(root, part) AS (
    SELECT part_id, part_id FROM parts WHERE part_type = 'FINISHED'
    UNION ALL SELECT ex.root, b.child_part_id FROM ex JOIN bom b ON b.parent_part_id = ex.part)
SELECT r.run_date, ex.root AS line_id, fg.description AS line_name, r.part_id,
       r.shortage_prob, r.expected_gap_days,
       lc.stoppage_cost_per_hour, lc.hours_per_day,
       r.shortage_prob * lc.stoppage_cost_per_hour * lc.hours_per_day AS prob_weighted_daily_exposure,
       r.expected_gap_days * lc.stoppage_cost_per_hour * lc.hours_per_day AS expected_stoppage_cost
FROM part_risk r
JOIN v_latest_run l ON l.run_date = r.run_date
JOIN ex ON ex.part = r.part_id
JOIN line_costs lc ON lc.part_id = ex.root
JOIN parts fg ON fg.part_id = ex.root;

-- 4. Lead-time variance detail (histograms / box plots)
DROP VIEW IF EXISTS v_lead_time_history;
CREATE VIEW v_lead_time_history AS
SELECT po.po_id, po.part_id, po.supplier_id, po.order_date, po.promised_date, po.received_date,
       julianday(po.received_date) - julianday(po.order_date)    AS actual_lead_days,
       julianday(po.received_date) - julianday(po.promised_date) AS delay_days
FROM purchase_orders po;

-- 5. BOM tree for drill-down (flattened, with depth)
DROP VIEW IF EXISTS v_bom_flat;
CREATE VIEW v_bom_flat AS
WITH RECURSIVE ex(root, part, qty, depth) AS (
    SELECT part_id, part_id, 1.0, 0 FROM parts WHERE part_type = 'FINISHED'
    UNION ALL SELECT ex.root, b.child_part_id, ex.qty * b.qty_per, ex.depth + 1
    FROM ex JOIN bom b ON b.parent_part_id = ex.part)
SELECT root AS finished_good, part AS component, qty AS qty_per_vehicle, depth FROM ex WHERE depth > 0;

-- 6. Risk trend over time (once the nightly job has run for several days)
DROP VIEW IF EXISTS v_risk_trend;
CREATE VIEW v_risk_trend AS
SELECT run_date, part_id, shortage_prob, risk_band, days_of_cover FROM part_risk;
