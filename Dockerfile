FROM python:3

WORKDIR /usr/src/mailrise

COPY . .
RUN pip install --no-cache-dir --use-feature=in-tree-build .

EXPOSE 8025
CMD [ "mailrise", "/etc/mailrise.conf" ]
