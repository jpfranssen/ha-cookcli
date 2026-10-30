FROM ghcr.io/cooklang/cookcli:0.39.0

ARG BUILD_VERSION=0.2.1
LABEL io.hass.version="${BUILD_VERSION}" \
      io.hass.type="app" \
      io.hass.arch="amd64"

USER root
RUN apt-get update && apt-get install -y --no-install-recommends jq \
    && rm -rf /var/lib/apt/lists/*
COPY run.sh /run.sh
RUN chmod 0755 /run.sh
ENTRYPOINT ["/run.sh"]
CMD []
