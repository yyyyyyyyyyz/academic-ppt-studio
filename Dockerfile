# Stage 1: Build Production React + Vite Frontend
FROM node:22-slim AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python 3.11 + RDKit + Linux CJK Fonts + FastAPI Single-Port Server
FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxrender1 \
    libxext6 \
    libexpat1 \
    fontconfig \
    fonts-noto-cjk \
    fonts-liberation \
    fonts-dejavu-core \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY skill/ /app/skill/
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/artifacts/decks /tmp/mpl_academic_ppt \
    && chown -R 1000:1000 /app /tmp/mpl_academic_ppt

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    MPLCONFIGDIR=/tmp/mpl_academic_ppt \
    LLM_PROVIDER_MODE=auto \
    FIGURE_PROVIDER_MODE=local \
    DECK_TTL_HOURS=24 \
    MAX_UPLOAD_MB=20 \
    PORT=7860

USER 1000

# Pre-build the 4-slide Nature Editorial specimen plates into /app/artifacts at image build time
RUN python /app/backend/docker_entrypoint.py --init-only

EXPOSE 7860 8000

CMD ["python", "/app/backend/docker_entrypoint.py"]
