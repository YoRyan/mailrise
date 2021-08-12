# This image is only used for build so we don't care about size
FROM python:3.9-alpine as builder
WORKDIR /build

# Add packages needed to build wheels
RUN apk update && mkdir -p /dist
RUN apk add build-base git libffi-dev rust cargo openssl-dev

# Build and install to /dist
COPY ["setup.cfg", "setup.py", "./"]
COPY src/ src/
RUN pip install --no-cache-dir --use-feature=in-tree-build --root /dist --no-warn-script-location .

# Published container
FROM python:3.9-alpine as target
RUN apk add --no-cache libffi openssl
COPY --from=builder /dist/ /
EXPOSE 8025
CMD [ "mailrise", "/etc/mailrise.conf" ]
