# first stage
FROM python:3 AS builder
WORKDIR /code
COPY . .
RUN pip install --user --no-cache-dir --use-feature=in-tree-build --no-warn-script-location .

# second stage
FROM python:3-slim
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
EXPOSE 8025
ENTRYPOINT ["mailrise"]
CMD ["/etc/mailrise.conf"]
