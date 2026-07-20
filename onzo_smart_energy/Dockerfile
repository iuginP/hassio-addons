FROM python:3.13-slim-bookworm

ARG BUILD_VERSION=1.0.0
ARG BUILD_ARCH=amd64

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libhidapi-hidraw0 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir hidapi==0.14.0.post4 paho-mqtt==2.1.0

WORKDIR /app
COPY discovery.py main.py protocol.py runtime.py run.sh ./
COPY THIRD_PARTY_NOTICES.md ./
COPY LICENSES ./LICENSES
RUN chmod +x /app/run.sh

CMD ["/app/run.sh"]
