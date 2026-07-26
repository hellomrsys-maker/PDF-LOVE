from setuptools import setup, Extension
import sys
import os

# Determine include and library directories for qpdf. Adjust if needed.
include_dirs = []
library_dirs = []
libraries = ["qpdf"]

# On Windows, the library may be named qpdf.lib and headers in typical locations.
if sys.platform.startswith("win"):
    # Attempt to locate qpdf via environment variables or common install paths
    qpdf_root = os.environ.get("QPDF_ROOT")
    if qpdf_root:
        include_dirs.append(os.path.join(qpdf_root, "include"))
        library_dirs.append(os.path.join(qpdf_root, "lib"))
    else:
        # Fallback: assume qpdf is in a standard location (e.g., vcpkg)
        include_dirs.append(r"C:\\vcpkg\\installed\\x64-windows\\include")
        library_dirs.append(r"C:\\vcpkg\\installed\\x64-windows\\lib")

pdf_merge_module = Extension(
    name="pdf_merge",
    sources=[os.path.join("backend", "pdf_merge.c")],
    include_dirs=include_dirs,
    library_dirs=library_dirs,
    libraries=libraries,
    language="c++",
    extra_compile_args=["-std=c++11"] if not sys.platform.startswith("win") else [],
)

setup(
    name="pdf_merge",
    version="0.1",
    description="Zero‑bridge PDF merge implemented in C using libqpdf",
    ext_modules=[pdf_merge_module],
    zip_safe=False,
)
