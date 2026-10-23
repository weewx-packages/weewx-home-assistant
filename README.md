# weewx-home-assistant

A [WeeWX](https://weewx.com/) service that publishes weather data to
[Home Assistant](https://www.home-assistant.io/) over MQTT. It uses MQTT
discovery, so Home Assistant creates the weather entities itself, and it reports
availability through the MQTT last will. It does not read the station and does
not install or configure the MQTT broker.

This is a continuation of
[felddy/weewx-home-assistant](https://github.com/felddy/weewx-home-assistant),
which is no longer maintained.

## Requirements

- An MQTT broker that Home Assistant and WeeWX can both reach, and the MQTT
  integration set up in Home Assistant.
- The Python packages `paho-mqtt` 2.0 or later and `pydantic` 2.7 or later in
  the Python environment that runs WeeWX. WeeWX does not install them. For a
  pip-based WeeWX, run this in the WeeWX virtual environment:

  ```shell
  pip install 'paho-mqtt>=2.0' 'pydantic>=2.7'
  ```

  For a package-based WeeWX, install both for the system Python that runs
  `weewxd`.

## Installation

Install `home-assistant` from the [WeeWX packages catalog](https://github.com/weewx-packages/catalog/blob/main/packages/home-assistant.md).
The catalog page lists the current release, its WeeWX and Python
requirements, and the install, update and removal commands.

The extension runs on the machine that runs WeeWX, not on Home Assistant.

The installer registers `user.weewx_ha.Controller` in `report_services` and adds
a `[HomeAssistant]` section to `weewx.conf`. The section has empty values for
the broker and the station, so the service logs a configuration error and stays
inactive until you fill them in. Edit the section, then restart WeeWX.

## Configuration

```ini
[HomeAssistant]
    node_id = weewx
    [[mqtt]]
        hostname = mqtt.example.com
        username = mqttUser
        password = mqttPassword
    [[station]]
        name = Weather Station
        model = Vantage Vue
        manufacturer = Davis
```

`node_id` groups the entities in the MQTT discovery topic. `station.name` is the
device name in Home Assistant and the prefix of every entity name.

| Option | Default |
|---|---|
| `discovery_topic_prefix` | `homeassistant` |
| `json_topic` | not set |
| `node_id` | required, letters, digits, `_` and `-` |
| `retain_discovery` | `true` |
| `retain_state` | `false` |
| `state_topic_prefix` | `weather` |
| `unit_system` | `METRICWX`, or `METRIC`, `US` |

`[[mqtt]]`:

| Option | Default |
|---|---|
| `client_id` | not set |
| `hostname` | required |
| `keep_alive` | `60` |
| `password` | required |
| `port` | `8883` |
| `use_tls` | `true` |
| `username` | required |

`[[[tls]]]` below `[[mqtt]]` has the optional settings `cadata`, `cafile`,
`capath`, `certfile`, `keyfile` and `password`. See
[`ssl.create_default_context`](https://docs.python.org/3/library/ssl.html#ssl.create_default_context)
for the first three and
[`ssl.SSLContext.load_cert_chain`](https://docs.python.org/3/library/ssl.html#ssl.SSLContext.load_cert_chain)
for the others.

`[[station]]`:

| Option | Default |
|---|---|
| `manufacturer` | required |
| `model` | required |
| `name` | required |
| `time_zone` | `UTC` |

- `time_zone` is an IANA zone name such as `America/New_York`. Some drivers
  report `sunrise`, `sunset` and `stormStart` as local clock time. The extension
  reads that clock time as time in `time_zone` and publishes it as a UTC
  timestamp. `dateTime` is a real epoch time and is always published as a UTC
  timestamp. Home Assistant shows timestamps in its own time zone.
- `retain_discovery` keeps the discovery messages on the broker, so entities
  survive a restart of Home Assistant or the broker. A sensor that WeeWX stops
  reporting stays on the broker until you clear its retained discovery topic.
- `retain_state` keeps the last value of every sensor topic on the broker.
- `json_topic` names a topic that receives one JSON object with all values of
  each loop packet, in addition to the per-sensor topics. Use it for consumers
  such as Node-RED that want a packet as a whole.
- Numeric sensors have a `state_class`, so Home Assistant records long-term
  statistics for them. Daily, monthly and yearly accumulators such as `dayRain`
  are `total_increasing`.

## Limitations

- Not tested on real station hardware or against a running Home Assistant. The
  tests use a fake MQTT client. The discovery payloads were checked offline
  against the MQTT sensor schema of Home Assistant 2026.2.
- Home Assistant rejects the discovery message of a few sensors because the
  WeeWX unit does not fit the device class: `o3` and `so2` in ppm, `soilMoist`
  in centibar, `leafWet` as a count, and `rainRate` and `snowRate` with
  `unit_system = METRIC` (cm/h). The other sensors are not affected.
- If the broker cannot be reached when WeeWX starts, the service raises an
  error and WeeWX does not start.

## Development

```shell
pip install weewx paho-mqtt pydantic pytest
python -m pytest tests
```

The tests install the extension into a temporary station with `weectl`. They
skip that test if `weectl` is not next to the Python interpreter.

## License

Copyright (c) 2024 Mark Feldhousen. Released under the [MIT license](LICENSE).
