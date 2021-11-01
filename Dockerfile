FROM debian:buster-slim AS build
RUN apt-get update && \
  apt-get install --no-install-suggests --no-install-recommends --yes python3-venv gcc libpython3-dev tar xz-utils wget ffmpeg && \
  python3 -m venv /venv && \
  /venv/bin/pip install --upgrade pip

FROM build AS build-venv
COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

FROM gcr.io/distroless/python3-debian10
COPY --from=build-venv /usr/bin/ff** /usr/local/bin/
COPY --from=build-venv /venv /venv

COPY . /code
WORKDIR /code

ENTRYPOINT ["/venv/bin/python3", "main.py"]

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"
