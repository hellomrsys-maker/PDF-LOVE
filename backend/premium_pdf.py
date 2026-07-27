"""
premium_pdf — page-level PDF operations (merge, split, rotate, watermark).

Two axes here: which engine, and whether the document is held in memory.

Engine, tried in order:
  1. dockbench_pdf — libqpdf linked straight into the interpreter. Measured
     ~6x faster than shelling out to the qpdf CLI for a 200-page split,
     because it does not fork+exec (and round-trip through the filesystem)
     once per page.
  2. pikepdf — the same qpdf engine behind a Python wrapper. Always present
     as a declared dependency, so the fallback is a slowdown, never a
     missing feature.

Memory model:
  * bytes in / bytes out for everyday files — fewer syscalls, no temp files.
  * **path in / path out** once a document is large. qpdf resolves objects
    lazily from disk and streams them back out, so peak memory tracks the
    object model rather than the file. Measured: merging four copies of a
    1.31 GB PDF into a 5.26 GB, 4000-page output peaked at **84 MB RSS**.
    That decoupling is what makes 100 GB documents possible at all — a
    browser tab cannot do this, because V8 caps ArrayBuffer at 2 GB.

Nothing here requires network access.
"""

import io
import logging
import os
import shutil
import tempfile
import zipfile
from typing import List, Optional, Tuple

import pikepdf

from errors import EngineError

logger = logging.getLogger("dockbench.pdf")

# The fused in-process engine (see native/pdfops.cpp).
try:
    import dockbench_pdf as _ext
    logger.info("Fused PDF engine loaded (dockbench_pdf)")
except ImportError:
    _ext = None

# Above this, work path-to-path instead of holding the document in memory.
# 64 MB is well below any plausible RAM budget while avoiding temp-file
# overhead for the common case.
STREAM_THRESHOLD = int(os.environ.get("STREAM_THRESHOLD_MB", "64")) * 1024 * 1024


def pdf_backend() -> str:
    """Which implementation these functions will use. Surfaced through
    /capabilities so a deployment can be checked rather than assumed."""
    return "extension" if _ext is not None else "pikepdf"


def streaming_available() -> bool:
    """True when path-based, memory-bounded operations are possible. Without
    the extension we fall back to pikepdf, which holds the document."""
    return _ext is not None and hasattr(_ext, "merge_files")


def _require_streaming():
    if not streaming_available():
        raise EngineError(
            501,
            "This file needs the streaming engine, which is not built on this "
            "deployment. Install the desktop app, or build the native "
            "extensions (cd backend && python setup.py build_ext --inplace).",
        )


def _open(data: bytes):
    """Open in-memory PDF bytes, turning a parse failure into a 422."""
    try:
        return pikepdf.open(io.BytesIO(data))
    except Exception as e:
        raise EngineError(422, f"Not a readable PDF: {e}")


def _npages(data: bytes) -> int:
    if _ext is not None:
        try:
            return _ext.npages(data)
        except ValueError as e:
            raise EngineError(422, f"Not a readable PDF: {e}")
    with _open(data) as pdf:
        return len(pdf.pages)


def run_merge_pdf(files: List[bytes]) -> Tuple[bytes, str]:
    """Merge PDFs held in memory. Returns (pdf_bytes, "application/pdf").

    The bytes-in/bytes-out variant, used by the batch endpoint and anywhere
    the uploads are already resident. `run_merge_pdf_files` is the
    path-based variant for inputs too large to hold in memory.
    """
    if not files:
        raise EngineError(422, "No PDFs provided for merge.")

    if _ext is not None:
        try:
            return _ext.merge(files), "application/pdf"
        except ValueError as e:
            raise EngineError(422, f"Merge failed: {e}")

    out = pikepdf.Pdf.new()
    try:
        for raw in files:
            with _open(raw) as src:
                out.pages.extend(src.pages)
        buf = io.BytesIO()
        out.save(buf)
        return buf.getvalue(), "application/pdf"
    finally:
        out.close()


def run_merge_pdf_files(input_paths: List[str]) -> Tuple[str, str]:
    """Merge PDFs from disk. Returns (output_path, "application/pdf").

    Prefers the streaming extension, whose peak memory is independent of
    input size — the pikepdf fallback builds the whole output in memory and
    will exhaust RAM on very large inputs.
    """
    if not input_paths:
        raise EngineError(422, "No PDFs provided for merge.")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="merged_")
    os.close(tmp_fd)

    if streaming_available():
        try:
            _ext.merge_files(list(input_paths), tmp_path)
            return tmp_path, "application/pdf"
        except ValueError as e:
            _unlink(tmp_path)
            raise EngineError(422, f"Merge failed: {e}")

    try:
        out = pikepdf.Pdf.new()
        with out:
            for p in input_paths:
                with pikepdf.open(p) as src:
                    out.pages.extend(src.pages)
            out.save(tmp_path)
    except Exception as e:
        _unlink(tmp_path)
        raise EngineError(422, f"Merge failed: {e}")

    return tmp_path, "application/pdf"


