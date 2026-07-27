# Dockbench

A 104-tool PDF, image & video workbench where **everything — OCR, AI
background removal, compression, conversion — runs on the user's own
device**. Every dependency is free and open-source, there is no paid API
anywhere in the stack, and after the first page load the app runs **fully
offline**.

Three ways to run it, in increasing order of what stays local:

| | Where tools run | What you need |
|---|---|---|
| **Double-click `index.html`** | 97 of 104 on-device | nothing at all |
| **Any static host** (Netlify, Pages, S3) | 97 of 104 on-device | a file host |
| **[Desktop app](desktop/README.md)** | **all 104 on-device** | the installer |

The desktop app bundles the engine, so the seven tools that need real
engines (Tesseract, LibreOffice, Ghostscript) run on the user's own machine
too. A self-hosted backend remains available for teams who want a shared
one, and the HTTP API is offered to business customers — but neither is
required for anything.

## Why it beats the alternatives

| | Dockbench | iLovePDF / Smallpdf (paid) | Stirling-PDF (self-hosted) |
|---|---|---|---|
| Files stay on-device | ✅ 97 of 104 in-browser, **104 of 104 in the desktop app** | ❌ every tool uploads | ❌ every tool goes to the server |
| Works by double-clicking the HTML file | ✅ no server needed at all | ❌ | ❌ |
| Native installer | ✅ Windows / macOS / Linux, engine included | ❌ web only | ❌ Docker only |
| Video tools (GIF, trim, slideshow, screen rec.) | ✅ on-device | partial, cloud | ❌ |
| Works offline (PWA) | ✅ core app + encryption | ❌ | ❌ needs the server |
| Daily limits / subscription | none | 1-2 free tasks/day, then $4-10/mo | none |
| Real AES-256 encrypt/decrypt in the browser | ✅ (qpdf → WebAssembly) | server-side | server-side |
| OCR → searchable PDF | ✅ **in the browser** (Tesseract→WASM, offline) | ✅ (their cloud) | ✅ (server) |
| AI background removal | ✅ **in the browser** (RMBG, cached model) | ☁ their cloud | ✅ (server) |
| Office ↔ PDF (full fidelity) | ✅ (self-hosted LibreOffice) | ✅ (their cloud) | ✅ |
| AI summarize/translate/chat | ✅ on-device (Transformers.js) or your own Ollama | ☁ their cloud AI | partial |
| External services required | none (one optional: live FX rates) | their cloud | none |

The design principle: **keep the high-frequency tools 100% local** for the
trust story and zero hosting cost, and reserve the server for jobs where
real engines (Tesseract, LibreOffice, Ghostscript) are the difference
between a toy and a tool — while keeping that server yours, free, and
open-source, or skipping it entirely by installing the desktop app.

You can verify the on-device claim in about fifteen seconds: devtools →
Network tab → use any on-device tool → no request fires.

## Structure

```
├── frontend/
│   ├── index.html        ← the entire client-side app (104 tools)
│   ├── vendor/           ← all JS/WASM libraries, self-hosted (no CDN needed)
│   ├── company/          ← about, pricing, contact, security, legal pages
│   ├── guides/           ← 7 plain-language SEO help pages
│   ├── manifest.json, sw.js  ← installable PWA, offline-capable
│   ├── nginx.conf        ← production static hosting + /api/ reverse proxy
│   └── Dockerfile        ← nginx-based image
├── backend/               ← the engine: server-assisted tools
│   ├── main.py           ← FastAPI app (see endpoints below)
│   ├── engines.py        ← engine logic, framework-free
│   ├── premium_pdf.py    ← page ops, on the fused C engine
│   ├── apikeys.py        ← business-tier API keys, verified offline
│   ├── local_engine.py   ← entrypoint when bundled in the desktop app
│   ├── native/imgproc.c        ← C scan-cleanup kernel (pure, portable)
│   ├── native/imgprocmodule.c  ← its CPython extension wrapper
│   ├── native/pdfops.cpp       ← libqpdf linked in-process
│   ├── setup.py          ← builds both extensions
│   └── Dockerfile        ← gunicorn + Tesseract + Ghostscript + LibreOffice
├── desktop/               ← Tauri app bundling the engine (all 104 local)
├── licensing/             ← offline licence + API key minting
├── docker-compose.yml    ← frontend + backend + queue + local LLM (Ollama)
└── .github/workflows/
    ├── validate.yml      ← CI: syntax, wiring, extension/fallback equivalence,
    │                       API-key gating, real browser functional test
    ├── desktop.yml       ← builds Windows/macOS/Linux installers
    └── release.yml       ← container images + offline bundle
```

