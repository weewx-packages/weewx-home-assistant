"""Tests for the WeeWX extension installer."""

# Standard Python Libraries
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess  # nosec B404
import sys

# Third-Party Libraries
import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "bin" / "user" / "weewx_ha"
WEECTL = Path(sys.executable).parent / "weectl"


def load_installer():
    """Load the installer object defined by install.py."""
    spec = importlib.util.spec_from_file_location("ha_install", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.loader()


def test_installer_lists_every_package_file():
    """A module missing from install.py would be missing on the station (#29)."""
    listed = {source for _, sources in load_installer()["files"] for source in sources}
    on_disk = {
        path.relative_to(ROOT).as_posix()
        for path in PACKAGE.rglob("*.py")
        if "__pycache__" not in path.parts
    }
    assert listed == on_disk


def test_installer_version_matches_package():
    """The installer and the package report the same version."""
    # Geekpad Libraries
    import weewx_ha

    assert load_installer()["version"] == weewx_ha.__version__


@pytest.mark.skipif(not WEECTL.exists(), reason="weectl is not installed")
def test_install_into_station_and_import(tmp_path):
    """Install into a fresh station, import every module, then uninstall (#29)."""
    station = tmp_path / "station"
    conf = station / "weewx.conf"

    def weectl(*args):
        subprocess.run(  # nosec B603
            [str(WEECTL), *args], cwd=tmp_path, check=True, capture_output=True
        )

    weectl("station", "create", str(station), "--no-prompt")
    weectl("extension", "install", str(ROOT), "--config", str(conf), "--yes")

    # The service is registered and the configuration section is present.
    # Third-Party Libraries
    import configobj

    config = configobj.ConfigObj(str(conf), encoding="utf-8")
    assert "user.weewx_ha.Controller" in config["Engine"]["Services"]["report_services"]
    assert config["HomeAssistant"]["node_id"] == "weewx"

    # Every installed module imports the way weewxd imports it, and the
    # service loads from the installed configuration without starting MQTT.
    script = (
        "import configobj, importlib, pathlib, types\n"
        "base = pathlib.Path('user/weewx_ha')\n"
        "for path in sorted(base.rglob('*.py')):\n"
        "    parts = path.with_suffix('').parts\n"
        "    if parts[-1] == '__init__':\n"
        "        parts = parts[:-1]\n"
        "    importlib.import_module('.'.join(parts))\n"
        "from user.weewx_ha import Controller\n"
        f"cfg = configobj.ConfigObj({str(conf)!r}, encoding='utf-8')\n"
        "controller = Controller(types.SimpleNamespace(), cfg)\n"
        "assert controller.mqtt_client is None\n"
        "controller.shutDown()\n"
    )
    env = os.environ | {
        "PYTHONPATH": str(station / "bin"),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    subprocess.run(  # nosec B603
        [sys.executable, "-c", script],
        cwd=station / "bin",
        env=env,
        check=True,
        capture_output=True,
    )

    weectl("extension", "uninstall", "home-assistant", "--config", str(conf), "--yes")
    config = configobj.ConfigObj(str(conf), encoding="utf-8")
    assert (
        "user.weewx_ha.Controller"
        not in config["Engine"]["Services"]["report_services"]
    )
    assert "HomeAssistant" not in config
    assert not list(station.glob("bin/user/weewx_ha/*.py"))
    shutil.rmtree(station)
