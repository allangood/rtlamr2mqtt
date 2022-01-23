FROM golang:bullseye as go-builder

WORKDIR /go/src/app

RUN go install github.com/bemasher/rtlamr@latest \
    && apt-get update \
    && apt-get install -y libusb-1.0-0-dev build-essential git cmake \
    && git clone git://git.osmocom.org/rtl-sdr.git \
    && cd rtl-sdr \
    && mkdir build && cd build \
    && cmake .. -DDETACH_KERNEL_DRIVER=ON -DENABLE_ZEROCOPY=ON -Wno-dev \
    && make \
    && make install

FROM debian:bullseye-slim

COPY --from=go-builder /usr/local/lib/librtl* /lib/
COPY --from=go-builder /go/bin/rtlamr* /usr/bin/
COPY --from=go-builder /usr/local/bin/rtl* /usr/bin/
COPY ./rtlamr2mqtt.py /usr/bin

RUN apt-get update \
    && apt-get install -o Dpkg::Options::="--force-confnew" -y \
      python3-paho-mqtt \
      python3-yaml \
      python3-tinydb \
      python3-sklearn \
      python3-requests \
      libusb-1.0-0 \
    && apt-get --purge autoremove -y perl \
    && apt-get clean \
    && find /var/lib/apt/lists/ -type f -delete \
    && rm -rf /usr/share/doc \
    && mkdir /var/lib/rtlamr2mqtt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py

STOPSIGNAL SIGTERM

VOLUME ["/var/lib/rtlamr2mqtt"]

ENTRYPOINT ["/usr/bin/rtlamr2mqtt.py"]
