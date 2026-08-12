FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PATH=/opt/crawler-venv/bin:$PATH \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq python3 python3-pip python3-venv xz-utils \
        libnss3 libnspr4 libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 \
        libdbus-1-3 libdrm2 libxkbcommon0 libatspi2.0-0t64 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
        libcairo2 libasound2t64 libx11-xcb1 libfontconfig1 libx11-6 \
        libxcb1 libxext6 libxshmfence1 libglib2.0-0t64 libgtk-3-0t64 \
        libpangocairo-1.0-0 libcairo-gobject2 libgdk-pixbuf-2.0-0 \
        libxss1 libxtst6 fonts-liberation fonts-noto-color-emoji \
        xvfb \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/crawler-venv

# Pulls in opencv-python-headless + numpy for tools/slider-cv (the 安全验证 solver).
# The headless wheel vendors its own native deps and links only against glibc,
# libstdc++ and libz, all of which the layer above already provides - no extra apt.
COPY tools/kanxue-crawler/requirements.txt /tmp/crawler-requirements.txt
RUN pip install --no-cache-dir \
      -r /tmp/crawler-requirements.txt cryptography

COPY tools/cloakbrowser-ci /opt/cloakbrowser-ci
RUN chmod +x /opt/cloakbrowser-ci/*.sh /opt/cloakbrowser-ci/*.py

WORKDIR /repo
ENTRYPOINT ["/opt/cloakbrowser-ci/entrypoint.sh"]
