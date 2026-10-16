FROM ghcr.io/home-assistant/aarch64-base:3.22

# The base image points pip at wheels.home-assistant.io, which has prebuilt
# musl wheels for luma's RPi.GPIO and spidev dependencies.
RUN apk add --no-cache python3 \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir \
      luma.core==2.6.0 \
      luma.oled==3.16.0 \
      pillow==12.3.0 \
      smbus2==0.6.1

COPY panel.py /
# s6-overlay starts CMD with an empty environment; with-contenv restores SUPERVISOR_TOKEN and TZ.
CMD ["/usr/bin/with-contenv", "/opt/venv/bin/python3", "/panel.py"]
