FROM ubuntu:24.04

RUN apt update
RUN apt install -y ffmpeg

WORKDIR /media

COPY grabacion.mp4 .

ENTRYPOINT ffmpeg -re -i grabacion.mp4 -c:v libx264 -c:a aac -f flv rtmp://nginx-c/hls/my-video