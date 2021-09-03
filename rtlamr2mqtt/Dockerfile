FROM python:3.6.14-alpine3.13

ARG BUILD_ARCH

ENV RTLAMR_VERSION=v0.9.1

COPY ./rtlamr2mqtt.py /usr/bin
COPY ./requirements.txt /tmp

WORKDIR /tmp
RUN apk update \
    && apk add rtl-sdr \
    && pip3 install -r /tmp/requirements.txt \
    && chmod 755 /usr/bin/rtlamr2mqtt.py \
    && echo ${BUILD_ARCH} \
    && echo ${BUILD_ARCH} \
    && echo ${BUILD_ARCH} \
    && echo ${BUILD_ARCH} \
    && echo ${BUILD_ARCH} \
    && case ${BUILD_ARCH} in \
         "linux/amd64")  ARCH=amd64  ;; \
         "linux/arm64")  ARCH=arm64  ;; \
         "linux/arm/v7") ARCH=arm    ;; \
         "linux/arm/v6") ARCH=arm    ;; \
         "linux/386")    ARCH=i386   ;; \
    esac \
    && wget https://github.com/bemasher/rtlamr/releases/download/v0.9.1/rtlamr_linux_amd64.tar.gz \
    # && wget https://github.com/bemasher/rtlamr/releases/download/${RTLAMR_VERSION}/rtlamr_linux_${ARCH}.tar.gz \
    && tar zxvf rtlamr_linux_${ARCH}.tar.gz \
    && chmod 755 rtlamr \
    && mv rtlamr /usr/bin \
    && rm -f /tmp/*

STOPSIGNAL SIGTERM
CMD ["/usr/bin/rtlamr2mqtt.py"]



https://github.com/bemasher/rtlamr/releases/download/v0.9.1/rtlamr_linux_amd64.tar.gz \