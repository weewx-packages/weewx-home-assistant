# weewx-home-assistant

WeeWX service that publishes loop packets to Home Assistant over MQTT discovery.
Continuation of felddy/weewx-home-assistant under weewx-packages (catalog id
`home-assistant`, MIT license, keep `LICENSE` and the copyright). Default branch
`develop`.

## Phase

Alpha. A few fast smoke tests, no coverage targets. No compatibility shims for
old config or data formats. The catalog contracts of the organization workspace
still apply: packages are never replaced after release.

## Layout

- `bin/user/weewx_ha/` is the payload. The installer copies it to
  `bin/user/weewx_ha` of a station, where it loads as `user.weewx_ha`.
  `pyproject.toml` maps the same directory to the top-level module `weewx_ha`
  for pip. Use relative imports only.
- `install.py` is the WeeWX installer (`name='home-assistant'`). It lists every
  package file by hand. `tests/test_install.py` fails if the list and the files
  differ.
- The version lives in `bin/user/weewx_ha/_version.py` and in `install.py`. A
  test checks that they match. Add a `CHANGELOG.md` entry with every bump.
- Config model: `bin/user/weewx_ha/models/extension_config.py`. The README
  option tables must match it.
- Sensor metadata (device class, state class, units): `bin/user/weewx_ha/utils.py`.
  Home Assistant rejects a whole entity for an invalid device class and unit
  pair. Check new entries against Home Assistant's `DEVICE_CLASS_UNITS` and
  `DEVICE_CLASS_STATE_CLASSES` (`homeassistant/components/sensor/const.py`).

## Commands

- Tests, about 1 s: `python -m pytest tests`. Needs weewx, paho-mqtt, pydantic
  and pytest in the environment. The install test needs `weectl` next to the
  interpreter.
- Python 3.10 and 3.14 must pass.

## Style

The code is annotated and uses numpy-style docstrings. Keep that. Formatting is
black.
