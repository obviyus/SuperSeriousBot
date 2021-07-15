# set base image (host OS)
FROM python:3.9-slim

# set the working directory in the container
WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# copy the content of the local src directory to the working directory
COPY / .

# install dependencies
RUN apt-get update \
    && apt-get install gcc musl-dev -y --no-install-recommends \
    && pip3 install --no-cache-dir -r requirements.txt \
    && pip3 install youtube-dl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"

# command to run on container start
CMD [ "python", "main.py" ]
