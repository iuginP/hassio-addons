FROM bluenviron/mediamtx:1.18.2 AS mediamtx

FROM python:3.11-slim-bookworm

ARG BUILD_VERSION=0.1.5
ARG BUILD_ARCH=amd64
ARG WIPCAM_COMMIT=0959ece54cea5829057ecc9a02d0de1416bb746e

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}" \
    org.opencontainers.image.source="https://github.com/iuginP/wipcam-bridge" \
    org.opencontainers.image.revision="${WIPCAM_COMMIT}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
        "https://github.com/iuginP/wipcam-bridge/archive/${WIPCAM_COMMIT}.tar.gz"

COPY --from=mediamtx /mediamtx /usr/local/bin/mediamtx
COPY --from=mediamtx /mediamtx.yml /etc/mediamtx.yml

WORKDIR /app
COPY launcher.py run.sh ./
RUN chmod +x /app/run.sh

EXPOSE 18080 8554

CMD ["/app/run.sh"]
