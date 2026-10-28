# ResumeIQ API. Python matches the tested baseline (see constraints-baseline.txt).
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt constraints-baseline.txt ./
RUN pip install --no-cache-dir -r requirements.txt -c constraints-baseline.txt

COPY . .
RUN useradd --create-home --uid 10001 resumeiq && mkdir -p /app/data && chown -R resumeiq /app/data
USER resumeiq

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

# One worker: sessions are held in process memory.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
