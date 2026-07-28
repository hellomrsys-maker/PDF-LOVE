#!/usr/bin/env python3
"""
Build the bundled engine for the desktop app.

    python desktop/build-engine.py

Three steps:
  1. compile the fused C/C++ extensions (backend/setup.py)
  2. freeze backend/local_engine.py with PyInstaller
  3. rename the result to the target-triple filename Tauri expects for a
     sidecar, e.g. pdflove-engine-x86_64-unknown-linux-gnu

Run this before `npm run tauri build`.
"""

import os
import shutil
import subprocess
import sys
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BACKEND = os.path.join(ROOT, "backend")
BINARIES = os.path.join(HERE, "binaries")


def run(cmd, cwd=None):
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def target_triple() -> str:
    """The triple Tauri appends to sidecar filenames.

    `rustc -vV` is authoritative; fall back to deriving it from Python's
    platform tag so this still works without a Rust toolchain present.
    """
    try:
        out = subprocess.run(["rustc", "-vV"], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            if line.startswith("host:"):
                return line.split(":", 1)[1].strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    plat = sysconfig.get_platform()          # e.g. linux-x86_64, macosx-11-arm64
    machine = "aarch64" if ("arm64" in plat or "aarch64" in plat) else "x86_64"
    if sys.platform.startswith("win"):
        return f"{machine}-pc-windows-msvc"
    if sys.platform == "darwin":
        return f"{machine}-apple-darwin"
    return f"{machine}-unknown-linux-gnu"


def main():
    print("== 1/3  building the fused C/C++ extensions ==")
    run([sys.executable, "setup.py", "build_ext", "--inplace"], cwd=BACKEND)

    print("\n== 2/3  freezing the engine ==")
    os.makedirs(BINARIES, exist_ok=True)
    run([sys.executable, "-m", "PyInstaller", os.path.join(HERE, "engine.spec"),
         "--distpath", BINARIES,
         "--workpath", os.path.join(HERE, "build"),
         "--noconfirm"])

    print("\n== 3/3  naming it for Tauri ==")
    ext = ".exe" if sys.platform.startswith("win") else ""
    src = os.path.join(BINARIES, "pdflove-engine" + ext)
    if not os.path.exists(src):
        sys.exit(f"PyInstaller did not produce {src}")

    dst = os.path.join(BINARIES, f"pdflove-engine-{target_triple()}{ext}")
    shutil.move(src, dst)
    os.chmod(dst, 0o755)

    size_mb = os.path.getsize(dst) / (1024 * 1024)
    print(f"\nBuilt {dst} ({size_mb:.1f} MB)")
    print("Next:  cd desktop && npm run tauri build")


if __name__ == "__main__":
    main()
