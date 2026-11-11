FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DW_DATA_DIR=/app/runtime DW_DETECTOR=demo
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home --uid 10001 inspector && mkdir -p /app/runtime && chown inspector:inspector /app/runtime
COPY --chown=inspector:inspector app ./app
COPY --chown=inspector:inspector scripts ./scripts
USER inspector
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["python", "-m", "scripts.run_backend", "--host", "0.0.0.0"]
