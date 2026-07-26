# backend/batch_pdf.py
"""Batch PDF processing helpers for the /batch-pdf endpoint.
Implements merging, splitting, rotating, and watermarking of multiple PDFs in a single request.
User requested no size caps.
"""
from typing import List

from errors import EngineError
from premium_pdf import (
    run_merge_pdf,
    run_split_pdf,
    run_rotate_pdf,
    run_watermark_pdf,
)


def run_batch_pdf(job: str, files: List[bytes], **kwargs):
    """Dispatch a batch job to the appropriate premium PDF function.

    Args:
        job: "merge", "split", "rotate", or "watermark".
        files: List of raw PDF bytes.
        kwargs: Additional parameters (e.g., angle for rotate, wm_bytes for watermark).

    Returns:
        Tuple[bytes, str]: (payload_bytes, mime_type)
    """
    # Bad input is the caller's fault, so raise EngineError (-> 4xx) rather
    # than ValueError, which the HTTP layer would surface as a 500.
    if job == "merge":
        # Merge expects a list of PDFs
        return run_merge_pdf(files)
    if job == "split":
        # Split expects a single PDF
        if not files:
            raise EngineError(422, "No PDF provided for split job.")
        return run_split_pdf(files[0])
    if job == "rotate":
        if not files:
            raise EngineError(422, "No PDF provided for rotate job.")
        return run_rotate_pdf(files[0], int(kwargs.get("angle", 0)))
    if job == "watermark":
        if len(files) < 2:
            raise EngineError(422, "Watermark job requires a base PDF and a watermark PDF.")
        base_pdf, wm_pdf = files[0], files[1]
        return run_watermark_pdf(base_pdf, wm_pdf)
    raise EngineError(422, f"Unsupported batch PDF job: {job!r}. Valid: merge, split, rotate, watermark.")
