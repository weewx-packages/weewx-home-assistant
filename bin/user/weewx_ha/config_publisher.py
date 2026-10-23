"""Processes loop packets and publish MQTT discovery configurations."""

# Standard Python Libraries
import json
import logging
import threading
from typing import Any
from zoneinfo import ZoneInfo

# Third-Party Libraries
import paho.mqtt.client as mqtt
from weewx.units import to_std_system  # type: ignore

from .models import StationInfo
from .utils import UnitSystem, get_key_config, get_unit_metadata

logger = logging.getLogger(__name__)


class ConfigPublisher:
    """Process loop packets and publish MQTT discovery configurations.

    Attributes
    ----------
    availability_topic : str
        The MQTT topic for availability status.
    discovery_topic_prefix : str
        The prefix for MQTT discovery topics.
    mqtt_client : mqtt.Client
        The MQTT client used for publishing messages.
    node_id : str
        The unique identifier for the node.
    state_topic_prefix : str
        The prefix for MQTT state topics.
    unit_system : UnitSystem
        The unit system to use for measurements.
    retain_discovery : bool
        Whether discovery messages are published with the MQTT retain flag.
    seen_measurements : dict of str to dict of str to Any
        A dictionary to hold measurement metadata.
    """

    def __init__(
        self,
        mqtt_client: mqtt.Client,
        availability_topic: str,
        discovery_topic_prefix: str,
        state_topic_prefix: str,
        node_id: str,
        station_info: StationInfo,
        unit_system: UnitSystem = UnitSystem.METRICWX,
        retain_discovery: bool = True,
    ):
        """
        Initialize the ConfigPublisher.

        Parameters
        ----------
        mqtt_client : mqtt.Client
            The MQTT client used for publishing messages.
        availability_topic : str
            The MQTT topic for availability status.
        discovery_topic_prefix : str
            The prefix for MQTT discovery topics.
        state_topic_prefix : str
            The prefix for MQTT state topics.
        node_id : str
            The unique identifier for the node.
        station_info : StationInfo
            The weather station information.
        unit_system : UnitSystem, optional
            The unit system to use for measurements (default is UnitSystem.METRICWX).
        retain_discovery : bool, optional
            Publish discovery messages with the MQTT retain flag (default is True).
        """
        self.availability_topic: str = availability_topic
        self.discovery_topic_prefix: str = discovery_topic_prefix
        self.mqtt_client: mqtt.Client = mqtt_client
        self.node_id: str = node_id
        self.retain_discovery: bool = retain_discovery
        self.state_topic_prefix: str = state_topic_prefix
        self.unit_system: UnitSystem = unit_system

        # Device metadata to include in discovery configurations
        self.device_description: dict[str, Any] = {
            "device": {
                "identifiers": [self.node_id],
                "name": station_info.name,
                "model": station_info.model,
                "manufacturer": station_info.manufacturer,
            }
        }

        self.time_zone: ZoneInfo = station_info.time_zone

        # Dictionary to hold measurement configuration and metadata. Worker
        # threads add keys in process_packet() while others iterate it in
        # publish_discovery(), so every access that iterates or inserts goes
        # through this lock. An entry is inserted only once it is complete,
        # because the state publisher reads entries without taking the lock.
        self.seen_measurements: dict[str, dict[str, Any]] = {}
        self._measurements_lock = threading.Lock()

    def process_packet(self, packet: dict) -> bool:
        """
        Process packet and compose discovery configurations.

        Parameters
        ----------
        packet : dict
            The packet of measurements to process.

        Returns
        -------
        bool
            True if new measurements were discovered, False otherwise.

        """
        logger.debug("Processing packet")
        found_new_measurements = False
        if self.unit_system is not None:
            packet = to_std_system(packet, int(self.unit_system))
        with self._measurements_lock:
            for key in packet.keys():
                if key in self.seen_measurements:
                    continue
                logger.debug(f"Discovered new measurement: {key}")
                found_new_measurements = True
                config = dict(get_key_config(key))
                # Unit metadata is underlaid with the metadata from the key
                unit_metadata = get_unit_metadata(key, self.unit_system)
                config["metadata"] = unit_metadata | config.get("metadata", {})
                self.seen_measurements[key] = config
        return found_new_measurements

    def publish_discovery(self) -> None:
        """Publish discovery configurations for Home Assistant.

        This method publishes MQTT discovery configurations for each sensor
        in previously seen measurements to allow Home Assistant to automatically
        discover and configure the sensors.

        Parameters
        ----------
        None

        Returns
        -------
        None
        """
        # Iterate over a snapshot: process_packet() may add measurements from
        # another thread while the (slow) MQTT publishes below are running.
        with self._measurements_lock:
            measurements = list(self.seen_measurements.items())
        logger.info(f"Publishing {len(measurements)} discovery configurations")
        for sensor_name, config in measurements:
            # Construct discovery topic
            integration = config.get("integration", "sensor")
            discovery_topic = f"{self.discovery_topic_prefix}/{integration}/{self.node_id}/{sensor_name}/config"
            # Construct the configuration payload
            payload: dict[str, Any] = (
                {
                    "availability_topic": self.availability_topic,
                    "state_topic": f"{self.state_topic_prefix}/{sensor_name}",
                    "unique_id": f"{self.node_id}_{sensor_name}",
                }
                | config.get("metadata", {})
                | self.device_description
            )

            # Remove any keys with None values
            payload = {k: v for k, v in payload.items() if v is not None}

            logger.debug(
                f"Publishing discovery configuration: {discovery_topic}: {payload}"
            )
            # Publish the discovery configuration
            self.mqtt_client.publish(
                discovery_topic, json.dumps(payload), retain=self.retain_discovery
            )