## 1. Frontend — no setup, no build step, no CDN

**The simplest way to run Dockbench: download the `frontend/` folder and
double-click `index.html`.** Everything works straight from the file —
PDF rendering runs on the main thread via the bundled worker script, and
even AES-256 encryption works offline (the WASM engine ships as an
embedded base64 copy in `vendor/qpdf.wasm.b64.js`, because browsers block
fetching local `.wasm` files). Only the server-assisted section needs
more than that.

`frontend/index.html` plus `frontend/vendor/` is the complete client-side
app. Every library it uses (pdf-lib, pdf.js, JSZip, mammoth, jsPDF,
html2canvas, qrcode, jsQR, JsBarcode, and qpdf compiled to WebAssembly)
is **self-hosted in `vendor/`** — zero external requests, and each script
tag still carries a pinned-version CDN fallback in case a stray copy of
the HTML is served without the vendor directory.

- **Serve it statically**:
  ```bash
  cd frontend
  python3 -m http.server 5500   # visit http://localhost:5500
  ```
- **Deploy it anywhere that hosts static files** — Netlify, GitHub Pages,
  S3, your own nginx. Hosting cost is effectively zero.
- **Install it as an app** — the service worker precaches everything, so
  after one visit the whole toolbox (including AES-256 encryption) works
  in airplane mode.
- **Navigate fast** — category tabs act like separate pages, Ctrl/Cmd+K
  jumps to search, ★ pins favorites to the top, and a "recently used"
  row remembers your workflow (both stored only in your browser). The
  whole UI follows your system's light/dark preference.

On-device highlights (~85 tools): merge, split (range or per-page),
organize, crop, rotate, N-up, compress, repair, compare, scan-to-PDF,
extract images, **flatten forms**, **sanitize (strip scripts/attachments/
metadata)**, grayscale, Bates numbering, headers/footers, watermark,
search-&-redact (SSNs/emails/phones), sign, stamp, forms, **protect/unlock
with real AES-256 in the browser**, PDF↔Word/Markdown/text, Markdown→PDF,
images↔PDF (JPG/PNG/WebP/GIF/BMP), image compress/resize/convert/rotate,
**EXIF viewer & stripper**, passport photos, ID/business cards, favicon
generator, QR/barcode, plus text, utility, finance, and fully on-device AI
tools (summarize, translate, voice-to-text, image captioning via
Transformers.js — model downloads once, then offline).

**Ask Dockbench (plain-language help desk)**: type what you want in your
own words — "compress this and give me a markdown copy", "make this scan
searchable" — and the assistant splits the request into steps, picks the
right tools, and walks you through with the file carried from step to step
automatically. Rule-based and instant: no model download, works offline,
multi-task requests supported, and after finishing a step it can suggest a
commonly-paired next one (e.g. compress → protect with a password). It
understands starting Spanish and Hindi (Devanagari + Hinglish) phrasing for
the ~20 most-used tools alongside English — the same flat phrase list, no
separate code path, easy to extend. It's also the front door for people who
don't know what MB/KB or "OCR" mean.

**On-device OCR**: the real Tesseract engine compiled to WebAssembly ships
with the app (`vendor/tesseract`, ~19 MB, precached) — scanned PDFs become
searchable PDFs or plain text without any server, offline after the first
visit. More languages: drop `{lang}.traineddata.gz` into
`vendor/tesseract/lang/` and add the dropdown option in `toolLocalOCR`.

**On-device AI background removal**: the open RMBG model via Transformers.js
(one ~44 MB download, then cached/offline; GPU-accelerated where available).

