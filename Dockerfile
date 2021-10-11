# set base image (host OS)
FROM python:3.9-slim
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y ffmpeg

WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip3 install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY . .

ENV PYTHONUNBUFFERED 0

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"

# command to run on container start
CMD [ "python3", "main.py" ]
