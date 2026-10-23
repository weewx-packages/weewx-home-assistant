# SPDX-License-Identifier: MIT
"""WeeWX extension installer for weewx-home-assistant.

Copies the weewx_ha package below bin/user and registers the Controller
service. The package files are listed one by one because the WeeWX installer
does not copy directories. A test compares the list with the files on disk.
"""

import importlib.util
import sys

from weecfg.extension import ExtensionInstaller

# Third-party modules the service needs at run time. WeeWX does not install
# Python dependencies, so the installer only warns when they are missing.
REQUIRED_MODULES = {"paho.mqtt.client": "paho-mqtt>=2.0", "pydantic": "pydantic>=2.7"}

PACKAGE_DIR = "bin/user/weewx_ha"
PACKAGE_FILES = [
    "__init__.py",
    "_version.py",
    "config_publisher.py",
    "controller.py",
    "preprocessor.py",
    "state_publisher.py",
    "utils.py",
]
MODEL_FILES = [
    "__init__.py",
    "extension_config.py",
    "mqtt_config.py",
    "station_info.py",
    "tls_config.py",
]


def loader():
    """Return the installer, warning about missing Python packages.

    Returns:
        HomeAssistantInstaller: The installer for this extension.
    """
    missing = []
    for module, requirement in REQUIRED_MODULES.items():
        try:
            found = importlib.util.find_spec(module) is not None
        except ImportError:
            found = False
        if not found:
            missing.append(requirement)
    if missing:
        print(
            "Warning: the Home Assistant extension needs these Python packages "
            "in the WeeWX environment: %s. Install them before starting WeeWX."
            % " ".join(f"'{m}'" for m in missing),
            file=sys.stderr,
        )
    return HomeAssistantInstaller()


class HomeAssistantInstaller(ExtensionInstaller):
    """Installer for the Home Assistant MQTT discovery service."""

    def __init__(self):
        super().__init__(
            version="1.1.0",
            name="home-assistant",
            description="Publish WeeWX data to Home Assistant with MQTT discovery.",
            author="Mark Feldhousen and weewx-packages contributors",
            report_services="user.weewx_ha.Controller",
            # The empty required values make the service log a configuration
            # error and stay inactive until the user fills them in.
            config={
                "HomeAssistant": {
                    "node_id": "weewx",
                    "mqtt": {"hostname": "", "username": "", "password": ""},
                    "station": {
                        "name": "Weather Station",
                        "model": "",
                        "manufacturer": "",
                    },
                }
            },
            files=[
                (PACKAGE_DIR, [f"{PACKAGE_DIR}/{name}" for name in PACKAGE_FILES]),
                (
                    f"{PACKAGE_DIR}/models",
                    [f"{PACKAGE_DIR}/models/{name}" for name in MODEL_FILES],
                ),
            ],
        )
