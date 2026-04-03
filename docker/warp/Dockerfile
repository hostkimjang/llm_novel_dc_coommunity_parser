FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    wget \
    gnupg \
    lsb-release \
    iproute2 \
    procps \
    && wget -qO /tmp/cloudflare-warp.gpg https://pkg.cloudflareclient.com/pubkey.gpg \
    && gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg /tmp/cloudflare-warp.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ $(lsb_release -cs) main" > /etc/apt/sources.list.d/cloudflare-client.list \
    && apt-get update \
    && apt-get install -y cloudflare-warp \
    && rm -rf /var/lib/apt/lists/* /tmp/cloudflare-warp.gpg

COPY docker/warp/setup.sh /scripts/setup.sh
RUN chmod +x /scripts/setup.sh

CMD ["/bin/bash", "/scripts/setup.sh"]
