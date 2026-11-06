# The host container supplies tools only; target packages are built from source.
FROM ubuntu:24.04@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
ENV DEBIAN_FRONTEND=noninteractive
RUN --mount=type=secret,id=ca_bundle,required=true,mode=0444 \
    sed -i 's|http://|https://|g' /etc/apt/sources.list.d/ubuntu.sources && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/ca_bundle update && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/ca_bundle install -y --no-install-recommends \
      build-essential ca-certificates chrpath cpio curl debianutils diffstat file gawk \
      git iputils-ping libacl1 liblz4-tool locales python3 python3-git python3-jinja2 \
      python3-pexpect python3-pip python3-subunit socat texinfo unzip wget xz-utils \
      zstd qemu-system-x86 qemu-utils && \
    locale-gen en_US.UTF-8 && rm -rf /var/lib/apt/lists/*
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8
ARG BUILD_UID=1000
ARG BUILD_GID=1000
RUN if [ "$(id -g ubuntu)" != "$BUILD_GID" ]; then groupmod -g "$BUILD_GID" ubuntu; fi && \
    if [ "$(id -u ubuntu)" != "$BUILD_UID" ]; then usermod -u "$BUILD_UID" ubuntu; fi && \
    chown -R "$BUILD_UID:$BUILD_GID" /home/ubuntu
USER ubuntu
WORKDIR /work
