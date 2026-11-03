# Worker Dockerfile for CodeImpact Background Tasks
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Runtime Image
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 codeimpact

COPY --from=builder /root/.local /home/codeimpact/.local
ENV PATH=/home/codeimpact/.local/bin:$PATH
ENV PYTHONPATH=/app

COPY . /app

RUN chown -R codeimpact:codeimpact /app
USER codeimpact

CMD ["python", "-m", "rq.worker", "-u", "redis://redis:6379/0", "codeimpact_analysis"]
