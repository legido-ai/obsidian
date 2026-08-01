# Obsidian in Docker — headless HTTP service (Local REST API), vaults me/raw + me/wiki
# Builds for amd64 (latest/amd64) and arm64 (arch64) via CI.

ARG DOCKER_GID=998
FROM ubuntu:24.04

# DOCKER_GID is passed by the CI template for the docker socket group.
# This image does not mount the docker socket, so the group is not required.
ARG DOCKER_GID=998

ENV DEBIAN_FRONTEND=noninteractive

# Obsidian version (pin from https://github.com/obsidianmd/obsidian-releases/releases)
ENV OBSIDIAN_VERSION=1.13.4

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    curl \
    python3 \
    ca-certificates \
    # Electron runtime libraries
    libgtk-3-0 \
    libnss3 \
    libasound2t64 \
    libxss1 \
    libxtst6 \
    libgbm1 \
    libdrm2 \
    libxkbcommon0 \
    libatk-bridge2.0-0 \
    libcups2t64 \
    libsecret-1-0 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Download Obsidian for the build architecture (buildx sets TARGETARCH).
# Asset naming: arm64 tarball has an -arm64 suffix; the amd64 tarball does not.
ARG TARGETARCH
RUN if [ "$TARGETARCH" = "amd64" ]; then \
      URL="https://github.com/obsidianmd/obsidian-releases/releases/download/v${OBSIDIAN_VERSION}/obsidian-${OBSIDIAN_VERSION}.tar.gz"; \
    else \
      URL="https://github.com/obsidianmd/obsidian-releases/releases/download/v${OBSIDIAN_VERSION}/obsidian-${OBSIDIAN_VERSION}-${TARGETARCH}.tar.gz"; \
    fi; \
    echo "[obsidian] downloading $URL"; \
    curl -fsSL "$URL" -o /tmp/obsidian.tar.gz && \
    mkdir -p /opt/obsidian && tar -xzf /tmp/obsidian.tar.gz -C /opt/obsidian && rm /tmp/obsidian.tar.gz

# Vault HTTP API (Hermes <-> Obsidian over pure HTTP, port 27123)
COPY vault_api.py /vault_api.py
# Local REST API plugin (optional; requires disabling restricted mode in the UI)
COPY obsidian-local-rest-api/ /opt/obsidian-local-rest-api/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 27123

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -s -o /dev/null http://localhost:27123/ || exit 1

CMD ["/entrypoint.sh"]
