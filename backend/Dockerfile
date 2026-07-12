FROM python:3.11-slim

# Tesseract is the open-source OCR engine itself (the pip package is only
# a wrapper around this binary).
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
# gunicorn manages multiple uvicorn worker processes so the API can use
# more than one CPU core. Tune --workers to (2 x CPU cores) + 1 as a
# starting point; each worker holds its own copy of any loaded AI models,
# so on a memory-constrained box, fewer workers + a task queue (see
# README) scales more predictably than cranking this number up.
CMD ["gunicorn", "main:app", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]
