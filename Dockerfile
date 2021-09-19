FROM python:rc-alpine3.14
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
RUN echo "$BUILDPLATFORM $BUILDOS $BUILDARCH $BUILDVARIANT $TARGETPLATFORM $TARGETOS $TARGETARCH $TARGETVARIANT"
RUN apk update \
    && apk add rtl-sdr \
    && pip3 install -r /tmp/requirements.txt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py \
    && case ${BUILDARCH} in \
         "linux/amd64")  ARCH=amd64  ;; \
         "linux/arm64")  ARCH=arm64  ;; \
         "linux/arm/v7") ARCH=arm    ;; \
         "linux/arm/v6") ARCH=arm    ;; \
         "linux/386")    ARCH=i386   ;; \
    esac \
    && wget https://github.com/bemasher/rtlamr/releases/download/${RTLAMR_VER}/rtlamr_linux_${ARCH}.tar.gz \
    && tar zxvf rtlamr_linux_${ARCH}.tar.gz \
    && chmod 755 rtlamr \
    && mv rtlamr /usr/bin \
    && rm -f /tmp/*

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]
