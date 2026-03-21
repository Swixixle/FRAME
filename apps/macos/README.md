# Frame Capture (macOS)

Lightweight capture flow: **select a screen region** → **Frame analyze + sign** → **receipt URL in clipboard** + notification.

Implementation is **bash + curl + `screencapture` + `osascript`** only (no Electron, Node, or Python in the tool itself).

## Requirements

- macOS **13+** (Ventura or later)
- **curl**, **bash**, **screencapture**, **osascript**, **plutil** (all ship with macOS)

## 1. Run the standalone script

From the repo root:

```bash
chmod +x scripts/frame-capture.sh
./scripts/frame-capture.sh
```

Or from anywhere:

```bash
/path/to/FRAME/scripts/frame-capture.sh
```

Flow:

1. Native crosshair selection (`screencapture -i`)
2. `POST …/v1/analyze-and-verify` (multipart PNG) — OCR, claim routing, public-record adapters, sign, `receiptUrl` in one response
3. Copies `receiptUrl` to the clipboard (or builds `/receipt/{receiptId}` if the field is omitted)
4. Notification: **Frame receipt ready — link copied to clipboard**

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `FRAME_API_BASE` | `https://frame-2yxu.onrender.com` | API origin (no trailing slash) |
| `FRAME_OPEN_BROWSER` | `0` | Set to `1` to open the receipt URL in the default browser after copying |
| `FRAME_CAPTURE_PATH` | `/tmp/frame_capture.png` | Where the PNG is written before upload |

Example:

```bash
FRAME_OPEN_BROWSER=1 ./scripts/frame-capture.sh
```

## 2. Screen Recording permission

The first time **`screencapture -i`** runs, macOS may prompt for **Screen Recording** access (or block capture until you allow it).

1. **System Settings** → **Privacy & Security** → **Screen Recording**
2. Enable the app you’re using:
   - **Terminal** or **iTerm** (if you run the script from a terminal), **or**
   - **FrameCapture** (if you use the `.app` bundle), **or**
   - **Platypus** helper app name (if you use Platypus for the menu bar)

Then run capture again. Apple documents this flow for interactive capture tools.

## 3. Use the bundled `.app` (no Dock icon)

`FrameCapture.app` is a minimal bundle:

- **`Contents/MacOS/FrameCapture`** — launcher
- **`Contents/Resources/frame-capture.sh`** — copy of `scripts/frame-capture.sh`
- **`Contents/Info.plist`** — **`LSUIElement` = true** (agent-style: no Dock icon)

Install:

1. Copy `apps/macos/FrameCapture.app` to **Applications** (or run it from the repo).
2. First launch: **right‑click → Open** if Gatekeeper warns (unsigned app).
3. Grant **Screen Recording** for **FrameCapture** (see above).

Double‑clicking the app runs **one** capture cycle (crosshair → API → clipboard). There is no window.

### Keep the embedded script in sync

After editing `scripts/frame-capture.sh`, refresh the copy inside the app:

```bash
cd apps/macos
./sync-embedded-script.sh
```

## 4. Menu bar: “Capture” + “Quit” (Platypus)

Pure shell **cannot** draw a menu bar icon by itself. The usual lightweight approach is **[Platypus](https://sveinbjorn.org/platypus)** (free):

1. Install Platypus.
2. Create a **Status Menu** application (menu bar app).
3. Script path: point to **`scripts/frame-capture.sh`** (or the copy under `FrameCapture.app/.../Resources/`).
4. Add menu items, for example:
   - **Capture with Frame** → runs `frame-capture.sh`
   - **Quit** → Platypus default quit for status menu apps

Use the same **Screen Recording** permission for the Platypus-generated app name.

## 5. Optional: SwiftBar / xbar

If you use [SwiftBar](https://github.com/swiftbar/SwiftBar) or xbar, add a plugin that invokes `scripts/frame-capture.sh` (absolute path, `terminal=false`). See `extras/swiftbar-example.sh`.

## Icon placeholder

There is no `AppIcon.icns` in-repo. To add one:

1. Create a **1024×1024** PNG (e.g. a simple **F** mark).
2. Build an iconset and run **`iconutil`** to produce **`AppIcon.icns`**.
3. Place **`AppIcon.icns`** in `FrameCapture.app/Contents/Resources/`.
4. Add to `Info.plist`:

```xml
<key>CFBundleIconFile</key>
<string>AppIcon</string>
```

## Troubleshooting

- **HTTP non-200 from analyze/sign** — you’ll get a notification with a short error snippet; check API status and keys on the server (`FRAME_PRIVATE_KEY`, etc.).
- **Empty `receiptUrl`** — signing failed or response shape changed; verify `POST /v1/analyze-and-verify` returns `receiptUrl` or `receiptId`.
- **plutil errors** — the script falls back to `sed` for `"receiptUrl":"…"`; ensure the API returns JSON with that field.

## Files

| Path | Role |
|------|------|
| `scripts/frame-capture.sh` | Canonical script |
| `apps/macos/FrameCapture.app/` | LSUIElement `.app` wrapper |
| `apps/macos/sync-embedded-script.sh` | Copies script into the `.app` |
| `apps/macos/extras/swiftbar-example.sh` | SwiftBar / xbar example |
