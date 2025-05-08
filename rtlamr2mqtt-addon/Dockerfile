# syntax=docker/dockerfile:1
FROM golang:bullseye AS go-builder

WORKDIR /go/src/app

RUN go install github.com/bemasher/rtlamr@latest \
    && apt-get update \
    && apt-get install -y libusb-1.0-0-dev build-essential git cmake \
    && git clone https://git.osmocom.org/rtl-sdr.git \
    && cd rtl-sdr \
    && mkdir build && cd build \
    && cmake .. -DDETACH_KERNEL_DRIVER=ON -DENABLE_ZEROCOPY=ON -Wno-dev \
    && make \
    && make install

FROM python:3.13-slim


ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

COPY --from=go-builder /usr/local/lib/librtl* /lib/
COPY --from=go-builder /go/bin/rtlamr* /usr/bin/
COPY --from=go-builder /usr/local/bin/rtl* /usr/bin/
COPY requirements.txt /tmp
COPY ./app/ $VIRTUAL_ENV/app/

RUN apt-get update \
    && apt-get install -o Dpkg::Options::="--force-confnew" -y \
      libusb-1.0-0 \
    && apt-get --purge autoremove -y \
    && apt-get clean \
    && find /var/lib/apt/lists/ -type f -delete \
    && pip install -r /tmp/requirements.txt \
    && rm -rf /usr/share/doc /tmp/requirements.txt

STOPSIGNAL SIGTERM

ENTRYPOINT ["python", "/opt/venv/app/rtlamr2mqtt.py"]
