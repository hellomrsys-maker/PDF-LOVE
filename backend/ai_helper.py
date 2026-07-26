"""
ai_helper — image/audio helpers that sit alongside the main engines.

Like everything else in this backend these run on the machine the backend is
installed on. They never call out to a hosted service, and they must never
require internet access to function.
"""

import logging
import os
import tempfile
from shutil import which

from errors import EngineError


def run_image_enhance(data: bytes, filename: str, model: str = "default"):
    """Enhance an image using a locally hosted model.

    Placeholder: returns the original image unchanged. Replace with real
    inference (ONNX Runtime is already a dependency) when the model files
    are shipped alongside the backend.
    """
    logging.info("run_image_enhance: model=%s (placeholder)", model)
    return data, "image/png"


def run_super_resolve(data: bytes, filename: str, scale: int = 2, model: str = "default"):
    """Upscale an image.

    Placeholder: returns the original data. In production this would run a
    super-resolution network locally.
    """
    logging.info("run_super_resolve: scale=%d model=%s (placeholder)", scale, model)
    return data, "image/png"


def run_audio_extract(data: bytes, filename: str, format: str = "mp3"):
    """Extract the audio track from a video file using FFmpeg.

    * ``format`` – desired audio container (e.g. mp3, wav, aac).
    """
    if not which("ffmpeg"):
        raise EngineError(503, "FFmpeg is not installed on this server (see backend/Dockerfile).")

    # Never let a caller-supplied filename escape the temp directory.
    safe_name = os.path.basename(filename or "input")
    safe_format = format.lower()
    if not safe_format.isalnum():
        raise EngineError(422, "Invalid audio format.")

    with tempfile.TemporaryDirectory(prefix="dockbench-") as tmp:
        src = os.path.join(tmp, safe_name)
        out_file = os.path.join(tmp, f"out.{safe_format}")
        with open(src, "wb") as f:
            f.write(data)
        # Imported here rather than at module scope: engines.py imports this
        # module at the bottom of its own body, so a top-level import would
        # reintroduce the cycle that errors.py exists to avoid.
        from engines import _run

        # -acodec copy keeps the original stream when the container allows
        # it; ffmpeg errors out (and _run raises) when it doesn't.
        _run(["ffmpeg", "-y", "-i", src, "-vn", "-acodec", "copy", out_file])
        with open(out_file, "rb") as f:
            out = f.read()

    mime = "audio/mpeg" if safe_format == "mp3" else f"audio/{safe_format}"
    return out, mime
