# first stage
FROM python:3 AS builder
WORKDIR /code
COPY . .
RUN pip install --user --no-cache-dir --no-warn-script-location .

# second stage
FROM python:3-slim
ARG PUID=1000
ARG PGID=1000
RUN groupadd -g ${PGID} -r mailrise && useradd --no-log-init -r -u ${PUID} -g mailrise mailrise
ARG TZ=Etc/UTC
RUN ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime && dpkg-reconfigure -f noninteractive tzdata
USER mailrise
COPY --from=builder --chown=mailrise:mailrise /root/.local/ /home/mailrise/.local/
ENV PATH=/home/mailrise/.local/bin/:$PATH
EXPOSE 8025
ENTRYPOINT ["mailrise"]
CMD ["/etc/mailrise.conf"]
