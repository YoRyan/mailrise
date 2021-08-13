#!/usr/bin/env bash
set -Eeuo pipefail
docker build .
exec docker run --rm --net host -it \
    -v $PWD/mailrise.conf~:/etc/mailrise.conf:ro \
    $(docker build -q .)
