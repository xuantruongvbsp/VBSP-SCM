# ── VBSP-SCM Docker Image ──────────────────────────────────────────────────────
# Build: docker build -t vbsp-scm .
# Run:   docker-compose up -d
FROM python:3.12-slim

# Metadata
LABEL maintainer="Chi nhanh Ngan hang Chinh sach xa hoi thanh pho Dong Nai" \
      description="He thong Quan tri Tin dung Noi bo VBSP-SCM"

# System dependencies (tesseract OCR + poppler for pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-vie \
        poppler-utils \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source (excluding items in .dockerignore)
COPY . .

# Persistent data lives in mounted volumes — pre-create dirs
RUN mkdir -p cache pgd_data backups logs

EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