**Big-file safety**: heavy tools estimate their memory need against the
device before starting and suggest a workaround instead of crashing the
tab; giant results stream directly to disk (File System Access API) and
page renders are capped at 8192px to block pixel-bomb files.

**Video tools** (all on-device): images → slideshow video with
crossfades, video → GIF (gifenc, pure JS), trim video (keeps audio),
screen recorder, and extract-audio-to-WAV. Recording uses the browser's
MediaRecorder — MP4 where the browser supports it, WebM otherwise, and
the button label tells you which before you click.

Every on-device tool reads the file with the File API, processes it in
memory, and triggers a browser download — the bytes never touch a network
request. Verify it yourself: devtools → Network tab → use any tool → no
request fires.

## 2. Desktop app — every tool on your own hardware

`desktop/` is a Tauri app that **bundles the engine**, so all 104 tools run
locally, including the seven the browser can't do alone (OCR, full-fidelity
Office conversion, Ghostscript compression, PDF/A, background removal,
chat). No server, no account, no upload.

```
Tauri shell (~10 MB)
├── webview → frontend/index.html      the same app, not a fork
└── sidecar → dockbench-engine         PyInstaller-frozen backend + the
                                       fused C extensions above
```

The engine binds `127.0.0.1` on an OS-assigned port, mints a random session
token, and prints `DOCKBENCH_READY <port> <token>`. The shell writes those
into the page's `localStorage` — the same two keys you'd set by hand to aim
the web app at a self-hosted backend. `/capabilities` then answers and the
server tools appear.

It is loopback-only, token-gated (so no other local process can drive it),
and dies with the app. The updater's check for a signed manifest is the
**only** routine network request the desktop app makes.

```bash
cd desktop && npm install && npm run build
```

Full detail, including the pre-ship checklist: **[desktop/README.md](desktop/README.md)**.

## 3. Backend — self-hosted, C-accelerated

The server-assisted tools use real engines, all C/C++ under a Python
orchestration layer — "C for the hot path, Python for the glue":

| Tool | Engine | License |
|---|---|---|
| OCR (text or **searchable PDF**) | Tesseract 5 (C++) + `native/imgproc.c` cleanup kernel | Apache-2.0 |
| Office → PDF (full fidelity) | LibreOffice headless (C++) | MPL-2.0 |
| PDF → Word (layout-aware) | pdf2docx on MuPDF (C) | GPL-3 / AGPL-3 |
| PDF → PowerPoint / Excel | PyMuPDF rendering / table detection (C) | AGPL-3 |
| Deep PDF compression | Ghostscript (C) | AGPL-3 |
| PDF/A archival conversion | Ghostscript (C) | AGPL-3 |
| Background removal | rembg + onnxruntime (C++) | Apache-2.0 |
| Summarize / Chat with PDF | Ollama running Llama 3.2 locally | Llama license (free for this use) |

### C and Python as one process

The engine does not talk to C across a bridge. Both hot paths are **CPython
extension modules** — C compiled into the interpreter's own address space,
no ctypes marshalling and no subprocess:

| Module | Replaces | Why |
|---|---|---|
| `dockbench_imgproc` | ctypes calls into `imgproc.so` | one boundary crossing for the whole pipeline instead of three; GIL released during the pixel work |
| `dockbench_pdf` | shelling out to the `qpdf` CLI | **6.2× faster** on a 200-page split (0.29s vs 1.79s) — 201 `fork`+`exec` calls and a filesystem round trip per page, gone |

`native/imgproc.c` deliberately includes no Python headers, so the
algorithm stays portable and independently testable under
`-Wall -Wextra -Werror`; `native/imgprocmodule.c` is the only file that
speaks the CPython ABI.

Both are **optional**. If the extensions aren't built — no compiler, no
`libqpdf-dev` — `native_ops.py` falls back to Pillow and `premium_pdf.py`
to pikepdf. Same features, slower. CI asserts the two paths agree.
`GET /capabilities` reports `imgproc_backend` and `pdf_backend` so you can
check what a deployment actually resolved to rather than assuming.

Build them with `cd backend && python setup.py build_ext --inplace`; the
Dockerfile does it automatically.

