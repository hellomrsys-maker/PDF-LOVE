FROM python:3.11-slim

# The open-source engines that do the heavy lifting (all C/C++):
#   tesseract-ocr           OCR engine (+ extra language packs as needed)
#   ghostscript             PDF/A conversion + deep PDF compression
#   libreoffice (nogui)     Office <-> PDF conversion, headless
#   gcc                     compiles our native scan-cleanup kernel below
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    ghostscript \
    libreoffice-writer-nogui \
    libreoffice-impress-nogui \
    libreoffice-calc-nogui \
    fonts-liberation \
    gcc \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Compile the native C image kernel (see native/imgproc.c). If this step
# is removed, the API still runs — native_ops.py falls back to Pillow.
COPY native/ native/
RUN gcc -O3 -shared -fPIC -o native/imgproc.so native/imgproc.c

COPY native_ops.py engines.py worker.py main.py ./

# Run as a non-root user; HOME is writable for engine caches (LibreOffice
# profiles go to per-request temp dirs, rembg models to ~/.u2net).
RUN useradd --create-home --uid 10001 app
USER app
ENV HOME=/home/app

EXPOSE 8000
# gunicorn manages multiple uvicorn worker processes so the API can use
# more than one CPU core. WEB_WORKERS defaults to 3; in the production
# (queued) topology the API only shuffles bytes, so a few are plenty —
# the heavy lifting happens in the `worker` containers.
# --forwarded-allow-ips="*" is safe here because the container port is
# only reachable through the bundled nginx/Caddy on the compose network;
# the app additionally requires TRUST_PROXY=1 before honoring the header.
CMD ["sh", "-c", "gunicorn main:app --workers ${WEB_WORKERS:-3} --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout ${WEB_TIMEOUT:-180} --graceful-timeout 30 --forwarded-allow-ips '*'"]
