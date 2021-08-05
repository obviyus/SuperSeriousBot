FROM python:3.9-slim AS build-env

ADD . /code
WORKDIR /code

RUN pip3 install --upgrade pip && pip install --no-cache-dir -r ./requirements.txt

FROM gcr.io/distroless/python3
COPY --from=build-env /code /code
COPY --from=build-env /usr/local/lib/python3.9/site-packages /usr/local/lib/python3.9/site-packages

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"
WORKDIR /code

ENV PYTHONPATH=/usr/local/lib/python3.9/site-packages
CMD ["main.py"]
