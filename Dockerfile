# set base image (host OS)
FROM python:3.8-alpine

# set the working directory in the container
WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# copy the content of the local src directory to the working directory
COPY / .

# install dependencies
RUN apk update \
    && apk add --no-cache gcc libressl-dev musl-dev libffi-dev jpeg-dev zlib-dev bash \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apk del gcc musl-dev

# command to run on container start
CMD [ "python", "./main.py" ]
