# Dockbench on the Play Store

The Android app is a **WebView app that bundles the entire web application
inside the APK** (see `android/README.md`). It is not a Trusted Web
Activity, and this is a deliberate change from the earlier scaffold.

## Why not a TWA

A TWA loads `https://dockbench.app` in Chrome. That means:

- **First launch needs a network connection**, and every launch is a
  request to our server — which contradicts the product's central promise
  that everything runs on the user's own device.
- It depends on Digital Asset Links verification against a live domain. If
  that breaks, the user sees a browser address bar inside "the app".

The current build serves the bundled assets through `WebViewAssetLoader`
over an `https://appassets.androidplatform.net` origin. That keeps the page
in a secure context — required for the camera, the service worker and
WebCrypto — while making the app fully offline from the moment it installs
and removing the need for `assetlinks.json` entirely.

The old `twa/twa-manifest.json` and `frontend/.well-known/assetlinks.json`
have been removed; both carried placeholder values and neither applies to
this build.

## What's already done for you

- `android/` — a complete Gradle project: manifest, activity, theme,
  ProGuard rules, signing wired to CI secrets.
- `.github/workflows/android.yml` — builds a signed APK and AAB on tag,
  and a debug build on every PR touching Android or the frontend.
- `scripts/build-android-assets.py` — stages `frontend/dist/` into the APK
  and generates the launcher icon set from `frontend/icons/icon-512.png`.
- `frontend/icons/` — full icon set (48–512px, plus maskable 192/512), a
  1024×500 feature graphic, a 512×512 Play Store icon, and 4 real
  screenshots of the running app — all generated from the actual app.
- `frontend/download.html` — a public download page offering the APK
  directly alongside the Play listing and the desktop installers.

## What only you can do (needs accounts/keys I have no access to)

1. A Play Console account ($25 one-off). The app itself no longer requires
   a live domain — it bundles its own assets — but a domain is still needed
   for the privacy-policy URL Play demands. (Historically a TWA required
   point at `localhost` or a file). Every placeholder below uses
   `dockbench.app` — replace with your real domain everywhere.
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
# One-off: create a signing key and back it up somewhere safe.
keytool -genkeypair -v -keystore dockbench.keystore \
  -alias dockbench -keyalg RSA -keysize 4096 -validity 10000

# Store it for CI (never commit the keystore itself):
base64 -w0 dockbench.keystore    # -> secret ANDROID_KEYSTORE_BASE64
```

Set these repository secrets so `.github/workflows/android.yml` can sign:

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | the base64 above |
| `ANDROID_KEYSTORE_PASSWORD` | the store password |
| `ANDROID_KEY_ALIAS` | `dockbench` |
| `ANDROID_KEY_PASSWORD` | the key password |

Then tag a release and CI produces a signed `.apk` and `.aab`. To build
locally instead:

```bash
python scripts/build-android-assets.py
cd android && ./gradlew bundleRelease
```

**No `assetlinks.json` step.** That file exists to prove domain ownership
for a TWA; this build serves its own bundled assets and never loads the
site, so there is nothing to verify. Losing the keystore means you can
never update the app under the same listing — back it up.

### 4. Upload to Play Console

- Create the app listing, upload the `.aab` from step 3.
- Feature graphic: `frontend/icons/feature-graphic-1024x500.png`
- App icon: `frontend/icons/play-store-icon-512.png`
- Screenshots: the 4 PNGs in `frontend/icons/screenshot-*.png` (phone
  size, real captures of the running app)
- Listing copy: see below.
- Privacy policy URL: host `deploy/PRIVACY_POLICY.md` (or its content)
  at a public URL — Play Console requires this field, and Dockbench's
  actual policy ("we don't collect anything") is a genuine selling point,
  not boilerplate.
- Content rating questionnaire: Dockbench has no user-generated content
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

**Title** (30 char max): `Dockbench — Free PDF Tools`

**Short description** (80 char max):
`103 free PDF/image tools. No login, no upload — runs on your device.`

**Full description:**

> Dockbench is a free PDF, image, and video toolbox that runs entirely on
> your device — merging, splitting, compressing, converting, OCR, even
> AES-256 encryption, all without uploading your file anywhere.
>
> No account. No login for individuals, ever. No daily limit. No
> subscription. Just tell Dockbench what you need in your own words —
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
> Dockbench is open-source. Audit it, self-host the optional backend for
> advanced tools (full-fidelity Office conversion, deep compression), or
> just use the free web app as-is.

**Category:** Productivity (or Tools)

**Content rating:** Everyone (no user-generated content sharing, no ads
by default, no account system)
