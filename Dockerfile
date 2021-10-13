FROM debian:buster-slim AS builder
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update \
  && apt-get install --no-install-suggests --no-install-recommends --yes python3-venv gcc libpython3-dev tar xz-utils wget \
  && python3 -m venv /venv \
  && /venv/bin/pip install --upgrade pip

FROM builder as build-env

COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install -r /requirements.txt

RUN wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
  && tar xJvf ffmpeg-git-amd64-static.tar.xz

FROM gcr.io/distroless/python3-debian10
COPY --from=build-env /ffmpeg-git-**-amd64-static/ffmpeg /usr/local/bin/
COPY --from=build-env /venv /venv
COPY --from=build-env . /code

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"

WORKDIR /code
ENTRYPOINT ["/venv/bin/python3", "main.py"]
