# Changelog

## 1.1.0 - 2026-10-23

First release of the continuation at weewx-packages. Upstream has had no
change since December 2024.

### Added

- `install.py`, so the extension installs with `weectl extension install`. The
  package moved from `src/weewx_ha` to `bin/user/weewx_ha` and loads as
  `user.weewx_ha`. The installer registers `user.weewx_ha.Controller` in
  `report_services`. A pip install still provides the module `weewx_ha`.
  (upstream #29, #24, #18)
- `state_class` in the discovery messages: `total_increasing` for daily,
  monthly and yearly accumulators, `measurement` for other numeric values.
  (upstream #40, #39)
- Option `retain_discovery`, default `true`: discovery messages are retained.
  Before, they were never retained. (upstream #19, #39)
- Option `retain_state`, default `false`: retain the state messages.
  (upstream #39)
- Option `json_topic`, default not set: one JSON object per loop packet.
  (upstream #15)

### Fixed

- `RuntimeError: dictionary changed size during iteration` in
  `publish_discovery()` when new measurements arrive during a publish.
  (upstream #42)
- The loop packet is copied before it is preprocessed. The preprocessor changed
  the dict that other services, such as weewx-mqtt, were iterating.
  (upstream #22)
- Unit metadata for `inch_per_hour`, `mile`, `microgram_per_meter_cubed` and the
  `group_speed2` units. Home Assistant rejected the entities that used them.
  (upstream #33)
- Stopping WeeWX with an invalid `[HomeAssistant]` section raised an
  `AttributeError`.
- README: the option is `time_zone`, not `timezone`, and the README now says what
  it does. (upstream #32)

### Changed

- The weewx test dependency is 5.5.2 (upstream #38). `paho-mqtt` 2.0 or later and
  `pydantic` 2.7 or later are declared as requirements.
- `pytest.ini` no longer enables coverage.
