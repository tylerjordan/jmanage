FROM alpine:3.4

MAINTAINER Tyler Jordan <tjordan@juniper.net>

RUN mkdir /jmanage

WORKDIR /jmanage

## Copy project inside the container
ADD jmanage.py jmanage.py
ADD utility.py utility.py
ADD data data


## Install dependancies and Pyez
RUN apk update \
    && apk upgrade \
    && apk add build-base gcc g++ make python-dev py-pip py-lxml \
    libxslt-dev libxml2-dev libffi-dev openssl-dev curl \
    ca-certificates openssl wget prettytable jxmlease ipaddress \
    junos_eznc

## Run the jmanage script
CMD ["python", "jmanage.py"]
