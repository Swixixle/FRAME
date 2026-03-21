# Frame — Chrome / Brave extension

Manifest **v3**, **vanilla JS** (no build step). Sends images to Frame’s media pipeline and opens the shareable receipt.

## What it does

- **Toolbar** — click the Frame icon to open a popup: last receipt URL, **Copy URL**, **Capture visible tab** (full-page screenshot of the active tab → **`POST /v1/analyze-and-verify`** → new tab with receipt).
- **Right‑click** any image → **Verify with Frame** — fetches the image (or reads it via the page when CORS/blob URLs require it), same one-shot pipeline (analyze + routed public-record adapters + sign).
- **Errors** — `chrome.notifications` with: *Frame could not verify this image. …*

## Configure API base

At the top of **`background.js`**:

```javascript
const FRAME_CONFIG = {
  apiBase: "https://frame-2yxu.onrender.com",
};
```

Change `apiBase` to your own Frame API origin (no trailing slash). Reload the extension after editing.

If the sign response omits `receiptUrl`, the extension builds  
`{apiBase}/receipt/{receiptId}` automatically.

## Load unpacked (Chrome / Brave)

1. Open **`chrome://extensions`** (Brave: **`brave://extensions`**).
2. Turn on **Developer mode** (top right).
3. **Load unpacked** → select this folder: `FRAME/apps/extension/`.
4. Pin **Frame** to the toolbar if you like.

First run: allow **notifications** if the browser asks (used for error toasts).

## Permissions (why)

| Permission        | Use |
|-----------------|-----|
| `activeTab`     | Capture the visible tab after you use the toolbar |
| `contextMenus`  | “Verify with Frame” on images |
| `scripting`     | Reserved for future injection; content script handles blob/CORS fallbacks |
| `notifications` | Error messages |
| `clipboardWrite`| Copy receipt URL in the popup |
| `storage`       | Remember last receipt URL for the popup |
| `host_permissions` | Call the Frame API; fetch image URLs from pages |

## Files

| File            | Role |
|-----------------|------|
| `manifest.json` | MV3 manifest |
| `background.js` | Service worker: menu, fetch/capture, API, storage, tabs |
| `popup.html` / `popup.js` | Toolbar popup UI |
| `content.js`    | Page-side fetch for `blob:` / strict CORS images |
| `icons/`        | 16 / 48 / 128 placeholder PNGs |

## Testing tips

- **Capture visible tab**: open any `https://` page, click the Frame icon → **Capture visible tab**. A new tab should open with the receipt page.
- **Right‑click image**: use a normal `<img src="https://...">` on a public site; some hotlinked or `blob:` images need the content-script path (automatic when background fetch fails).

## Privacy

Images are sent to your configured Frame API only. No third-party analytics in this extension.
