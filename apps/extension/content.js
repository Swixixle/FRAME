/**
 * Runs in page context — used when the service worker cannot fetch an image URL
 * (e.g. blob: URLs or strict CORS). Fetches in the page and returns raw bytes.
 */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "FRAME_GET_IMAGE_BLOB") return;

  (async () => {
    try {
      const res = await fetch(msg.url, { credentials: "include", mode: "cors" });
      if (!res.ok) {
        sendResponse({ ok: false, error: `HTTP ${res.status}` });
        return;
      }
      const buf = await res.arrayBuffer();
      const mime = res.headers.get("content-type") || "image/png";
      sendResponse({
        ok: true,
        buffer: Array.from(new Uint8Array(buf)),
        mime,
      });
    } catch (e) {
      sendResponse({ ok: false, error: e.message || String(e) });
    }
  })();

  return true;
});
