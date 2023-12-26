FROM python:3.10-bullseye
LABEL authors="eitchtee"

WORKDIR /

COPY ./requirements.txt ./
RUN pip3 install -r ./requirements.txt
COPY ./src ./
RUN mkdir -p ./data


ENTRYPOINT [ "python3", "-u", "./bot.py" ]