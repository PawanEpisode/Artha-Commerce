# syntax=docker/dockerfile:1
# F-03 PDF worker image: one image for every host (Render, Fly.io, Railway, docker compose). Configuration is env vars only.
# Build context: apps/api   ->   docker build -f worker/Dockerfile -t artha-worker .   (run inside apps/api)
# Not built in the authoring sandbox (no Docker daemon); first build happens on your machine or on the host.

# ---- stage 1: the Noto fonts, checksum-pinned (licence SIL OFL 1.1, details in worker/FONTS.md) --------------------------
FROM python:3.12-slim-bookworm AS fonts
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /fonts
ARG NOTO=https://raw.githubusercontent.com/notofonts/notofonts.github.io/main/fonts
RUN set -eu; \
    curl -fsSL -o NotoSans-Regular.ttf "$NOTO/NotoSans/hinted/ttf/NotoSans-Regular.ttf"; \
    curl -fsSL -o NotoSans-Bold.ttf "$NOTO/NotoSans/hinted/ttf/NotoSans-Bold.ttf"; \
    curl -fsSL -o NotoSansDevanagari-Regular.ttf "$NOTO/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Regular.ttf"; \
    curl -fsSL -o NotoSansDevanagari-Bold.ttf "$NOTO/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Bold.ttf"; \
    printf '%s\n' \
      "478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823  NotoSans-Regular.ttf" \
      "1df075a380fc7cb898acf64c1f7b3b4dd780de3caa860178bf929de35817a913  NotoSans-Bold.ttf" \
      "4e3c66638958c3e2ab5d37f47a8deb89fffeb7be9985c665a519bbc7ba762313  NotoSansDevanagari-Regular.ttf" \
      "6a09c8d797cfc803d32cdc731e809424d74cbaff59f503de34ade421a08e5bc2  NotoSansDevanagari-Bold.ttf" \
      | sha256sum -c -
COPY worker/FONTS.md /fonts/README-FONTS.md

# ---- stage 2: Python dependencies in a venv ----------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS deps
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /build
COPY requirements.txt worker/requirements-worker.txt ./worker/
# requirements-worker.txt says `-r ../requirements.txt`, so keep the two files one level apart as in the repo
RUN mv worker/requirements.txt ./requirements.txt && pip install -r worker/requirements-worker.txt

# ---- stage 3: runtime ------------------------------------------------------------------------------------------------------------
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    OMP_THREAD_LIMIT=1 \
    WORKER_FONTS_DIR=/usr/share/fonts/truetype/artha \
    WORKER_LIVENESS_FILE=/tmp/artha-worker.alive \
    DJANGO_DEBUG=false

# tini: PID 1 that forwards SIGTERM and reaps children (clamd, freshclam).
# tesseract-ocr 5 with English and Hindi data; ClamAV daemon and updater (clamd needs about 1 GB of RAM).
RUN apt-get update && apt-get install -y --no-install-recommends \
        tini tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
        clamav clamav-daemon clamav-freshclam \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --home-dir /home/worker worker \
    && mkdir -p /var/lib/clamav /app \
    && chown -R worker:worker /var/lib/clamav /app

COPY --from=deps /opt/venv /opt/venv
COPY --from=fonts /fonts /usr/share/fonts/truetype/artha
WORKDIR /app
COPY --chown=worker:worker . /app
RUN chmod +x /app/worker/entrypoint.sh

USER worker
# Seed the signature database at build time so a cold start does not wait for a full download; the entrypoint keeps it fresh.
# Best effort: a build without network still succeeds and the entrypoint downloads at first start.
RUN freshclam --config-file=/app/worker/freshclam.conf --quiet --foreground=yes || echo "freshclam skipped at build time"

# Real work is only the claim loop; handlers talk to Postgres (DATABASE_URL), Supabase Storage and clamd (unix socket).
HEALTHCHECK --interval=60s --timeout=30s --start-period=240s --retries=3 \
    CMD sh -c 'tools=tesseract; [ "${MEDIA_SCANNER:-null}" = clamd ] && tools=tesseract,clamd; exec python manage.py worker_health --require-worker --require-tools "$tools"' 

ENTRYPOINT ["/usr/bin/tini", "--", "/app/worker/entrypoint.sh"]
CMD ["python", "manage.py", "run_worker"]
