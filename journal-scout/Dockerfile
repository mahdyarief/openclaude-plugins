FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JOSC_TRANSPORT=http \
    JOSC_HOST=0.0.0.0 \
    JOSC_PORT=8080 \
    JOSC_WEB_DIST=/app/web/dist

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY --from=web-build /web/dist ./web/dist
RUN pip install --no-cache-dir ".[server,web]"

RUN useradd --create-home --uid 10001 josc
USER josc

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"

CMD ["journal-scout"]
