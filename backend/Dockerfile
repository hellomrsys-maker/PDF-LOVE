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

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Compile the native C image kernel (see native/imgproc.c). If this step
# is removed, the API still runs — native_ops.py falls back to Pillow.
COPY native/ native/
RUN gcc -O3 -shared -fPIC -o native/imgproc.so native/imgproc.c

COPY native_ops.py main.py ./

EXPOSE 8000
# gunicorn manages multiple uvicorn worker processes so the API can use
# more than one CPU core. Tune --workers to (2 x CPU cores) + 1 as a
# starting point; each worker holds its own copy of any loaded AI models,
# so on a memory-constrained box, fewer workers + a task queue (see
# README) scales more predictably than cranking this number up.
CMD ["gunicorn", "main:app", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "180"]
