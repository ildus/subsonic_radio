FROM alpine:edge
RUN apk add yt-dlp ffmpeg rsync python3 py3-pip \
  && pip3 install --break-system-packages ytmusicapi py-sonic
ENV PYTHONUNBUFFERED=1
RUN mkdir /app && chmod a+rwx /app
COPY ./main.py ./yt.py /app/
WORKDIR /app
ENTRYPOINT ["python3", "/app/main.py"]
