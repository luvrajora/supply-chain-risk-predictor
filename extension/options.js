const $ = (id) => document.getElementById(id);
chrome.storage.sync.get({ apiUrl: "http://localhost:8000", apiKey: "" }).then((s) => { $("url").value = s.apiUrl; $("key").value = s.apiKey; });
$("save").onclick = () => chrome.storage.sync.set({ apiUrl: $("url").value.trim(), apiKey: $("key").value.trim() })
  .then(() => { $("msg").textContent = "Saved"; setTimeout(() => ($("msg").textContent = ""), 1500); });
