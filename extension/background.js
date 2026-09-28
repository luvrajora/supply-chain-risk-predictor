// Service worker: calls the risk API (avoids mixed-content/CORS problems in web pages) and caches results.
const DEFAULTS = { apiUrl: "http://localhost:8000", apiKey: "" };
const cache = new Map();            // part_id -> { data, time }
const TTL_MS = 10 * 60 * 1000;      // re-check every 10 minutes

async function lookup(partId) {
  const hit = cache.get(partId);
  if (hit && Date.now() - hit.time < TTL_MS) return hit.data;

  const { apiUrl, apiKey } = await chrome.storage.sync.get(DEFAULTS);
  const headers = apiKey ? { "X-API-Key": apiKey } : {};
  let data;
  try {
    const res = await fetch(`${apiUrl.replace(/\/$/, "")}/api/part-risk?part_id=${encodeURIComponent(partId)}`, { headers });
    if (res.status === 404) data = { unknown: true };
    else if (!res.ok) data = { error: `API ${res.status}` };
    else data = await res.json();
  } catch (e) {
    data = { error: "API unreachable" };
  }
  if (!data.error) cache.set(partId, { data, time: Date.now() });
  return data;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "lookup") { lookup(msg.partId).then(sendResponse); return true; }   // async response
});
