"""
native_ops — the C image kernel, exposed as one call: `enhance_for_ocr(img)`.

It runs the scan-cleanup pipeline used before Tesseract:

    grayscale -> percentile contrast stretch -> flip inverted scans
    -> Otsu binarization

in exactly two passes over the pixels; everything in between operates on a
256-bin histogram, so a 300-DPI A4 page cleans up in tens of milliseconds.

Three implementations, tried in order, all producing identical output:

  1. dockbench_imgproc  — compiled CPython extension. The whole pipeline is
     one call and the GIL is released during it, so pages of a scanned PDF
     binarize in parallel across cores. This is the path that ships.
  2. imgproc.so via ctypes — the older bridge. Kept because it works with a
     bare `gcc -shared` and no Python headers, which is a convenient escape
     hatch when the extension can't be built.
  3. Pure Pillow — no compiler needed at all.

Nothing here ever requires the network.
"""

import ctypes
import logging
import os

logger = logging.getLogger("dockbench.native")

# Preferred path: the fused extension (see native/imgprocmodule.c).
try:
    import dockbench_imgproc as _ext
    logger.info("Fused C image kernel loaded (dockbench_imgproc)")
except ImportError:
    _ext = None

_LIB_PATHS = (
    os.path.join(os.path.dirname(__file__), "native", "imgproc.so"),
    os.path.join(os.path.dirname(__file__), "imgproc.so"),
)

_lib = None
for _path in _LIB_PATHS:
    if os.path.exists(_path):
        try:
            _lib = ctypes.CDLL(_path)
            break
        except OSError as e:  # wrong arch, corrupt file, ...
            logger.warning("Could not load %s: %s", _path, e)

if _lib is not None:
    _u8p = ctypes.POINTER(ctypes.c_uint8)
    _u64p = ctypes.POINTER(ctypes.c_uint64)
    # Read-only source buffers are passed as c_char_p so Python bytes
    # objects go through zero-copy; writable buffers via from_buffer.
    _lib.gray_and_hist.argtypes = [ctypes.c_char_p, _u8p, ctypes.c_size_t, ctypes.c_int, _u64p]
    _lib.gray_and_hist.restype = None
    _lib.hist_only.argtypes = [ctypes.c_char_p, ctypes.c_size_t, _u64p]
    _lib.hist_only.restype = None
    _lib.build_lut.argtypes = [_u64p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, _u8p]
    _lib.build_lut.restype = ctypes.c_int
    _lib.apply_lut.argtypes = [_u8p, ctypes.c_size_t, _u8p]
    _lib.apply_lut.restype = None
    logger.info("Native C image kernel loaded (imgproc.so)")


def native_available() -> bool:
    """True when any compiled C path is in use (fused extension or ctypes)."""
    return _ext is not None or _lib is not None


def native_backend() -> str:
    """Which implementation enhance_for_ocr will actually use — reported by
    /capabilities so a deployment can be checked without guessing."""
    if _ext is not None:
        return "extension"
    if _lib is not None:
        return "ctypes"
    return "pillow"


def enhance_for_ocr(img):
    """Take a PIL image of a scanned page, return a cleaned 1-band PIL
    image ready for Tesseract. Uses the fastest available C path."""
    from PIL import Image

    if _ext is not None:
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        w, h = img.size
        if w * h == 0:
            return img.convert("L")
        channels = {"L": 1, "RGB": 3, "RGBA": 4}[img.mode]
        # One boundary crossing for the whole pipeline, GIL released inside.
        out = _ext.enhance(img.tobytes(), w, h, channels)
        return Image.frombytes("L", (w, h), out)

    if _lib is None:
        return _enhance_pillow(img)

    if img.mode not in ("RGB", "RGBA", "L"):
        img = img.convert("RGB")
    w, h = img.size
    npix = w * h
    if npix == 0:
        return img.convert("L")

    hist = (ctypes.c_uint64 * 256)()
    if img.mode == "L":
        gray = bytearray(img.tobytes())
        gbuf = (ctypes.c_uint8 * npix).from_buffer(gray)
        _lib.hist_only(bytes(gray), npix, hist)
    else:
        channels = 4 if img.mode == "RGBA" else 3
        gray = bytearray(npix)
        gbuf = (ctypes.c_uint8 * npix).from_buffer(gray)
        _lib.gray_and_hist(img.tobytes(), gbuf, npix, channels, hist)

    lut = (ctypes.c_uint8 * 256)()
    _lib.build_lut(hist, npix, 5, 995, lut)
    _lib.apply_lut(gbuf, npix, lut)
    del gbuf  # release the from_buffer view so `gray` can be exported

    return Image.frombytes("L", (w, h), bytes(gray))


def _enhance_pillow(img):
    """Pure-Pillow fallback: the same pipeline via Pillow's own C ops."""
    from PIL import Image, ImageOps

    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    hist = gray.histogram()
    total = sum(hist) or 1
    mean = sum(i * c for i, c in enumerate(hist)) / total
    if mean < 100:  # inverted scan (light text on dark)
        gray = ImageOps.invert(gray)
        hist = gray.histogram()
    threshold = _otsu_py(hist, total)
    return gray.point(lambda v: 255 if v > threshold else 0)


def _otsu_py(hist, total):
    """Otsu's threshold from a 256-bin histogram — fallback path."""
    total_sum = sum(i * c for i, c in enumerate(hist))
    sum_b = w_b = 0.0
    max_var, threshold = 0.0, 127
    for t in range(256):
        w_b += hist[t]
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * hist[t]
        m_b = sum_b / w_b
        m_f = (total_sum - sum_b) / w_f
        between = w_b * w_f * (m_b - m_f) ** 2
        if between > max_var:
            max_var, threshold = between, t
    return threshold
