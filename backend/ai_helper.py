import os
import tempfile
import logging
from shutil import which
from errors import EngineError

# ---------------------------------------------------------------------
# AI-powered engines – placeholder implementations using local tools.
# These run entirely on the host: no network calls, so they keep working
# on an air-gapped deployment (see README "Offline licensing").
# ---------------------------------------------------------------------

def run_image_enhance(data: bytes, filename: str, model: str = "default"):
    """Enhance an image using a locally hosted AI model."""
    logging.info("run_image_enhance: model=%s (placeholder)", model)
    return data, "image/png"


def run_super_resolve(data: bytes, filename: str, scale: int = 2, model: str = "default"):
    """Perform super‑resolution on an image."""
    logging.info("run_super_resolve: scale=%d model=%s (placeholder)", scale, model)
    return data, "image/png"


def run_audio_extract(data: bytes, filename: str, format: str = "mp3"):
    """Extract audio from a video file using FFmpeg."""
    if not which("ffmpeg"):
        raise EngineError(503, "FFmpeg is not installed on this server (see backend/Dockerfile).")
    if not format.isalnum():
        raise EngineError(422, "Invalid audio format.")
    with tempfile.TemporaryDirectory(prefix="dockbench-") as tmp:
        # basename() only — the uploaded filename is attacker-controlled and
        # must never be able to escape the private temp dir.
        src = os.path.join(tmp, os.path.basename(filename) or "input")
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
        from engines import _run
        _run(cmd)
        with open(out_file, "rb") as f:
            out = f.read()
    mime = f"audio/{format}" if not format.startswith("mp3") else "audio/mpeg"
    return out, mime
