# set base image (host OS)
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND="noninteractive"

RUN apt-get update && apt-get install -y git tar wget build-essential

RUN apt-get -y install \
    autoconf automake build-essential libtool pkg-config texinfo wget nasm \
    libass-dev libfreetype6-dev libsdl2-dev libtheora-dev \
    libva-dev libvdpau-dev libvorbis-dev libxcb1-dev \
    libxcb-shm0-dev libxcb-xfixes0-dev zlib1g-dev \
    yasm cmake mercurial cmake-curses-gui \
    libx264-dev libx265-dev libnuma-dev libfdk-aac-dev libmp3lame-dev libopus-dev libvpx-dev \
    python3-pip libffi-dev libssl-dev python3-dev

# ffmpeg
RUN mkdir ~/ffmpeg_sources && mkdir ~/ffmpeg_build && mkdir ~/bin

# path where ffmpeg-binaries are emmited to and read from
ENV PATH="~/bin:${PATH}"

# path where ffmpeg looks for vid.stab
# note: $HOME is not available for docker-commands, only for bash-commands. https://github.com/moby/moby/issues/28971
ENV LD_LIBRARY_PATH /root/ffmpeg_build/lib:$LD_LIBRARY_PATH

WORKDIR ~/ffmpeg_sources

# Build vid.stab
RUN git clone https://github.com/georgmartius/vid.stab.git \
      && cd vid.stab \
      && cmake -DCMAKE_INSTALL_PREFIX:PATH=$HOME/ffmpeg_build . \
      && make \
      && make install


## Build ffmpeg
RUN wget http://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 \
    && tar xjvf ffmpeg-snapshot.tar.bz2 \
    && cd ffmpeg \
    && PATH="$HOME/bin:$PATH"   PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" ./configure \
      --prefix="$HOME/ffmpeg_build" \
      --pkg-config-flags="--static" \
      --extra-cflags="-I$HOME/ffmpeg_build/include" \
      --extra-ldflags="-L$HOME/ffmpeg_build/lib" \
      --bindir="$HOME/bin" \
      --enable-gpl \
      --enable-libass \
      --enable-libfdk-aac \
      --enable-libfreetype \
      --enable-libmp3lame \
      --enable-libopus \
      --enable-libtheora \
      --enable-libvorbis \
      --enable-libvpx \
      --enable-libx264 \
      --enable-libx265 \
      --enable-nonfree \
      --enable-libvidstab \
    && PATH="$HOME/bin:$PATH" make \
    && make install \
    && hash -r

# workaround: ffprobe-wrapper doesn't find ffprobe otherwise
RUN cp -r ~/bin/* /bin

WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# copy the content of the local src directory to the working directory
COPY / .

# install dependencies
RUN pip3 install -r requirements.txt

ENV PYTHONUNBUFFERED 0

LABEL org.opencontainers.image.source="https://github.com/Super-Serious/bot"

# command to run on container start
CMD [ "python3", "main.py" ]
