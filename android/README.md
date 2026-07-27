# Dockbench for Android

A WebView app that **ships the entire application inside the APK**. Nothing
is fetched from a server — not on first launch, not ever.

## Why this is not a TWA

`twa/twa-manifest.json` scaffolded a Trusted Web Activity, which is the
usual way to put a PWA on the Play Store. It was the wrong choice here:

- A TWA loads `https://dockbench.app` in Chrome. **First launch requires a
  network connection**, and every launch is a request to our server. That
  contradicts the product's central promise.
- It depends on the site staying up, and on `assetlinks.json` verification;
  if either breaks the user sees a browser address bar inside "the app".

Instead this is a plain `WebView` fed by **`WebViewAssetLoader`**, which
serves files bundled in the APK over `https://appassets.androidplatform.net/`.
Two things fall out of that:

1. **Fully offline from the moment it installs.** The tools are in the APK.
2. **It is still a secure context** (`https://` origin), which the camera
   (`getUserMedia`), the service worker, and WebCrypto all require. Loading
   from `file://` would silently disable every one of them — this is the
   detail that makes the approach work at all.

## Layout

```
android/
├── app/
│   ├── build.gradle
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/app/dockbench/MainActivity.java
│       ├── assets/www/            ← frontend/dist, copied at build time
│       └── res/                   ← icons, strings, theme
├── build.gradle
└── settings.gradle
```

`app/src/main/assets/www/` is generated — never edit it, and it is
git-ignored. `scripts/build-android-assets.py` populates it from
`frontend/dist/` (falling back to `frontend/` if the minified build has not
been produced).

## Building

Needs JDK 17+ and the Android SDK (API 34).

```bash
python scripts/build-android-assets.py    # stage the web app into assets/
cd android
./gradlew assembleRelease                 # APK
./gradlew bundleRelease                   # AAB for Play
```

Unsigned builds land in `app/build/outputs/`. CI signs them from repository
secrets — see `.github/workflows/android.yml`.

## Permissions, and why each one exists

| Permission | Why | When asked |
|---|---|---|
| `CAMERA` | Document scanner | Only when the scanner is opened |
| `INTERNET` | Ads and the optional AI model download | Not needed for tools |

There is deliberately no storage permission: the Storage Access Framework
handles file open/save without one, so the app never gets blanket access to
the user's files.

`INTERNET` is declared but the app makes no request of its own. It is
required because a `WebView` cannot load *any* remote subresource without
it — including an ad — and because the on-device AI models download once
from their public host if the user opens one of those tools.

## Before shipping

- [ ] Real icons in `app/src/main/res/mipmap-*` (`icons/icon-512.png` is the
      source; Android Studio's Image Asset tool generates the set)
- [ ] A signing keystore, with `ANDROID_KEYSTORE_BASE64` and
      `ANDROID_KEYSTORE_PASSWORD` set as repository secrets
- [ ] Bump `versionCode` for every Play upload — Play rejects duplicates
- [ ] Play Data Safety: declare "no data collected" for the app itself, and
      whatever the ad network collects if ads are enabled
