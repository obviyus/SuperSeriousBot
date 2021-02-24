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
    && apt-get install -y \
        # cloudmersive
        gcc musl-dev libffi-dev \
        # pillow
        bash \
    && pip3 install --no-cache-dir -r requirements.txt \
    && apt-get remove gcc musl-dev -y \
    && apt-get autoremove -y

# command to run on container start
CMD [ "python", "./main.py" ]
