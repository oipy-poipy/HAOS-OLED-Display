# HA Pi Panel

A Home Assistant OS add-on for the Raspberry Pi that cycles status pages on a small I2C OLED display: SSD1306 128x64 (for example the Dorhea 0.96 inch), SSD1306 128x32 (the common 0.91 inch modules) or SH1106 128x64.

## Setup

1. Wire the display to the Pi: VCC to 3.3V or 5V (whichever the module is rated for), GND to GND, SDA to SDA, SCL to SCL.
2. Enable I2C on Home Assistant OS. On the boot partition, add `dtparam=i2c_arm=on` to `config.txt`, and create `CONFIG/modules/rpi-i2c.conf` containing `i2c-dev`. Reboot the host. The community [HassOS I2C Configurator](https://community.home-assistant.io/t/add-on-hassos-i2c-configurator/264167) add-on can make these changes for you.
3. Copy this folder to `/addons/ha_pi_panel` on the host, reload the add-on store, and install **HA Pi Panel**.

## Options

| Option | Meaning |
| --- | --- |
| `display_type` | `ssd1306_128x64`, `ssd1306_128x32` or `sh1106_128x64` |
| `display_i2c_address` | Usually `0x3C`, sometimes `0x3D` |
| `display_rotate` | Rotation in degrees: 0, 90, 180 or 270 |
| `display_contrast` | Brightness from 0 to 255 |
| `display_page_seconds` | How long each page stays on screen |
| `display_pages_json` | The pages (see below) |

## Pages

`display_pages_json` is a JSON list of pages. Each page has a list of `lines`. A 64 pixel high display fits 5 lines, a 32 pixel high one fits 3.

- A line that starts with `#` is drawn as an inverted header bar.
- A tab (`\t` in JSON) splits a line into a label and a right-aligned value.
- Text that does not fit is shortened with `…`.

Tokens in curly braces are filled in each time a page is shown:

| Token | Value |
| --- | --- |
| `{hostname}`, `{ip}` | Name and LAN address of the Home Assistant host |
| `{clock}`, `{date}` | `HH:MM` and `YYYY-MM-DD` |
| `{uptime_short}` | Host uptime, for example `3d 4h` |
| `{cpu_temp_c}`, `{cpu_load_1m}` | CPU temperature and 1 minute load average |
| `{mem_percent}`, `{disk_percent}` | Memory and disk usage in percent |

Home Assistant entities use `{ha:<entity_id>[@<attribute>][,<fallback>...][|<format>]}`:

- `{ha:sensor.outdoor_temperature}` shows the state.
- `{ha:weather.forecast_home@temperature}` shows an attribute.
- `{ha:sensor.outdoor_temperature,weather.forecast_home@temperature}` shows the first one that has a usable value.
- `|1°C` rounds to 1 decimal and appends `°C`. The format is an optional number of decimals followed by any suffix.

Weather states such as `partlycloudy` are shown as readable labels such as `Part cloud`. A value that cannot be read is shown as `--`.

The default pages:

```json
[
  {"name": "System", "lines": [
    "#{hostname}\t{clock}",
    "CPU\t{cpu_temp_c}°C",
    "RAM\t{mem_percent}%",
    "Disk\t{disk_percent}%"
  ]},
  {"name": "Network", "lines": [
    "#Network\t{clock}",
    "IP\t{ip}",
    "Up\t{uptime_short}",
    "Load\t{cpu_load_1m}"
  ]},
  {"name": "Home", "lines": [
    "#Home\t{clock}",
    "Out\t{ha:sensor.outdoor_temperature,weather.forecast_home@temperature,weather.home@temperature|1°C}",
    "Sky\t{ha:weather.forecast_home,weather.home}",
    "Hum\t{ha:sensor.outdoor_humidity,weather.forecast_home@humidity|0%}",
    "Wind\t{ha:weather.forecast_home@wind_speed,weather.home@wind_speed|0 km/h}"
  ]}
]
```

## Troubleshooting

- **`I2C device not found: /dev/i2c-1`**: I2C is not enabled. Follow step 2 of the setup and reboot the host.
- **`I2C device not found on address`**: Check the wiring and `display_i2c_address`. Try `0x3D`.
- **A value shows `--`**: The add-on log explains why, once per problem. A missing entity is logged as `HTTP Error 404`. Entity ids are case sensitive and are listed under Developer Tools, States. If nothing is logged, the entity exists but its value is unknown, unavailable, or the attribute name is wrong.
- **Turning the display off**: Stop the add-on. The display is blanked on exit, and automations can do this with the `hassio.addon_stop` and `hassio.addon_start` actions.
- **The add-on stopped after an error**: Turn on Watchdog on the add-on page and it will be restarted automatically.
