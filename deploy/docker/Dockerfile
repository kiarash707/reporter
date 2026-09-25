# =============================================================================
#  Slim, non-root runtime image for the Telegram Community Bot.
#  Build:  docker build -f deploy/docker/Dockerfile -t telegram-community-bot .
# =============================================================================
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BOT_HOME=/app

WORKDIR /app

# --- dependencies (kept in a separate layer so code changes stay cheap) ------
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt cryptg

# --- application ------------------------------------------------------------
COPY bot ./bot
COPY main.py pyproject.toml ./

# --- runtime ----------------------------------------------------------------
RUN useradd --create-home --uid 10001 botuser \
    && mkdir -p /app/data /app/logs /app/sessions \
    && chown -R botuser:botuser /app
USER botuser

ENV ENVIRONMENT=production \
    DATA_DIR=/app/data \
    SESSION_DIR=/app/sessions \
    LOG_DIR=/app/logs \
    LOG_JSON=true

VOLUME ["/app/data", "/app/sessions", "/app/logs"]

HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from bot.config import load_settings; from bot.storage.database import Database; s=load_settings(); db=Database(s.db_file); print(db.health()); db.close()" || exit 1

CMD ["python", "-m", "bot", "run"]
