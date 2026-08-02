# PDFLove on the Play Store (TWA)

PDFLove is already an installable PWA (`frontend/manifest.json` +
`frontend/sw.js`). A **Trusted Web Activity (TWA)** wraps that same PWA in a
thin native Android shell — no app code to write or maintain, no
Play-Store-specific fork of the app. Everything in this doc assumes the
scaffold already in the repo (`twa/twa-manifest.json`,
`frontend/.well-known/assetlinks.json`, `frontend/icons/`).

## What's already done for you

- `frontend/icons/` — full icon set (48–512px, plus maskable 192/512),
  a 1024×500 feature graphic, a 512×512 Play Store icon, and 4 real
  screenshots of the running app (hero, tool grid, the assistant mid-plan,
  a tool panel) — all generated from the actual app, not mockups.
- `frontend/manifest.json` — updated to reference the real PNG icons.
- `frontend/sw.js` — precaches the new icons (cache bumped to `v5`).
- `frontend/.well-known/assetlinks.json` — the Digital Asset Links file
  Android checks to confirm you (not an impersonator) own both the app and
  the domain. Ships with placeholders — see step 3.
- `twa/twa-manifest.json` — a best-effort starting config in Bubblewrap's
  format. **Bubblewrap's own `init` command (step 2) is the authoritative
  way to generate this file** — treat the committed one as a reference/
  starting point, not a guarantee of matching whatever Bubblewrap version
  you install, since its schema has changed across releases.

## What only you can do (needs accounts/keys I have no access to)

1. A real production domain serving `frontend/` over HTTPS (TWA requires
   Digital Asset Links verification against a live domain — it cannot
   point at `localhost` or a file). Every placeholder below uses
   `pdflove.co.in` — replace with your real domain everywhere.
2. A Google Play Console developer account ($25 one-time fee,
   play.google.com/console).
3. A signing key you generate and **back up somewhere safe, forever** —
   losing it means you can never publish an update to the same app listing
   again. Play App Signing (Google-managed) is the safer default for new
   apps; the steps below use it.

## Step-by-step

### 1. Deploy the site

Host `frontend/` at your real domain (any of the methods in the main
README — static host, or `docker compose --profile prod up -d` per
`deploy/PRODUCTION.md`). Confirm `https://yourdomain/manifest.json` and
`https://yourdomain/index.html` both load before continuing — Bubblewrap
reads the live manifest, not this repo.

### 2. Install Bubblewrap and initialize

```bash
npm install -g @bubblewrap/cli
bubblewrap init --manifest="https://yourdomain/manifest.json"
```

Answer its prompts (package ID, app name, colors) — it will suggest
sensible defaults read from your live manifest. This generates the real
Android project (Gradle files, etc.) that `twa/twa-manifest.json` in this
repo is a preview of; let Bubblewrap's generated files be the source of
truth, and diff them against the committed reference if anything looks off.

### 3. Build and get your signing key's fingerprint

```bash
bubblewrap build
```

This creates `android.keystore` (your signing key — **back this up**) and
prints the app bundle path plus your key's SHA-256 fingerprint. Take that
fingerprint and your final package ID (e.g. `in.co.pdflove.twa`), and
update `frontend/.well-known/assetlinks.json` on your live domain:

```json
[{
  "relation": ["delegate_permission/common.handle_all_urls"],
  "target": {
    "namespace": "android_app",
    "package_name": "in.co.pdflove.twa",
    "sha256_cert_fingerprints": ["YOUR:ACTUAL:FINGERPRINT:HERE"]
  }
}]
```

Verify it's live and correct:
```bash
curl https://yourdomain/.well-known/assetlinks.json
```
(Google also has a Statement List Generator/validator tool if you want a
second check before submitting.)

### 4. Upload to Play Console

- Create the app listing, upload the `.aab` from step 3.
- Feature graphic: `frontend/icons/feature-graphic-1024x500.png`
- App icon: `frontend/icons/play-store-icon-512.png`
- Screenshots: the 4 PNGs in `frontend/icons/screenshot-*.png` (phone
  size, real captures of the running app)
- Listing copy: see below.
- Privacy policy URL: host `deploy/PRIVACY_POLICY.md` (or its content)
  at a public URL — Play Console requires this field, and PDFLove's
  actual policy ("we don't collect anything") is a genuine selling point,
  not boilerplate.
- Content rating questionnaire: PDFLove has no user-generated content
  sharing, no ads by default (until you configure `AD_CONFIG` in
  `frontend/index.html`), no data collection — answer accordingly.
- Data safety section: declare **no data collected** (true as shipped) —
  if you later enable `AD_CONFIG`, revisit this section since ad networks
  typically collect device/usage data of their own.

### 5. Updates

Bump `appVersionName`/`appVersionCode` in your Bubblewrap-generated
manifest and re-run `bubblewrap build` for each release — the web content
itself updates instantly for existing installs (it's the same PWA,
service-worker-cached), so most feature changes need **no new Play Store
submission at all**. Only bump the Android wrapper for TWA-level changes
(icon, manifest fields, minimum Chrome version, etc.).

## Store listing copy (draft — edit freely)

**Title** (30 char max): `PDFLove — Free PDF Tools`

**Short description** (80 char max):
`103 free PDF/image tools. No login, no upload — runs on your device.`

**Full description:**

> PDFLove is a free PDF, image, and video toolbox that runs entirely on
> your device — merging, splitting, compressing, converting, OCR, even
> AES-256 encryption, all without uploading your file anywhere.
>
> No account. No login for individuals, ever. No daily limit. No
> subscription. Just tell PDFLove what you need in your own words —
> "make this small enough to email," "turn my photos into one PDF" — and
> it picks the right tool and walks you through it.
>
> • 103 tools: merge, split, compress, redact, sign, encrypt, OCR,
>   background removal, video-to-GIF, and more
> • Works offline after first load — no internet required
> • Your files never leave your device for on-device tools — verify it
>   yourself, the code is open-source
> • No watermarks, no forced ads, no "2 files a day" limit
> • Multi-language input support (English, Spanish, Hindi) for the
>   built-in assistant
>
> PDFLove is open-source. Audit it, self-host the optional backend for
> advanced tools (full-fidelity Office conversion, deep compression), or
> just use the free web app as-is.

**Category:** Productivity (or Tools)

**Content rating:** Everyone (no user-generated content sharing, no ads
by default, no account system)
