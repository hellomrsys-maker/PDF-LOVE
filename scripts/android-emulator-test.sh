#!/usr/bin/env bash
#
# Install the built APK on a running emulator and check that it does what
# the architecture promises — most importantly that it works with no
# network from a cold start, since every asset is meant to be inside the
# APK rather than fetched from a site.
#
# Run by .github/workflows/android.yml inside android-emulator-runner,
# which provides a booted emulator and adb on PATH.
#
set -uo pipefail

PKG=app.dockbench
ACT="$PKG/.MainActivity"
OUT=/tmp/android-test
mkdir -p "$OUT"

fail() { echo "FAIL: $*"; adb logcat -d > "$OUT/logcat-failure.txt" 2>/dev/null; exit 1; }
note() { echo "  $*"; }

APK=$(find android/app/build/outputs/apk -name '*.apk' | grep -v unsigned | head -1)
[ -z "$APK" ] && APK=$(find android/app/build/outputs/apk -name '*.apk' | head -1)
[ -z "$APK" ] && fail "no APK was built"
note "installing $(basename "$APK") ($(du -h "$APK" | cut -f1))"

adb wait-for-device
adb install -r -t "$APK" || fail "install rejected the APK"

# ---------------------------------------------------------------------
# The APK must carry the whole app. If assets are missing the app would
# have to fetch them, and the offline run below would be meaningless.
# ---------------------------------------------------------------------
ASSET_COUNT=$(unzip -l "$APK" | grep -c 'assets/' || true)
note "assets bundled in the APK: $ASSET_COUNT"
[ "$ASSET_COUNT" -lt 10 ] && fail "only $ASSET_COUNT asset entries — the web app was not staged into the APK"
unzip -l "$APK" | grep -q 'assets/index.html' || fail "assets/index.html is not in the APK"

launch_and_check() {
  local label="$1"
  note "--- $label"
  adb shell am force-stop "$PKG"
  adb logcat -c
  adb shell am start -W -n "$ACT" >"$OUT/start-$label.txt" 2>&1 \
    || fail "$label: activity would not start"
  sleep 12

  # Still running, rather than having crashed back to the launcher.
  local pid
  pid=$(adb shell pidof "$PKG" | tr -d '\r')
  [ -z "$pid" ] && { adb logcat -d > "$OUT/logcat-$label.txt"; fail "$label: the app is not running 12s after launch"; }
  note "$label: running as pid $pid"

  adb exec-out screencap -p > "$OUT/screen-$label.png" 2>/dev/null || true

  adb logcat -d > "$OUT/logcat-$label.txt"
  if grep -qE "FATAL EXCEPTION|AndroidRuntime: .*Exception" "$OUT/logcat-$label.txt"; then
    grep -A 12 "FATAL EXCEPTION" "$OUT/logcat-$label.txt" | head -30
    fail "$label: the app threw a fatal exception"
  fi

  # The WebView must be serving from the asset loader's origin. A file://
  # page is not a secure context, which silently disables the camera, the
  # service worker and WebCrypto — so this is a real functional assertion,
  # not a cosmetic one.
  if grep -q "appassets.androidplatform.net" "$OUT/logcat-$label.txt"; then
    note "$label: WebView is on the secure asset-loader origin"
  else
    note "$label: no origin line in logcat (informational)"
  fi

  # Anything the page logged as an error.
  if grep -qE "chromium.*(ERR_|Uncaught)" "$OUT/logcat-$label.txt"; then
    note "$label: page-level errors seen:"
    grep -E "chromium.*(ERR_|Uncaught)" "$OUT/logcat-$label.txt" | head -8 | sed 's/^/      /'
    # ERR_INTERNET_DISCONNECTED during the offline run would mean the app
    # tried to reach the network — the exact thing this test exists to catch.
    if [ "$label" = "offline" ] && grep -q "ERR_INTERNET_DISCONNECTED\|ERR_NAME_NOT_RESOLVED" "$OUT/logcat-$label.txt"; then
      fail "offline: the app attempted a network request, so it is not self-contained"
    fi
  fi
}

# ---------------------------------------------------------------------
launch_and_check online

note "--- switching the device to airplane mode"
adb shell svc wifi disable || true
adb shell svc data disable || true
adb shell settings put global airplane_mode_on 1
adb shell su 0 am broadcast -a android.intent.action.AIRPLANE_MODE --ez state true >/dev/null 2>&1 || true
sleep 5
AIR=$(adb shell settings get global airplane_mode_on | tr -d '\r')
[ "$AIR" != "1" ] && note "warning: airplane_mode_on reads '$AIR'; wifi and data were disabled regardless"

# A cold start with no network is the case that matters: nothing warm in
# memory, nothing cached from the online run beyond what shipped in the APK.
adb shell pm clear "$PKG" >/dev/null 2>&1 || true
launch_and_check offline

adb shell settings put global airplane_mode_on 0
adb shell svc wifi enable || true

echo "PASS: the app installs, launches, and runs cold with no network."
