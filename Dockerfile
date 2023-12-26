FROM python:3.10-bullseye
LABEL authors="eitchtee"

#RUN sed -i '/pt_BR.UTF-8/s/^# //g' /etc/locale.gen && \
#    locale-gen
#ENV LANG pt_BR.UTF-8
#ENV LANGUAGE pt_BR:en
#ENV LC_ALL pt_BR.UTF-8

WORKDIR /yearinpixels

COPY ./yearinpixels/requirements.txt /
RUN pip3 install -r /requirements.txt
COPY ./src /src


ENTRYPOINT [ "python3", "-u", "./src/bot.py" ]