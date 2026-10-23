"""Tests for the publishers and the controller, using a fake MQTT client."""

# Standard Python Libraries
import json
from types import SimpleNamespace

# Third-Party Libraries
import pytest

# Geekpad Libraries
from weewx_ha import (
    ConfigPublisher,
    Controller,
    ExtensionConfig,
    PacketPreprocessor,
    StatePublisher,
    UnitSystem,
)
from weewx_ha.models import StationInfo

DISCOVERY_PREFIX = "homeassistant"
STATE_PREFIX = "weather"


class FakeMQTTClient:
    """Record publishes instead of talking to a broker."""

    def __init__(self):
        """Start with an empty record."""
        self.published = []

    def publish(self, topic, payload=None, qos=0, retain=False):
        """Remember the message."""
        self.published.append((topic, payload, retain))


def make_publishers(unit_system=UnitSystem.METRICWX, **options):
    """Create a connected pair of publishers around one fake client."""
    client = FakeMQTTClient()
    config = ConfigPublisher(
        client,
        f"{STATE_PREFIX}/status",
        DISCOVERY_PREFIX,
        STATE_PREFIX,
        "weewx",
        StationInfo(name="Test", model="Model", manufacturer="Maker"),
        unit_system,
        **{k: v for k, v in options.items() if k == "retain_discovery"},
    )
    state = StatePublisher(
        client,
        config,
        STATE_PREFIX,
        unit_system,
        **{k: v for k, v in options.items() if k != "retain_discovery"},
    )
    return client, config, state


def discovery_payloads(client):
    """Map sensor name to the decoded discovery payload."""
    return {
        topic.split("/")[-2]: json.loads(payload)
        for topic, payload, _ in client.published
        if topic.endswith("/config")
    }


def packet(unit_system=UnitSystem.METRICWX, **values):
    """Build a loop packet in the given unit system."""
    return {"usUnits": int(unit_system), "dateTime": 1700000000} | values


def test_discovery_survives_measurement_added_while_publishing():
    """A measurement added mid-publish must not break the iteration (#42)."""
    client, config, _ = make_publishers()
    config.process_packet(packet(outTemp=1.0, rainRate=0.0))

    def publish_and_add(topic, payload=None, qos=0, retain=False):
        # Stands in for another worker thread that discovers a new key while
        # publish_discovery() is still working through the old ones.
        if "pressure" not in config.seen_measurements:
            config.process_packet(packet(pressure=1000.0))

    client.publish = publish_and_add
    config.publish_discovery()

    assert "pressure" in config.seen_measurements


def test_seen_measurements_only_hold_complete_entries():
    """The state publisher reads entries unlocked, so they must be complete (#42)."""
    _, config, _ = make_publishers()
    config.process_packet(packet(dayRain=1.0))
    assert config.seen_measurements["dayRain"]["metadata"]["name"]
    assert config.seen_measurements["dayRain"]["metadata"]["unit_of_measurement"]


def test_discovery_is_retained_by_default_and_can_be_switched_off():
    """Discovery messages carry the retain flag unless disabled (#19)."""
    for option, expected in ((None, True), (True, True), (False, False)):
        options = {} if option is None else {"retain_discovery": option}
        client, config, _ = make_publishers(**options)
        config.process_packet(packet(outTemp=1.0))
        config.publish_discovery()
        flags = {retain for topic, _, retain in client.published}
        assert flags == {expected}, option


def test_state_is_not_retained_by_default_and_can_be_retained():
    """State messages carry the retain flag only on request (#39)."""
    for option, expected in ((None, False), (True, True)):
        options = {} if option is None else {"retain_state": option}
        client, config, state = make_publishers(**options)
        data = packet(outTemp=1.0)
        config.process_packet(data)
        state.process_packet(data)
        flags = {retain for _, _, retain in client.published}
        assert flags == {expected}, option


