const lastUrlEl = document.getElementById("last-url");
const copyBtn = document.getElementById("copy-btn");
const captureBtn = document.getElementById("capture-btn");
const errEl = document.getElementById("err");

async function refresh() {
  errEl.classList.remove("visible");
  errEl.textContent = "";
  const { lastReceiptUrl } = await chrome.storage.local.get(["lastReceiptUrl"]);
  if (lastReceiptUrl) {
    lastUrlEl.textContent = lastReceiptUrl;
    lastUrlEl.classList.remove("empty");
    copyBtn.disabled = false;
  } else {
    lastUrlEl.textContent = "No receipt yet — capture a tab or right‑click an image.";
    lastUrlEl.classList.add("empty");
    copyBtn.disabled = true;
  }
}

copyBtn.addEventListener("click", async () => {
  const { lastReceiptUrl } = await chrome.storage.local.get(["lastReceiptUrl"]);
  if (!lastReceiptUrl) return;
  try {
    await navigator.clipboard.writeText(lastReceiptUrl);
    errEl.textContent = "Copied.";
    errEl.style.color = "#4caf7a";
    errEl.classList.add("visible");
    setTimeout(() => errEl.classList.remove("visible"), 2000);
  } catch (e) {
    errEl.textContent = e.message || String(e);
    errEl.style.color = "#c75c5c";
    errEl.classList.add("visible");
  }
});

captureBtn.addEventListener("click", async () => {
  captureBtn.disabled = true;
  errEl.classList.remove("visible");
  try {
    const r = await chrome.runtime.sendMessage({ type: "FRAME_CAPTURE_VISIBLE_TAB" });
    if (!r || !r.ok) {
      throw new Error((r && r.error) || "Capture failed.");
    }
    await refresh();
  } catch (e) {
    errEl.textContent = e.message || String(e);
    errEl.style.color = "#c75c5c";
    errEl.classList.add("visible");
  } finally {
    captureBtn.disabled = false;
  }
});

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && changes.lastReceiptUrl) {
    refresh();
  }
});

refresh();
