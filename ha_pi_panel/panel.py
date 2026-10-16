"""HA Pi Panel: cycle status pages on a small I2C OLED display."""

import functools
import itertools
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import time
import urllib.request

from luma.core.interface.serial import i2c
from luma.core.render import canvas
import luma.oled.device
from PIL import ImageFont

# Pillow's built-in font. Smaller sizes lose colons and decimal points on a 1 bit display.
FONT = ImageFont.load_default(10)
# {name} is a value from TOKENS, {ha:...} a Home Assistant entity.
TOKEN = re.compile(r"\{(ha:[^}]+|\w+)\}")
# Home Assistant weather states are machine readable, not display ready.
WEATHER = {
    "clear-night": "Clear", "cloudy": "Cloudy", "exceptional": "Alert", "fog": "Fog", "hail": "Hail",
    "lightning": "Storm", "lightning-rainy": "Storm/rain", "partlycloudy": "Part cloud",
    "pouring": "Heavy rain", "rainy": "Rain", "snowy": "Snow", "snowy-rainy": "Sleet",
    "sunny": "Sunny", "windy": "Windy", "windy-variant": "Windy",
}


def supervisor(path):
    """GET a Supervisor API path. Paths under /core/api/ are proxied to Home Assistant."""
    token = os.environ["SUPERVISOR_TOKEN"]
    request = urllib.request.Request("http://supervisor" + path, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.load(response)


def host_ip():
    # The add-on container has an address of its own, so ask the Supervisor for the host's.
    interfaces = supervisor("/network/info")["data"]["interfaces"]
    primary = next(interface for interface in interfaces if interface["primary"])
    return primary["ipv4"]["address"][0].split("/")[0]


def uptime():
    minutes = int(time.clock_gettime(time.CLOCK_BOOTTIME)) // 60
    days, hours, minutes = minutes // 1440, minutes // 60 % 24, minutes % 60
    if days:
        return f"{days}d {hours}h"
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def mem_percent():
    info = dict(line.split(":") for line in Path("/proc/meminfo").read_text().splitlines())
    total, available = (int(info[key].split()[0]) for key in ("MemTotal", "MemAvailable"))
    return round(100 * (total - available) / total)


def disk_percent():
    disk = shutil.disk_usage("/")
    return round(100 * disk.used / disk.total)


TOKENS = {
    "hostname": lambda: supervisor("/host/info")["data"]["hostname"],
    "ip": host_ip,
    "clock": lambda: time.strftime("%H:%M"),
    "date": lambda: time.strftime("%Y-%m-%d"),
    "uptime_short": uptime,
    "cpu_temp_c": lambda: f"{int(Path('/sys/class/thermal/thermal_zone0/temp').read_text()) / 1000:.1f}",
    "cpu_load_1m": lambda: f"{os.getloadavg()[0]:.2f}",
    "mem_percent": mem_percent,
    "disk_percent": disk_percent,
}


@functools.cache
def warn_once(message):
    logging.warning(message)


@functools.cache  # Cleared for every page, so each entity is fetched once per page.
def entity(entity_id):
    try:
        return supervisor("/core/api/states/" + entity_id)
    except Exception as error:
        warn_once(f"Cannot read {entity_id} from Home Assistant: {error}")


def ha_value(spec):
    """Resolve "entity[@attribute],fallback...|format" to the first usable value."""
    refs, _, fmt = spec.partition("|")
    digits = fmt[:1] if fmt[:1].isdigit() else ""  # "|1°C" rounds to one decimal and appends °C.
    for ref in refs.split(","):
        entity_id, _, attribute = ref.strip().partition("@")
        state = entity(entity_id)
        if state is None:
            continue
        value = str(state["attributes"].get(attribute) if attribute else state["state"])
        if value.lower() in ("unknown", "unavailable", "none", ""):
            continue
        if digits:
            value = f"{float(value):.{digits}f}"
        return WEATHER.get(value, value) + fmt[len(digits):]
    return "--"


def fill(text):
    """Replace the tokens in text, showing -- for any value that cannot be read."""

    def value(match):
        token = match[1]
        try:
            return ha_value(token[3:]) if token.startswith("ha:") else str(TOKENS[token]())
        except Exception as error:
            warn_once(f"Cannot show {{{token}}}: {error!r}")
            return "--"

    return TOKEN.sub(value, text)


def fit(draw, text, width):
    """Shorten text with an ellipsis until it is at most width pixels wide."""
    while len(text) > 1 and draw.textlength(text, font=FONT) > width:
        text = text[:-2] + "…"
    return text


def show(device, lines):
    row_height = 10 if device.height <= 32 else 12  # 3 rows on a 32 pixel display, 5 on a 64 pixel one.
    with canvas(device) as draw:
        for row, line in enumerate(lines[: device.height // row_height]):
            top, ink = row * row_height, "white"
            if line.startswith("#"):  # A header: dark text on a light bar.
                line, ink = line[1:], "black"
                draw.rectangle((0, top, device.width - 1, top + row_height - 1), fill="white")
            left, _, right = line.partition("\t")  # A tab right-aligns the rest of the line.
            right = fit(draw, fill(right), device.width - 4)
            left = fit(draw, fill(left), device.width - 8 - draw.textlength(right, font=FONT))
            draw.text((2, top), left, font=FONT, fill=ink)
            draw.text((device.width - 2, top), right, font=FONT, fill=ink, anchor="ra")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    options = json.loads(Path("/data/options.json").read_text())
    pages = json.loads(options["display_pages_json"])
    driver, size = options["display_type"].split("_")  # For example ssd1306_128x64.
    width, height = map(int, size.split("x"))
    device = getattr(luma.oled.device, driver)(
        i2c(port=1, address=int(options["display_i2c_address"], 0)),
        width=width,
        height=height,
        rotate=int(options["display_rotate"]) // 90,
    )
    device.contrast(options["display_contrast"])
    # luma blanks the display when Python exits, so make SIGTERM a normal exit.
    signal.signal(signal.SIGTERM, lambda *_: sys.exit())
    logging.info("Showing %d pages on %s", len(pages), options["display_type"])
    for page in itertools.cycle(pages):
        entity.cache_clear()
        show(device, page["lines"])
        time.sleep(options["display_page_seconds"])


if __name__ == "__main__":
    main()
