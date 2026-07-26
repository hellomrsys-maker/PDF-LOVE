"""
Build the fused native extensions.

    python setup.py build_ext --inplace

produces two importable CPython modules that run inside the interpreter
process rather than behind a bridge:

  dockbench_imgproc   scan-cleanup kernel  (was: ctypes -> imgproc.so)
  dockbench_pdf       PDF operations       (was: subprocess -> qpdf CLI)

Both are optional. native_ops.py and premium_pdf.py fall back to Pillow and
pikepdf respectively when an extension is missing, so the backend still runs
on a machine with no compiler or no libqpdf headers — the fallbacks are
slower, not different.

dockbench_pdf needs libqpdf's headers (Debian/Ubuntu: libqpdf-dev). If they
are absent the build of that one extension is skipped rather than failing
the whole install; see build_ext.run below.
"""

import sys

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext as _build_ext

IS_WIN = sys.platform.startswith("win")

# -O3 matters here: the image kernel is a tight per-pixel loop.
C_FLAGS = [] if IS_WIN else ["-O3", "-Wall", "-Wextra"]
CXX_FLAGS = ["/std:c++17"] if IS_WIN else ["-O3", "-std=c++17", "-Wall", "-Wextra"]

imgproc = Extension(
    "dockbench_imgproc",
    # imgproc.c is the pure algorithm and includes no Python headers, so it
    # stays independently compilable and testable; the module file is the
    # only part that speaks the CPython ABI.
    sources=["native/imgproc.c", "native/imgprocmodule.c"],
    extra_compile_args=C_FLAGS,
)

pdfops = Extension(
    "dockbench_pdf",
    sources=["native/pdfops.cpp"],
    libraries=["qpdf"],
    language="c++",
    extra_compile_args=CXX_FLAGS,
)


class build_ext(_build_ext):
    """Build each extension independently so a missing optional system
    library degrades to a fallback instead of breaking the whole build."""

    def run(self):
        _build_ext.run(self)

    def build_extension(self, ext):
        try:
            super().build_extension(ext)
        except Exception as e:
            if ext.name == "dockbench_pdf":
                sys.stderr.write(
                    f"\n*** Skipping {ext.name}: {e}\n"
                    "*** Install libqpdf-dev for the in-process PDF engine. "
                    "Falling back to pikepdf.\n\n"
                )
                return
            raise


setup(
    name="dockbench-native",
    version="0.4.0",
    description="Fused C/C++ extensions for the Dockbench engine.",
    ext_modules=[imgproc, pdfops],
    cmdclass={"build_ext": build_ext},
    zip_safe=False,
)
