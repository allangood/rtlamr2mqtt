FROM golang:bullseye as go-builder

WORKDIR /go/src/app

RUN go get github.com/bemasher/rtlamr \
    && apt update \
    && apt install -y libusb-1.0-0-dev build-essential git cmake \
    && git clone git://git.osmocom.org/rtl-sdr.git \
    && cd rtl-sdr \
    && mkdir build && cd build \
    && cmake .. -DDETACH_KERNEL_DRIVER=ON -Wno-dev \
    && make \
    && make install

FROM python:slim as python-builder
COPY ./requirements.txt /tmp
RUN apt update \
    && apt install -y gfortran build-essential liblapack-dev libblas-dev\
    && pip3 install -r /tmp/requirements.txt \
    && pip cache purge

FROM python:slim
COPY --from=go-builder /go/bin/rtlamr* /usr/bin/
COPY --from=go-builder /usr/local/bin/rtl* /usr/bin/
COPY --from=go-builder /usr/local/lib/librtl* /lib/
COPY --from=python-builder /usr/local/ /usr/local/
COPY ./rtlamr2mqtt.py /usr/bin

RUN apt update \
    && apt install -y libusb-1.0-0 gfortran libblas3 liblapack3 \
    && apt clean \
    && find /var/lib/apt/lists/ -type f -delete \
    && mkdir /var/lib/rtlamr2mqtt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py

STOPSIGNAL SIGTERM

CMD ["/usr/bin/rtlamr2mqtt.py"]
