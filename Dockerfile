FROM python:alpine3.14
ARG BUILDPLATFORM
ARG BUILDOS
ARG BUILDARCH
ARG BUILDVARIANT
ARG TARGETPLATFORM
ARG TARGETOS
ARG TARGETARCH
ARG TARGETVARIANT

ENV RTLAMR_VER=v0.9.1

COPY ./rtlamr2mqtt.py /usr/bin
COPY ./requirements.txt /tmp

WORKDIR /tmp
RUN echo "Building to: ${TARGETARCH}" \
    && apk update \
    && apk add rtl-sdr \
    && pip3 install -r /tmp/requirements.txt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py \
    && wget https://github.com/bemasher/rtlamr/releases/download/${RTLAMR_VER}/rtlamr_linux_${TARGETARCH}.tar.gz \
    && tar zxvf rtlamr_linux_${TARGETARCH}.tar.gz \
    && chmod 755 rtlamr \
    && mv rtlamr /usr/bin \
    && rm -f /tmp/*

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
