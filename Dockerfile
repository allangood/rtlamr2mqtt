FROM golang:alpine3.12 as builder

WORKDIR /go/src/app

RUN go get github.com/bemasher/rtlamr \
    && apk update \
    && apk add --no-cache libtool libusb-dev librtlsdr-dev rtl-sdr autoconf cmake git make gcc musl-dev \
    && git clone https://github.com/merbanan/rtl_433.git \
    && cd rtl_433 \
    && mkdir build && cd build \
    && cmake .. \
    && make \
    && make install

FROM python:rc-alpine3.12
COPY --from=builder /go/bin/rtlamr* /usr/bin/
COPY --from=builder /usr/local/bin/rtl* /usr/bin/
COPY --from=builder /usr/local/etc/rtl_433/ /etc/rtl_433/
COPY ./rtlamr2mqtt.py /usr/bin

RUN apk update \
    && apk add rtl-sdr \
    && pip3 install paho-mqtt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
