FROM python:3-alpine
RUN apk add yt-dlp ffmpeg \
  && python3 -m pip install ytmusicapi py-sonic
ENV PYTHONUNBUFFERED=1
RUN mkdir /app && chmod a+rwx /app
COPY ./main.py ./yt.py /app/
WORKDIR /app
ENTRYPOINT ["python3", "/app/main.py"]
