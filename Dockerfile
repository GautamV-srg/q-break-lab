FROM node:20-slim AS frontend-build
WORKDIR /fe
COPY frontend/ ./
RUN if [ -f package.json ]; then npm ci && npm run build; else mkdir -p dist && echo '<h1>Q-Break API is up</h1>' > dist/index.html; fi

FROM python:3.11-slim
WORKDIR /app
COPY backend/ ./backend/
RUN pip install --no-cache-dir ./backend
COPY --from=frontend-build /fe/dist ./static
ENV QBREAK_KEY_BITS=4 \
    QBREAK_AES_TIMEOUT_S=60 \
    SYMMETRIC_MAX_KEY_BITS=8 \
    QBREAK_RESULTS_DIR=/app/backend/results \
    QBREAK_MODULI=15,21,33,35 \
    QBREAK_MAX_CONCURRENT_SIMS=1 \
    STATIC_DIR=/app/static
EXPOSE 8000
CMD ["sh", "-c", "uvicorn qbreak.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
