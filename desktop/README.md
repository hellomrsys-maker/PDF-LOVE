# PDF Love Desktop

A native app for Windows, macOS and Linux that bundles the engine, so
**every one of the 104 tools runs on the user's own machine** — including
the ten that the web app can only offer when someone has stood up a
server.

## Why this exists

In the browser, 94 tools run on-device and 10 do not, because they depend on
engines too large to ship to a page: Tesseract for OCR, LibreOffice for
full-fidelity Office conversion, Ghostscript for deep compression. In the
web app those tools are simply invisible unless a backend is reachable.

The desktop app closes that gap by shipping the engine inside the
installer. It starts as a child process on `127.0.0.1`, the UI points at it
automatically, and the server tools light up. No account, no upload, no
server anywhere in the picture.

## How it fits together

```
Tauri shell (Rust, ~10 MB)
├── webview → ../frontend/index.html        the existing app, unmodified
└── sidecar → pdflove-engine (~39 MB)     PyInstaller-frozen backend
                ├── dockbench_imgproc.so    fused C scan-cleanup kernel
                ├── dockbench_pdf.so        fused libqpdf page operations
                └── FastAPI on 127.0.0.1:0
```

The UI is **not forked**. `frontendDist` points at `../../frontend`, the
same directory the website is served from, so a fix lands in both.

### Handshake

1. The shell spawns the engine as a Tauri sidecar.
2. The engine binds `127.0.0.1:0` — loopback only, OS-assigned port — mints
   a random 256-bit session token, and prints one line:
   `DOCKBENCH_READY <port> <token>`.
3. The shell parses that line and sets `dockbench.apiBase` and
   `dockbench.apiToken` in the webview's localStorage. These are the same
   two keys someone would set by hand to aim the web app at a self-hosted
   backend; the shell just fills them in.
4. `/capabilities` now answers, so the server tools appear.

### Security

Running a local HTTP server on someone's laptop deserves care:

- **Loopback only.** Never `0.0.0.0` — nothing off-machine can reach it.
- **Ephemeral port.** Port 0, so it isn't sitting somewhere predictable.
- **Session token required.** Without it, any local process — including a
  web page in a browser tab doing a form POST — could drive the engine.
  Compared with `secrets.compare_digest`, so the check isn't timing-dependent.
  Only `/health` and the OpenAPI docs are exempt.
- **Dies with the app.** Tauri kills the sidecar on clean exit, and the
  engine also watches stdin for EOF so a crash or `SIGKILL` can't leave an
  orphan listening.
- **No business API key.** `DOCKBENCH_LOCAL=1` disables key enforcement.
  Someone running the engine on their own machine is not a customer to be
  metered.

## Building

Needs Python 3.11+, Node 20+, a Rust toolchain, and `libqpdf-dev`
(`brew install qpdf` on macOS).

```bash
cd desktop
npm install
npm run build          # builds the engine, then the installers
```

Or separately:

```bash
python ../desktop/build-engine.py      # 1. extensions + PyInstaller
npx tauri build                        # 2. installers
```

Output lands in `src-tauri/target/<triple>/release/bundle/` as `.msi`/`.exe`
(Windows), `.dmg` (macOS), `.AppImage`/`.deb` (Linux).

CI builds all four targets on tag push — see
`.github/workflows/desktop.yml`. It asserts the engine starts, refuses
untokened requests, reports `imgproc_backend: extension` (a silent fallback
to the slow Python path is a real regression), and exits with its parent.

## Before shipping

- [ ] `[COMPANY LEGAL NAME]` in `tauri.conf.json`
- [ ] Generate an updater keypair: `npx tauri signer generate`, put the
      public half in `tauri.conf.json` and the private half in the
      `TAURI_SIGNING_PRIVATE_KEY` secret
- [ ] Point `plugins.updater.endpoints` at a real host
- [ ] Add app icons under `src-tauri/icons/` (`npx tauri icon path/to/icon.png`
      generates the full set from one source image)
- [ ] **Code-sign.** Unsigned downloads convert badly and Windows
      SmartScreen and macOS Gatekeeper will both warn users off. Budget for
      an EV certificate and an Apple Developer ID.

## Updates

The Tauri updater checks a signed `latest.json` on launch. **This is the
only routine network request the desktop app makes** — a version string
out, a signed manifest back. No telemetry, and no document data, ever.
