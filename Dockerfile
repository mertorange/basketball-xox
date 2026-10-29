# Hoop-Tac-Toe: one image for the game server and the data builder.
# The test stage must pass for the final image to build.

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend backend
COPY frontend frontend

FROM base AS test
RUN pip install pytest httpx
COPY tests tests
RUN HOOPGRID_RATE_LIMIT=0 python -m pytest -q -p no:cacheprovider tests && touch /tmp/tests-passed

FROM base AS app
COPY --from=test /tmp/tests-passed /tmp/tests-passed
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 0755 /usr/local/bin/entrypoint.sh \
 && useradd --create-home --uid 10001 hoopgrid \
 && mkdir -p /data \
 && chown hoopgrid:hoopgrid /data
USER hoopgrid
# The data volume holds releases/<stamp>/ and a `current` link to the live one
ENV HOOPGRID_DATA_ROOT=/data \
    HOOPGRID_DATA_DIR=/data/current
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
ENTRYPOINT ["entrypoint.sh"]
# One worker: rooms and running games live in this process's memory
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