def test_state_class_in_discovery():
    """Accumulators are total_increasing, other numbers measurement (#40, #39)."""
    client, config, _ = make_publishers()
    config.process_packet(
        packet(
            dayRain=1.0,
            outTemp=1.0,
            extraTemp1=2.0,
            windDir=90.0,
            extraAlarm1=0,
        )
    )
    config.publish_discovery()
    payloads = discovery_payloads(client)

    assert payloads["dayRain"]["state_class"] == "total_increasing"
    assert payloads["outTemp"]["state_class"] == "measurement"
    assert payloads["extraTemp1"]["state_class"] == "measurement"
    assert payloads["windDir"]["state_class"] == "measurement"
    # Timestamps, enumerations and binary sensors have no state class.
    assert "state_class" not in payloads["dateTime"]
    assert "state_class" not in payloads["usUnits"]
    assert "state_class" not in payloads["extraAlarm1"]


@pytest.mark.parametrize(
    "unit_system,unit",
    [(UnitSystem.US, "in/h"), (UnitSystem.METRICWX, "mm/h")],
)
def test_rain_rate_unit_is_accepted_by_home_assistant(unit_system, unit):
    """Home Assistant rejects inch_per_hour for precipitation_intensity (#33)."""
    client, config, _ = make_publishers(unit_system)
    config.process_packet(packet(unit_system, rainRate=0.0))
    config.publish_discovery()
    assert discovery_payloads(client)["rainRate"]["unit_of_measurement"] == unit


def test_state_messages_and_json_message():
    """One JSON object carries every published value of a packet (#15)."""
    client, config, state = make_publishers(json_topic="weather/loop")
    data = packet(outTemp=21.5, rainRate=None, unknownThing=1.0)
    config.process_packet(packet(outTemp=21.5, rainRate=0.0))
    state.process_packet(data)

    topics = {topic: payload for topic, payload, _ in client.published}
    assert topics["weather/outTemp"] == 21.5
    assert "weather/rainRate" not in topics
    assert json.loads(topics["weather/loop"]) == {
        "usUnits": "METRICWX",
        "dateTime": "2023-11-14T22:13:20+00:00",
        "outTemp": 21.5,
    }


def test_no_json_message_by_default():
    """Without json_topic only the per-sensor topics are published (#15)."""
    client, config, state = make_publishers()
    data = packet(outTemp=21.5)
    config.process_packet(data)
    state.process_packet(data)
    assert all(topic.startswith("weather/") for topic, _, _ in client.published)
    assert "weather/loop" not in {topic for topic, _, _ in client.published}


def test_loop_packet_is_copied_before_preprocessing():
    """The preprocessor must not change the engine's packet (#22)."""
    submitted = []
    controller = object.__new__(Controller)
    controller.mqtt_client = SimpleNamespace(is_connected=lambda: True)
    controller.executor = SimpleNamespace(
        submit=lambda fn, *args: submitted.append((fn, args))
        or SimpleNamespace(add_done_callback=lambda cb: None)
    )
    controller.packet_preprocessor = PacketPreprocessor()
    event = SimpleNamespace(packet={"usUnits": 17, "txBatteryStatus": 5})

    controller.on_weewx_loop(event)
    fn, args = submitted[0]
    result = fn(*args)

    assert event.packet == {"usUnits": 17, "txBatteryStatus": 5}
    assert "txBatteryStatus" not in result
    assert result["batteryStatusISS"] == 1


def test_invalid_configuration_leaves_service_inactive():
    """The placeholder configuration of the installer must not break WeeWX."""
    controller = Controller(SimpleNamespace(), {"HomeAssistant": {"node_id": "weewx"}})
    assert controller.mqtt_client is None
    controller.shutDown()


def test_extension_config_options():
    """New options have defaults and accept the strings WeeWX hands over."""
    base = {
        "node_id": "weewx",
        "mqtt": {"hostname": "h", "username": "u", "password": "p"},
        "station": {"name": "n", "model": "m", "manufacturer": "x"},
    }
    config = ExtensionConfig.from_config_dict({"HomeAssistant": base}, "HomeAssistant")
    assert config.retain_discovery is True
    assert config.retain_state is False
    assert config.json_topic is None

    options = {"retain_discovery": "false", "retain_state": "true", "json_topic": "a/b"}
    config = ExtensionConfig.from_config_dict(
        {"HomeAssistant": base | options}, "HomeAssistant"
    )
    assert config.retain_discovery is False
    assert config.retain_state is True
    assert config.json_topic == "a/b"