### The scan-cleanup kernel

`backend/native/imgproc.c` preprocesses every scanned page before OCR —
grayscale → percentile contrast stretch → inverted-scan detection → Otsu
binarization — in exactly **two passes over the pixels**; everything in
between is computed on a 256-bin histogram and folded into a single
lookup table. Faded scans, photographed documents, and white-on-black
pages all come out clean, which is what actually moves Tesseract's
accuracy. If the shared library isn't built, `native_ops.py` silently
falls back to a pure-Pillow implementation, so the API runs anywhere.

### Run it

```bash
docker compose up -d                 # local: http://localhost:8080
docker compose --profile prod up -d  # production: automatic HTTPS — see deploy/PRODUCTION.md
docker compose --profile ai up -d    # adds Ollama for the local-LLM tools
docker exec -it $(docker compose ps -q ollama) ollama pull llama3.2
```

This starts:
- `frontend` (unprivileged nginx, proxies `/api/*` to the backend so the
  browser only ever talks to one origin — no CORS setup needed)
- `backend` (FastAPI, docs at `/docs`) + `redis` + `worker` — heavy jobs
  (OCR, Office conversion, Ghostscript) run through a queue so the API
  always answers instantly; scale with `--scale worker=N`
- with `--profile prod`: Caddy with automatic Let's Encrypt TLS
- with `--profile ai`: Ollama for the local LLM tools

**Full production guide (VPS quickstart, monitoring, scaling, security
checklist): [deploy/PRODUCTION.md](deploy/PRODUCTION.md).**

The frontend auto-detects the backend at `/api`. Pointing it somewhere
else takes one line in the browser console:
`localStorage.setItem('dockbench.apiBase', 'https://your-server:8000')`.

### Endpoints

- `POST /ocr` — `file`, `language` (default `eng`), `output` (`text` |
  `pdf` for a searchable PDF), `enhance` (C kernel cleanup, default on)
- `POST /convert` — `file`, `target` (`pdf` from any Office format;
  `docx` / `pptx` / `xlsx` from PDF)
- `POST /compress-pdf` — `file`, `level` (`balanced` | `strong` | `extreme`);
  never returns a bigger file than the input
- `POST /pdfa` — `file` → ISO 19005 PDF/A-2b
- `POST /remove-bg` — `file` → transparent PNG
- `POST /summarize` — `text`, `max_words`
- `POST /chat` — `question`, `context` (the frontend extracts text
  on-device and sends only relevant excerpts, never the file)
- `GET /capabilities` — which engines this deployment has (the frontend
  can use it to enable exactly what will work)
- `GET /health` — liveness check

Privacy contract: nothing about file contents or names is ever logged;
pure-Python endpoints work entirely in memory; the engines that require
real files (LibreOffice, Ghostscript) get a private per-request temp
directory deleted the moment the response is built. Rate limits
(10-20/min/IP on heavy endpoints) keep one user from starving the box.
`MAX_FILE_MB` (default 50) caps upload size.

## Production notes

- **Set `ALLOWED_ORIGINS`** in `docker-compose.yml` to your real domain.
- **HTTPS**: put Caddy / nginx + Let's Encrypt or a cloud LB in front.
- **Scale out**: `docker compose up -d --scale backend=3` — Docker's DNS
  round-robins across replicas on one host; use a real LB across hosts.
- **Structured logs**: every request gets an `X-Request-ID`, logged with
  method/path/status/timing only.
- **Health checks** are wired into compose so the frontend won't route to
  a backend that isn't ready.
- **Heavy traffic?** Consider a task queue (Celery/RQ) in front of `/ocr`
  and `/convert` so slow jobs don't hold workers hostage.
- The backend image includes LibreOffice + Ghostscript + Tesseract, so it
  is a few GB — that is the price of full-fidelity conversion with zero
  per-call cost. Strip engines you don't need from `backend/Dockerfile`
  and `/capabilities` will report accordingly.
- Extra OCR languages: add e.g. `tesseract-ocr-deu` to the Dockerfile.

## Business API

