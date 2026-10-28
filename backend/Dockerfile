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
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/api/health', timeout=3)"

# One worker: sessions are held in process memory. Hosts such as Render set
# PORT; behind their proxy, set FORWARDED_ALLOW_IPS so login rate limiting sees
# real client addresses (uvicorn reads it from the environment).
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