def _extract(data: bytes, first: int, last: int) -> bytes:
    """Pages first..last inclusive (1-based) as a standalone PDF."""
    if _ext is not None:
        try:
            return _ext.extract(data, first, last)
        except ValueError as e:
            raise EngineError(422, str(e))
    with _open(data) as src:
        dst = pikepdf.Pdf.new()
        with dst:
            for i in range(first - 1, last):
                dst.pages.append(src.pages[i])
            buf = io.BytesIO()
            dst.save(buf)
        return buf.getvalue()


def run_split_pdf(data: bytes) -> Tuple[bytes, str]:
    """Split a PDF into one file per page, returned as a .zip."""
    page_count = _npages(data)
    if page_count == 0:
        raise EngineError(422, "PDF has no pages.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in range(1, page_count + 1):
            zf.writestr(f"page_{i}.pdf", _extract(data, i, i))
    return buf.getvalue(), "application/zip"


def run_split_pdf_range(data: bytes, start_page: int, end_page: int) -> Tuple[bytes, str]:
    """Return pages start_page..end_page (inclusive) as a .zip."""
    if start_page < 1 or end_page < start_page:
        raise EngineError(422, "Invalid page range specified.")

    total = _npages(data)
    if end_page > total:
        raise EngineError(422, f"Requested end_page {end_page} exceeds total pages {total}.")

    payload = _extract(data, start_page, end_page)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"range_{start_page}_{end_page}.pdf", payload)
    return buf.getvalue(), "application/zip"


def run_rotate_pdf(data: bytes, angle: int = 0) -> Tuple[bytes, str]:
    """Rotate every page by `angle` degrees, relative to its current
    rotation. `angle` must be a multiple of 90."""
    if angle % 90 != 0:
        raise EngineError(422, "Angle must be a multiple of 90 degrees.")

    if _ext is not None:
        try:
            return _ext.rotate(data, angle), "application/pdf"
        except ValueError as e:
            raise EngineError(422, f"Not a readable PDF: {e}")

    with _open(data) as src:
        for page in src.pages:
            # /Rotate is optional and absent on most real-world pages, so
            # reading it as an attribute raises instead of defaulting to 0.
            current = int(page.obj.get("/Rotate", 0))
            page.obj["/Rotate"] = (current + angle) % 360
        out = io.BytesIO()
        src.save(out)
    return out.getvalue(), "application/pdf"


def run_watermark_pdf(data: bytes, watermark: bytes) -> Tuple[bytes, str]:
    """Stamp the first page of `watermark` over every page of `data`.

    Stays on pikepdf: add_overlay handles content-stream merging and
    resource-name collisions, which is the fiddly part of this operation.
    """
    with _open(data) as base, _open(watermark) as wm:
        if len(wm.pages) == 0:
            raise EngineError(422, "Watermark PDF has no pages.")
        wm_page = wm.pages[0]
        for page in base.pages:
            page.add_overlay(wm_page)
        out = io.BytesIO()
        base.save(out)
    return out.getvalue(), "application/pdf"


# ---------------------------------------------------------------------
# Path-based API — for documents too large to hold in memory.
#
# These are what the desktop app's local engine calls. Nothing is ever
# copied through HTTP or through a Python bytes object; the OS file picker
# hands over a path and the engine works on it in place.
# ---------------------------------------------------------------------

def npages_path(in_path: str) -> int:
    """Page count without reading the document into memory."""
    _require_streaming()
    _check_readable(in_path)
    try:
        return _ext.npages_file(in_path)
    except ValueError as e:
        raise EngineError(422, f"Not a readable PDF: {e}")


# Peak RSS of a merge is not a function of the input's size in bytes — a
# 2.7 GB / 240-page merge costs 43 MB while a 5.2 GB / 12,000-page merge
# costs 216 MB. It is a function of the *page count*, because the output
# document holds a page-tree entry (plus that page's resource references)
# for every page until the writer finishes.
#
# Measured across a 40x page range on this engine: 17.0-23.1 KB per page,
# on top of a ~25 MB interpreter baseline. Batching the input does not help
# — cascading a 48,000-page merge through 8 intermediates lowered the
# intermediate peak to 116 MB but the final pass still cost 804 MB, the
# same as merging directly, and took twice as long. The only thing that
# genuinely bounds the peak is capping pages per *output* file.
KB_PER_PAGE = 24           # upper end of the measured range, for planning
BASELINE_MB = 32           # interpreter + engine, independent of the job


def estimate_merge_mb(pages: int, max_pages_per_part: Optional[int] = None) -> int:
    """Peak RSS a merge of `pages` pages is expected to need, in MB.

    Splitting the output caps the cost at one part's worth, since each part
    is written and released before the next begins. Verified: 48,000 pages
    cost 812 MB in one file, 124 MB in parts of 6,000, 75 MB in parts of
    3,000.
    """
    effective = min(pages, max_pages_per_part) if max_pages_per_part else pages
    return int(BASELINE_MB + (effective * KB_PER_PAGE) / 1024)


