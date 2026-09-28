// Finds part numbers on the page and injects a colour-coded risk badge after each one.
// Pattern: two letters, dash, four digits (e.g. SN-2004, WH-1003). Change PART_RE to match your numbering.
const PART_RE = /\b([A-Z]{2}-\d{4})\b/g;
const SKIP = new Set(["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "NOSCRIPT", "CODE", "PRE"]);

function fmtDate(iso) { return new Date(iso + "T00:00:00").toLocaleDateString(undefined, { day: "numeric", month: "short" }); }

function buildBadge(data) {
  const b = document.createElement("span");
  b.className = "prb-badge";
  if (data.error || data.unknown) {
    b.classList.add("prb-unknown");
    b.textContent = data.unknown ? "no score" : "risk n/a";
    b.title = data.unknown ? "Part not found in risk model" : data.error;
    return b;
  }
  b.style.background = data.color;
  const pct = Math.round(data.shortage_probability * 100);
  b.textContent = `${data.risk_band.toUpperCase()} ${pct}% · ~${Math.round(data.estimated_lead_time_days.typical)}d`;
  b.title =
    `${data.description} (${data.supplier})\n` +
    `Shortage probability: ${pct}%\n` +
    `Days of cover: ${data.days_of_cover}\n` +
    `Lead time: typical ${Math.round(data.estimated_lead_time_days.typical)}d, worst case ${Math.round(data.estimated_lead_time_days.worst_case_p90)}d\n` +
    `Reorder by: ${fmtDate(data.recommended_reorder_date)}${data.reorder_overdue ? " (OVERDUE)" : ""}`;
  return b;
}

function annotate(textNode) {
  const text = textNode.nodeValue;
  PART_RE.lastIndex = 0;
  if (!PART_RE.test(text)) return;
  PART_RE.lastIndex = 0;

  const frag = document.createDocumentFragment();
  let last = 0, m;
  while ((m = PART_RE.exec(text))) {
    frag.append(text.slice(last, m.index), m[1]);
    const badge = document.createElement("span");
    badge.className = "prb-badge prb-loading";
    badge.textContent = "…";
    frag.append(badge);
    chrome.runtime.sendMessage({ type: "lookup", partId: m[1] }, (data) => {
      if (chrome.runtime.lastError || !data) return badge.remove();
      badge.replaceWith(buildBadge(data));
    });
    last = m.index + m[0].length;
  }
  frag.append(text.slice(last));
  textNode.replaceWith(frag);
}

function scan(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(n) {
      const p = n.parentElement;
      if (!p || SKIP.has(p.tagName) || p.isContentEditable || p.closest(".prb-badge")) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(annotate);
}

scan(document.body);

// Handle content that loads later (webmail, single-page portals)
let timer;
new MutationObserver((muts) => {
  clearTimeout(timer);
  timer = setTimeout(() => {
    muts.forEach((mu) => mu.addedNodes.forEach((n) => {
      if (n.nodeType === 1 && !n.classList.contains("prb-badge")) scan(n);
      else if (n.nodeType === 3 && n.parentElement) scan(n.parentElement);
    }));
  }, 300);
}).observe(document.body, { childList: true, subtree: true });
