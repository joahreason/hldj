# syntax=docker/dockerfile:1
FROM python:3.10

RUN apt-get -y update && \
    apt-get install -y ffmpeg && \
    mkdir -p /user/src/bot

WORKDIR /usr/src/bot

COPY . .

RUN pip install -r requirements.txt

CMD [ "python", "hldj.py" ]