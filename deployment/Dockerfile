FROM python:3.12-slim-bookworm AS backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    z3 procps curl libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 libffi-dev shared-mime-info && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY backend/requirements.txt ./backend/requirements.txt

# Install dependencies (torch CPU wheel + all pins via requirements.txt)
RUN pip install --no-cache-dir -r backend/requirements.txt

RUN groupadd -r logiscan && useradd -r -g logiscan -d /app -s /sbin/nologin logiscan

COPY backend/ ./backend/
COPY models/ ./models/

RUN mkdir -p /app/logs && chown -R logiscan:logiscan /app

# --- Frontend build stage ---
FROM node:22-slim AS frontend

WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# --- Final stage ---
FROM backend

COPY --from=frontend /build/dist /app/frontend/dist
COPY frontend/streamlit/ /app/frontend/streamlit/

COPY deployment/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

USER logiscan
EXPOSE 8000 8501
ENTRYPOINT ["/entrypoint.sh"]
