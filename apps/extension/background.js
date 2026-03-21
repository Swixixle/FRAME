/**
 * Frame extension — background service worker.
 * Pipeline: image blob → POST /v1/analyze-and-verify → receipt URL.
 */

const FRAME_CONFIG = {
  apiBase: "https://frame-2yxu.onrender.com",
};

function api(path) {
  return `${FRAME_CONFIG.apiBase.replace(/\/$/, "")}${path}`;
}

function receiptUrlFromSigned(signed) {
  if (!signed || typeof signed !== "object") return null;
  if (signed.receiptUrl) return signed.receiptUrl;
  const id = signed.receiptId;
  if (id) return `${FRAME_CONFIG.apiBase.replace(/\/$/, "")}/receipt/${id}`;
  return null;
}

function notifyFailure(reason) {
  const msg = "Frame could not verify this image. " + (reason || "Unknown error.");
  chrome.notifications.create({
    type: "basic",
    iconUrl: chrome.runtime.getURL("icons/icon128.png"),
    title: "Frame",
    message: msg.slice(0, 250),
  });
}

async function saveLastReceipt(url) {
  await chrome.storage.local.set({
    lastReceiptUrl: url,
    lastReceiptAt: Date.now(),
  });
}

async function blobToAnalyzeSign(blob, filename) {
  const form = new FormData();
  form.append("file", blob, filename || "frame-capture.png");

  const res = await fetch(api("/v1/analyze-and-verify"), {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const t = await res.text().catch(() => "");
    throw new Error(`Analyze-and-verify failed (HTTP ${res.status}). ${t.slice(0, 120)}`);
  }

  const signed = await res.json();
  const url = receiptUrlFromSigned(signed);
  if (!url) throw new Error("No receipt URL in response.");
  return url;
}

async function fetchImageAsBlob(srcUrl, tabId) {
  if (!srcUrl) throw new Error("No image URL.");

  if (srcUrl.startsWith("blob:") || srcUrl.startsWith("data:")) {
    return fetchBlobViaContentScript(tabId, srcUrl);
  }

  try {
    const res = await fetch(srcUrl, { credentials: "omit", mode: "cors" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const blob = await res.blob();
    if (!blob || blob.size === 0) throw new Error("Empty image.");
    return blob;
  } catch (e) {
    if (tabId != null) {
      return fetchBlobViaContentScript(tabId, srcUrl);
    }
    throw e;
  }
}

function fetchBlobViaContentScript(tabId, url) {
  return new Promise((resolve, reject) => {
    chrome.tabs.sendMessage(
      tabId,
      { type: "FRAME_GET_IMAGE_BLOB", url },
      async (response) => {
        const err = chrome.runtime.lastError;
        if (err) {
          reject(new Error(err.message));
          return;
        }
        if (!response || !response.ok) {
          reject(new Error((response && response.error) || "Could not read image in page."));
          return;
        }
        try {
          const bytes = new Uint8Array(response.buffer);
          const mime = response.mime || "image/png";
          resolve(new Blob([bytes], { type: mime }));
        } catch (e) {
          reject(e);
        }
      }
    );
  });
}

async function runPipelineFromBlob(blob) {
  const url = await blobToAnalyzeSign(blob, "frame-image.png");
  await saveLastReceipt(url);
  await chrome.tabs.create({ url, active: true });
  return url;
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "frame-verify-image",
      title: "Verify with Frame",
      contexts: ["image"],
    });
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "frame-verify-image") return;
  try {
    const blob = await fetchImageAsBlob(info.srcUrl, tab && tab.id);
    await runPipelineFromBlob(blob);
  } catch (e) {
    notifyFailure(e.message || String(e));
  }
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "FRAME_CAPTURE_VISIBLE_TAB") {
    (async () => {
      try {
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const tab = tabs[0];
        if (!tab || tab.id == null) throw new Error("No active tab.");

        const dataUrl = await chrome.tabs.captureVisibleTab(null, { format: "png" });
        const blob = dataUrlToBlob(dataUrl);
        const url = await runPipelineFromBlob(blob);
        sendResponse({ ok: true, receiptUrl: url });
      } catch (e) {
        notifyFailure(e.message || String(e));
        sendResponse({ ok: false, error: e.message || String(e) });
      }
    })();
    return true;
  }
  return false;
});

function dataUrlToBlob(dataUrl) {
  const i = dataUrl.indexOf(",");
  if (i < 0) throw new Error("Invalid capture data.");
  const header = dataUrl.slice(0, i);
  const b64 = dataUrl.slice(i + 1);
  const mimeMatch = /data:([^;]+)/.exec(header);
  const mime = mimeMatch ? mimeMatch[1] : "image/png";
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let j = 0; j < binary.length; j++) bytes[j] = binary.charCodeAt(j);
  return new Blob([bytes], { type: mime });
}