def pages_per_part_for(budget_mb: int) -> int:
    """Largest part size that fits a memory budget.

    Use on devices with a hard per-process ceiling — an Android app is
    typically held to a few hundred MB no matter how much RAM the phone has.
    """
    usable = max(budget_mb - BASELINE_MB, 16)
    return max(500, int(usable * 1024 / KB_PER_PAGE))


def _available_mb() -> Optional[int]:
    """Physical memory available right now, or None if it cannot be read."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return None


def merge_paths(in_paths: List[str], out_path: str,
                max_pages_per_part: Optional[int] = None) -> int:
    """Merge PDFs from disk to disk. Returns the page count written.

    With `max_pages_per_part` set, the result is split across
    `out_path`-derived part files, each holding at most that many pages.
    Peak memory then tracks the part size rather than the total, which is
    what makes a very large merge possible on a device with a hard
    per-process memory ceiling, such as a phone.
    """
    _require_streaming()
    if not in_paths:
        raise EngineError(422, "No PDFs provided for merge.")
    for p in in_paths:
        _check_readable(p)

    if max_pages_per_part:
        return _merge_in_parts(in_paths, out_path, max_pages_per_part)

    try:
        return _ext.merge_files(list(in_paths), out_path)
    except ValueError as e:
        _unlink(out_path)
        raise EngineError(422, f"Merge failed: {e}")


def _merge_in_parts(in_paths: List[str], out_path: str, per_part: int) -> int:
    """Merge into consecutive part files, each capped at `per_part` pages.

    Sources are accumulated until adding the next one would cross the cap,
    so a single source larger than the cap still lands whole in its own
    part — splitting mid-document would be a surprising thing to do to
    someone who asked for a merge.
    """
    if per_part < 1:
        raise EngineError(422, "Pages per part must be at least 1.")
    root, ext = os.path.splitext(out_path)
    batch: List[str] = []
    batch_pages = 0
    total = 0
    part = 0
    written: List[str] = []

    def flush():
        nonlocal batch, batch_pages, part, total
        if not batch:
            return
        part += 1
        target = f"{root}-part{part}{ext or '.pdf'}"
        try:
            total += _ext.merge_files(list(batch), target)
        except ValueError as e:
            for w in written:
                _unlink(w)
            _unlink(target)
            raise EngineError(422, f"Merge failed on part {part}: {e}")
        written.append(target)
        batch = []
        batch_pages = 0

    for p in in_paths:
        n = _ext.npages_file(p)
        if batch and batch_pages + n > per_part:
            flush()
        batch.append(p)
        batch_pages += n
    flush()
    return total


def extract_path(in_path: str, out_path: str, first: int, last: int) -> int:
    """Write pages first..last (inclusive, 1-based) to out_path."""
    _require_streaming()
    _check_readable(in_path)
    if first < 1 or last < first:
        raise EngineError(422, "Invalid page range specified.")
    try:
        return _ext.extract_file(in_path, out_path, first, last)
    except ValueError as e:
        _unlink(out_path)
        raise EngineError(422, str(e))


def rotate_path(in_path: str, out_path: str, angle: int) -> int:
    """Rotate every page relative to its current rotation."""
    _require_streaming()
    _check_readable(in_path)
    if angle % 90 != 0:
        raise EngineError(422, "Angle must be a multiple of 90 degrees.")
    try:
        return _ext.rotate_file(in_path, out_path, angle)
    except ValueError as e:
        _unlink(out_path)
        raise EngineError(422, f"Not a readable PDF: {e}")


def split_path(in_path: str, out_dir: str, prefix: str = "page") -> int:
    """Write one PDF per page into out_dir. Returns the file count."""
    _require_streaming()
    _check_readable(in_path)
    os.makedirs(out_dir, exist_ok=True)
    try:
        return _ext.split_file(in_path, out_dir, prefix)
    except ValueError as e:
        raise EngineError(422, f"Split failed: {e}")


def _check_readable(path: str):
    if not os.path.isfile(path):
        raise EngineError(404, "File not found.")
    if not os.access(path, os.R_OK):
        raise EngineError(403, "File is not readable.")


def _unlink(path: str):
    try:
        os.remove(path)
    except OSError:
        pass


def free_space_ok(out_dir: str, needed_bytes: int, headroom: float = 1.2) -> bool:
    """Is there room to write `needed_bytes` into out_dir?

    Checked before starting rather than failing halfway through and leaving
    a truncated file behind — which matters far more at 100 GB than at 1 MB.
    """
    try:
        free = shutil.disk_usage(out_dir).free
    except OSError:
        return True          # can't tell; let the write attempt decide
    return free > needed_bytes * headroom
