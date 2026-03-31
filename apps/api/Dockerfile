# Build from repository root (signing + JCS use FRAME_REPO_ROOT → scripts + packages/signing).
# docker compose up --build  (see docker-compose.yml)
FROM python:3.11-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    ffmpeg \
    tesseract-ocr \
    gcc \
    libpq-dev \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

COPY package.json package-lock.json ./
COPY tsconfig.json tsconfig.build.json ./
COPY packages ./packages
COPY scripts ./scripts

RUN npm ci && npm run build

WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/ ./

ENV FRAME_REPO_ROOT=/workspace

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
