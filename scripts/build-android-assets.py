#!/usr/bin/env python3
"""
Stage the web app into the Android project's assets, and generate the
launcher icon set.

    python scripts/build-android-assets.py

Copies frontend/dist/ (or frontend/ if the minified build has not been run)
into android/app/src/main/assets/www/. That directory is generated and
git-ignored — never edit it by hand.

The APK therefore contains the entire application. It makes no network
request to load itself, on first launch or any launch.
"""

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(ROOT, "frontend")
DIST = os.path.join(FRONTEND, "dist")
ASSETS = os.path.join(ROOT, "android", "app", "src", "main", "assets", "www")
RES = os.path.join(ROOT, "android", "app", "src", "main", "res")

# Not useful inside the APK: nginx config, Docker build inputs, the TWA
# verification file (this build is not a TWA), and the service worker —
# assets are already local, so a cache layer on top of them is pure overhead
# and a source of stale-content bugs.
EXCLUDE_FILES = {"Dockerfile", "nginx.conf", "_headers", "sw.js"}
EXCLUDE_DIRS = {".well-known", "dist"}

# Launcher icon densities, and the source width each needs.
MIPMAPS = [("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)]


def stage_assets():
    src = DIST if os.path.isdir(DIST) else FRONTEND
    if src == FRONTEND:
        print("note: frontend/dist not found — bundling unminified source.")
        print("      run `node build.mjs` first for a smaller APK.")

    if os.path.isdir(ASSETS):
        shutil.rmtree(ASSETS)
    os.makedirs(ASSETS)

    total = 0
    for dirpath, dirnames, filenames in os.walk(src):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        rel = os.path.relpath(dirpath, src)
        target_dir = ASSETS if rel == "." else os.path.join(ASSETS, rel)
        os.makedirs(target_dir, exist_ok=True)
        for fn in filenames:
            if fn in EXCLUDE_FILES:
                continue
            shutil.copy2(os.path.join(dirpath, fn), os.path.join(target_dir, fn))
            total += os.path.getsize(os.path.join(dirpath, fn))

    print(f"staged {src} -> {ASSETS} ({total / 1048576:.1f} MB)")

    index = os.path.join(ASSETS, "index.html")
    if not os.path.isfile(index):
        sys.exit("FAIL: index.html did not make it into the assets directory.")
    return total


def build_icons():
    """Generate the launcher icon set from the existing 512px app icon."""
    try:
        from PIL import Image
    except ImportError:
        print("note: Pillow not installed — skipping icon generation.")
        return

    source = os.path.join(FRONTEND, "icons", "icon-512.png")
    if not os.path.isfile(source):
        print(f"note: {source} missing — skipping icon generation.")
        return

    img = Image.open(source).convert("RGBA")
    for density, size in MIPMAPS:
        out_dir = os.path.join(RES, f"mipmap-{density}")
        os.makedirs(out_dir, exist_ok=True)
        resized = img.resize((size, size), Image.LANCZOS)
        resized.save(os.path.join(out_dir, "ic_launcher.png"))
        # Round variant: same art. Android masks it; supplying a
        # pre-rounded bitmap would double-round on most launchers.
        resized.save(os.path.join(out_dir, "ic_launcher_round.png"))
    print(f"generated launcher icons for {len(MIPMAPS)} densities")


def main():
    size = stage_assets()
    build_icons()
    print("\nNext: cd android && ./gradlew assembleRelease")
    if size > 100 * 1048576:
        print(f"warning: {size / 1048576:.0f} MB of assets — Play's APK limit "
              "is 100 MB (AAB with asset packs goes higher).")


if __name__ == "__main__":
    main()