The HTTP API is the paid surface; the on-device app is free and unlimited
forever, with no key. Set `REQUIRE_API_KEY=1` (plus a verifying key) and
the processing endpoints require `Authorization: Bearer dkb_live_...`.
`/health` and `/capabilities` stay open for monitoring and discovery.

**A self-hosted backend is never gated** — it's your server. Neither is the
desktop app's bundled engine. Enforcement is opt-in, so nothing changes for
anyone running their own instance.

```bash
node licensing/mint-api-key.js --sub=acme-corp --expires=2027-12-31
```

Keys are ECDSA P-256 signatures over their own payload, using the same
signing identity as the offline licence system. Verification is in-process
against a public key: **no database lookup and no licence server on the
request path**, so it works air-gapped and costs microseconds. Rate limits
bucket by the key's subject rather than by IP.

Full reference: **[deploy/API.md](deploy/API.md)**.

## CI

`.github/workflows/validate.yml` runs on every push:

**Frontend** — JS syntax of the whole inline app; every tool card resolving
to a real function; no duplicate tool names; all 21 vendor assets present
and precached; the base64 WASM copy matching the real binary; every service
worker precache entry existing on disk; every internal link across all 18
pages resolving; manifest icons and screenshots matching their declared
sizes.

**Backend** — `py_compile` of every module; each module imported in its own
process (so a module that only works because another was imported first is
caught); both `main` and `worker` entrypoints; a `-Werror` compile of the C
kernel; a build of both fused extensions plus an equivalence test proving
the extension and its pure-Python fallback agree on merge/rotate/split/
range/watermark and that bad input raises 4xx rather than 500; API keys
minted with the real script and checked against expired, tampered, forged
and garbage variants.

**Functional** — a headless-Chromium job that opens all 104 tools and runs
real PDFs through Merge and Rotate, asserting the downloaded output is a
valid 5-page PDF and a 3-page PDF rotated 90°. Every static check above
once passed on a build whose backend could not start; this is the job that
exercises the product.

`desktop.yml` builds the Windows/macOS/Linux installers and asserts the
bundled engine starts loopback-only, rejects untokened requests, exits with
its parent, and is serving the fused extensions rather than the fallbacks.

## Offline licensing (for deployments with no internet at all)

Ad revenue needs a live connection — there's no way around that, an ad
network has to serve the creative and verify the impression in real time.
For a genuinely offline deployment (a library, a school, a government
office, any air-gapped machine), that path doesn't exist, so Dockbench has
a separate one: a cryptographically signed license key, verified entirely
on-device via the Web Crypto API, no server involved before or after, ever.
Run `node licensing/keygen.js` once (keep `private-key.json` secret, embed
`public-key.json`'s contents in `frontend/index.html`), then
`node licensing/mint.js` to sell licenses — see **licensing/README.md**
for the full walkthrough, including institutional/site licensing for
many offline machines at once.

## Guides & Play Store

`frontend/guides/` has 7 static, plain-language SEO pages ("How do I make a
PDF small enough to email?", "Why can't I select text in my scanned PDF?",
etc.), each ending in a link that deep-links straight into the assistant
with the question pre-filled (`index.html?ask=...`). `frontend/icons/` has
a full PWA/TWA icon set (including maskable variants), a Play Store feature
graphic, and real screenshots of the running app — all generated from the
actual app, not mockups. `twa/twa-manifest.json` plus
`frontend/.well-known/assetlinks.json` are a starting scaffold for
packaging the existing PWA as a Trusted Web Activity; **`deploy/PLAY_STORE.md`**
has the full step-by-step (Bubblewrap, signing, Play Console submission,
draft listing copy) and **`deploy/PRIVACY_POLICY.md`** is a ready-to-host
policy reflecting what the app actually does and doesn't collect.

## Roadmap (not yet built)

- PaddleOCR as a swap-in for better table/multilingual accuracy
- A visual pipeline builder (chain tools like "split → OCR → compress")
- WebGPU acceleration for the on-device AI models as browser support lands
- Fusing Tesseract and Ghostscript into extension modules too, removing the
  last subprocess calls (bigger build surface; measured gain unproven)
