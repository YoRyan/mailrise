#!/usr/bin/env bash
set -Eeuo pipefail

export DOCKER_CLI_EXPERIMENTAL=enabled

docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

docker buildx build \
    --platform linux/amd64,linux/arm/v7,linux/arm64 \
    -t "ghcr.io/homelab-library/mailrise:latest" .
