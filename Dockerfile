FROM python:3.10-slim-bullseye

RUN apt-get update && \
  apt-get install --no-install-suggests --no-install-recommends --yes gcc ffmpeg libc6-dev

COPY requirements.txt /requirements.txt
RUN pip install --disable-pip-version-check -r /requirements.txt

COPY . /code
WORKDIR /code

ENTRYPOINT ["python3", "/code/main.py"]

LABEL org.opencontainers.image.source="https://github.com/obviyus/SuperSeriousBot"
