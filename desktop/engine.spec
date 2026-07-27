# PyInstaller spec for the bundled Dockbench engine.
#
#   pyinstaller desktop/engine.spec --distpath desktop/binaries
#
# Produces a single executable that the Tauri shell launches as a sidecar.
# Tauri requires the target triple in the filename (dockbench-engine-x86_64-
# unknown-linux-gnu, etc.); desktop/build-engine.py renames it afterwards.
#
# What has to be forced in:
#   * the compiled extensions (dockbench_imgproc / dockbench_pdf) — they are
#     .so/.pyd files loaded by name, so PyInstaller's import graph misses them
#   * uvicorn's worker/protocol modules, which it imports by string
#   * the engine modules main.py imports at call time rather than at module
#     scope

import os
import sys
import glob

BACKEND = os.path.abspath(os.path.join(SPECPATH, '..', 'backend'))

# The fused extensions, built by `python setup.py build_ext --inplace`.
binaries = []
for pattern in ('dockbench_imgproc*', 'dockbench_pdf*'):
    for path in glob.glob(os.path.join(BACKEND, pattern)):
        if path.endswith(('.so', '.pyd', '.dylib')):
            binaries.append((path, '.'))

if not binaries:
    sys.stderr.write(
        "\n*** No compiled extensions found in backend/.\n"
        "*** Run: cd backend && python setup.py build_ext --inplace\n"
        "*** The engine will still work via the Pillow/pikepdf fallbacks,\n"
        "*** but every PDF and OCR operation will be slower.\n\n"
    )

a = Analysis(
    [os.path.join(BACKEND, 'local_engine.py')],
    pathex=[BACKEND],
    binaries=binaries,
    datas=[],
    hiddenimports=[
        # Imported by string at runtime, so not in the import graph.
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        # Deferred imports inside engines.py / main.py.
        'fitz',
        'pytesseract',
        'pdf2docx',
        'pptx',
        'openpyxl',
        'httpx',
        'PIL.Image',
        'PIL.ImageOps',
        'cryptography.hazmat.primitives.asymmetric.ec',
        # Our own modules, reached through main.py.
        'engines', 'premium_pdf', 'batch_pdf', 'ai_helper',
        'native_ops', 'apikeys', 'errors', 'worker',
        'dockbench_imgproc', 'dockbench_pdf',
    ],
    excludes=[
        # Large and unused in the local engine: it never renders plots or
        # trains anything, and arq/redis only matter in the queued topology.
        'tkinter', 'matplotlib', 'notebook', 'IPython', 'pytest',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='dockbench-engine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX-packed binaries trip antivirus heuristics
    console=True,       # the handshake line goes to stdout
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
