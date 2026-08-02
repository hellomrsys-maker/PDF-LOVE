# PDFLove Desktop

A **real installed application** — not a browser shortcut to a website.

This is the answer to the failure where the installed PWA showed
*"This site can't be reached — ERR_FAILED"* when opened offline. A PWA is
bound to an origin: if that origin is unreachable and the service worker has
not activated with a warm cache, the app cannot open. The desktop build has
no origin at all.

| | Website / PWA | Desktop app |
|---|---|---|
| Loads from | `https://pdflove.co.in` | `file://` on your disk |
| Needs a host to resolve | yes | **no** |
| Service worker | yes | none — nothing to cache |
| Works on a machine that has never been online | after a first online visit | **always** |
| Can show "site can't be reached" | yes | **impossible** |
| Outbound network | allowed | **blocked at session level** |

## Building

```bash
cd desktop
npm install
npm start            # run it locally
npm run dist:win     # Windows: NSIS installer + portable .exe
npm run dist:mac     # macOS: .dmg (x64 + arm64)
npm run dist:linux   # Linux: AppImage + .deb
```

Installers land in `desktop/dist/`.

Each of those runs `scripts/bundle.js` first, which copies `../frontend`
into `desktop/app/` and adapts it for a packaged app:

- removes the service-worker registration (there is no origin to cache for)
- removes the web app manifest link and the Install button — it *is* installed
- hides the ad slots and the web-only update control
- tags `<body data-build="desktop">` so the page can adapt

The bundler **fails the build** if a service worker registration or manifest
link survives into the packaged output.

`desktop/app/` is generated and git-ignored. Never edit it by hand — change
`frontend/` and rebuild.

## Network policy

`main.js` installs a session-level `onBeforeRequest` filter that cancels
every request that is not `file:`, `blob:`, `data:` or `devtools:`. Even a
bug or a third-party script in the page cannot reach the network.

The single exception is **Help → Check for updates**, which the *main*
process performs with `https` — never the page. It fetches a small version
file, tells you whether a newer build exists, and offers to open the
download page in your normal browser. Declining changes nothing; the
installed copy keeps working forever.

## Verifying it

```bash
xvfb-run -a node scripts/smoke.js     # headless, no display needed
```

Asserts the app opens from `file://`, all tool cards render, a real
two-file PDF merge produces the expected page count, no service worker
controls the page, no manifest link is present, and an outbound `fetch()`
from the renderer is blocked.

## Icons

`build/icon.png` (512×512) is used for Linux and as the window icon. For
signed Windows and macOS builds add `build/icon.ico` and `build/icon.icns`;
electron-builder falls back to the PNG if they are absent.
