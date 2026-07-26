import os
import tempfile
import logging
from shutil import which
from .engines import EngineError

# ---------------------------------------------------------------------
# AI-powered engines – placeholder implementations using local tools
# ---------------------------------------------------------------------

def run_image_enhance(data: bytes, filename: str, model: str = "default"):
    """Enhance an image using a locally hosted AI model.

    Requires internet connectivity for model download/verification.
    """
    if not is_online():
        raise EngineError(503, "Online connectivity required for image enhancement.")
    logging.info("run_image_enhance: model=%s (placeholder)", model)
    return data, "image/png"
    """Enhance an image using a locally hosted AI model.

    This placeholder simply returns the original image. Replace with actual
    model inference (e.g., TensorFlow or PyTorch) when the model files are
    available on the user's hardware.
    """
    logging.info("run_image_enhance: model=%s (placeholder)", model)
    return data, "image/png"


def run_super_resolve(data: bytes, filename: str, scale: int = 2, model: str = "default"):
    """Perform super‑resolution on an image.

    Requires internet connectivity for model download/verification.
    """
    if not is_online():
        raise EngineError(503, "Online connectivity required for super‑resolution.")
    logging.info("run_super_resolve: scale=%d model=%s (placeholder)", scale, model)
    return data, "image/png"
    """Perform super‑resolution on an image.

    Placeholder implementation – returns the original data. In production
    this would up‑sample the image using a super‑resolution network.
    """
    logging.info("run_super_resolve: scale=%d model=%s (placeholder)", scale, model)
    return data, "image/png"


def run_audio_extract(data: bytes, filename: str, format: str = "mp3"):
    """Extract audio from a video file using FFmpeg.

    Requires internet connectivity for licensing checks or remote model usage.
    """
    if not is_online():
        raise EngineError(503, "Online connectivity required for audio extraction.")
    if not which("ffmpeg"):
        raise EngineError(503, "FFmpeg is not installed on this server (see backend/Dockerfile).")
    with tempfile.TemporaryDirectory(prefix="dockbench-") as tmp:
        src = os.path.join(tmp, filename)
        out_file = os.path.join(tmp, f"out.{format}")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", src,
            "-vn",
            "-acodec", "copy",
            out_file,
        ]
        from .engines import _run
        _run(cmd)
        with open(out_file, "rb") as f:
            out = f.read()
    mime = f"audio/{format}" if not format.startswith("mp3") else "audio/mpeg"
    return out, mime
    """Extract audio from a video file using FFmpeg.

    * ``format`` – Desired audio container (e.g., mp3, wav, aac).
    """
    if not which("ffmpeg"):
        raise EngineError(503, "FFmpeg is not installed on this server (see backend/Dockerfile).")
    with tempfile.TemporaryDirectory(prefix="dockbench-") as tmp:
        src = os.path.join(tmp, filename)
        out_file = os.path.join(tmp, f"out.{format}")
        with open(src, "wb") as f:
            f.write(data)
        cmd = [
            "ffmpeg",
            "-y",
            "-i", src,
            "-vn",
            "-acodec", "copy",
            out_file,
        ]
        # Import the internal _run helper from engines
        from .engines import _run
        _run(cmd)
        with open(out_file, "rb") as f:
            out = f.read()
    mime = f"audio/{format}" if not format.startswith("mp3") else "audio/mpeg"
    return out, mime
