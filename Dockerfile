# first stage
FROM python:3 AS builder
WORKDIR /code
COPY . .
RUN pip install --user --no-cache-dir --no-warn-script-location .

# second stage
FROM python:3-slim
RUN groupadd -r mailrise && useradd --no-log-init -r -g mailrise mailrise
USER mailrise
COPY --from=builder --chown=mailrise:mailrise /root/.local/ /home/mailrise/.local/
ENV PATH=/home/mailrise/.local/bin/:$PATH
EXPOSE 8025
ENTRYPOINT ["mailrise"]
CMD ["/etc/mailrise.conf"]
