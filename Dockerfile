# Build Stage 1
FROM python:3.9-slim AS build-env
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y tar xz-utils wget

RUN wget https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
  && tar xJvf ffmpeg-git-amd64-static.tar.xz

WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies in a virtualenv
RUN python3 -m venv venv \
  && export PATH="/code/venv/bin:$PATH" \
  && pip3 install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY . .

# Build Stage 2
FROM gcr.io/distroless/python3

# Copy the ffmpeg binary over
COPY --from=build-env /ffmpeg-git-**-amd64-static/ff* /usr/local/bin/

# Copy source from build image to final image
COPY --from=build-env /code /code

WORKDIR /code

ENV PYTHONUNBUFFERED 0
ENV PATH="/code/venv/bin:$PATH"

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"

# command to run on container start
ENTRYPOINT [ "python3", "main.py" ]
