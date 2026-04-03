FROM python:3.11-slim

WORKDIR /app

# Runtime defaults for cleaner logs and reliable container behavior.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# System dependencies:
# - build-essential: compile wheels when needed
# - tesseract-ocr + language packs: OCR support in production
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir .

# Render/Docker entrypoint:
# 1) create/ensure schema + tables
# 2) ensure vector collection
# 3) start API server
CMD ["python", "-m", "scripts.bootstrap_start"]
