FROM golang:alpine3.15 as builder

WORKDIR /go/src/app

RUN go get github.com/bemasher/rtlamr \
    && apk update \
    && apk add --no-cache libtool libusb-dev autoconf cmake git make gcc musl-dev \
    && git clone git://git.osmocom.org/rtl-sdr.git \
    && cd rtl-sdr \
    && mkdir build && cd build \
    && cmake .. -DDETACH_KERNEL_DRIVER=ON -Wno-dev \
    && make \
    && make install

FROM python:alpine
COPY --from=builder /go/bin/rtlamr* /usr/bin/
COPY --from=builder /usr/local/bin/rtl* /usr/bin/
COPY --from=builder /usr/local/lib/librtl* /lib/
COPY ./rtlamr2mqtt.py /usr/bin
COPY ./requirements.txt /tmp

RUN apk update \
    && apk add --no-cache libusb gfortran \
    && apk add --no-cache --virtual .build \
      musl-dev \
      gcc \
      g++ \
      lapack-dev \
      libffi-dev \
      libressl-dev \
      musl-dev \
    && pip3 install -r /tmp/requirements.txt \
    && apk del .build \
    && chmod 755 /usr/bin/rtlamr2mqtt.py

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
