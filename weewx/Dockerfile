FROM python:3.13-slim-bookworm

ARG BUILD_VERSION=1.1.0
ARG BUILD_ARCH=amd64

LABEL \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.type="app" \
    io.hass.arch="${BUILD_ARCH}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WEEWX_ROOT=/data/weewx

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir weewx==5.4.0

RUN mkdir -p /data/weewx /etc/weewx
COPY configure.py run.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/run.sh

EXPOSE 80

CMD ["/usr/local/bin/run.sh"]
