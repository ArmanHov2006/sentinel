FROM python:3.11-slim

LABEL maintainer="Arman"
LABEL description="Sentinel LLM Gateway"
LABEL version="0.1.0"

WORKDIR /app

COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app/src

RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=5 --start-period=40s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "sentinel.main:app", "--host", "0.0.0.0", "--port", "8000"]
