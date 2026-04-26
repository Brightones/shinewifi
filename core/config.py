"""Configuration schema for shinebridge using pydantic-settings."""

import os
from pathlib import Path
from typing import Optional, Any

import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModbusConfig(BaseSettings):
    """Modbus TCP server settings."""
    host: str = "0.0.0.0"
    port: int = 5279
    device_id: int = 1
    ignore_missing_slaves: bool = True
    timeout: int = 3


class MQTTConfig(BaseSettings):
    """MQTT bridge settings."""
    broker: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""
    topic_prefix: str = "Inverter"
    qos: int = 1


class RegisterMapping(BaseSettings):
    """Register mapping configuration."""
    enabled: bool = True
    update_interval: int = 30
    mapping: dict[str, int] = {}

    model_config = SettingsConfigDict(extra="allow")


class LoggingConfig(BaseSettings):
    """Data logging settings."""
    history_enabled: bool = True
    history_filepath: str = "data/history.csv"
    max_rows: int = 100_000
    flush_interval: int = 60


class DashboardConfig(BaseSettings):
    """Streamlit dashboard settings."""
    enabled: bool = True
    port: int = 8503
    refresh_interval: int = 5
    title: str = "ShineWiFi-F Modbus Server"


class LoguruConfig(BaseSettings):
    """Loguru logging configuration."""
    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"


# Default register definitions for ShineWiFi-F
DEFAULT_REGISTER_DEFINITIONS = {
    "solar_voltage": {"type": "uint16", "unit": "V", "multiplier": 0.1, "description": "Solar panel voltage"},
    "solar_current": {"type": "uint16", "unit": "A", "multiplier": 0.1, "description": "Solar panel current"},
    "solar_power": {"type": "uint32", "unit": "W", "multiplier": 0.1, "description": "Solar panel power"},
    "battery_voltage": {"type": "uint16", "unit": "V", "multiplier": 0.1, "description": "Battery voltage"},
    "battery_current": {"type": "int32", "unit": "A", "multiplier": 0.1, "description": "Battery current (charge/discharge)"},
    "battery_power": {"type": "uint32", "unit": "W", "multiplier": 0.1, "description": "Battery power"},
    "battery_soc": {"type": "uint16", "unit": "%", "multiplier": 1.0, "description": "Battery state of charge"},
    "ac_voltage": {"type": "uint16", "unit": "V", "multiplier": 0.1, "description": "AC output voltage"},
    "ac_frequency": {"type": "uint16", "unit": "Hz", "multiplier": 0.1, "description": "AC output frequency"},
    "ac_power": {"type": "uint32", "unit": "W", "multiplier": 0.1, "description": "AC output power"},
    "daily_energy": {"type": "uint32", "unit": "kWh", "multiplier": 0.1, "description": "Daily energy production"},
    "total_energy": {"type": "uint32", "unit": "kWh", "multiplier": 0.1, "description": "Total energy production"},
    "temperature": {"type": "int32", "unit": "°C", "multiplier": 0.1, "description": "Device temperature"},
    "rssi_signal": {"type": "int32", "unit": "dBm", "multiplier": 1.0, "description": "WiFi signal strength"},
}


class RegisterMapping(BaseSettings):
    """Register mapping configuration."""
    enabled: bool = True
    update_interval: int = 30
    mapping: dict[str, int] = {}
    register_definitions: dict[str, dict] = DEFAULT_REGISTER_DEFINITIONS

    model_config = SettingsConfigDict(extra="allow")


class AppConfig(BaseSettings):
    """Top-level application configuration."""
    modbus: ModbusConfig = ModbusConfig()
    mqtt: MQTTConfig = MQTTConfig()
    registers: RegisterMapping = RegisterMapping()
    logging_cfg: LoggingConfig = LoggingConfig()
    dashboard: DashboardConfig = DashboardConfig()
    loguru: LoguruConfig = LoguruConfig()

    @property
    def logging(self) -> LoggingConfig:
        """Alias for logging_cfg to support config.logging access."""
        return self.logging_cfg

    model_config = SettingsConfigDict(
        env_prefix="SHINEBRIDGE_",
        extra="ignore",
    )


def _flatten_dict(d: dict, parent_key: str = '', sep: str = '.') -> dict:
    """Flatten a nested dictionary for pydantic-settings."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def load_config(path: Optional[str] = None) -> AppConfig:
    """Load configuration from YAML file or environment variables.

    Args:
        path: Optional explicit path to config.yaml. If None, uses default location.

    Returns:
        Fully populated AppConfig instance.
    """
    # Start with defaults
    config_dict = {}
    
    if path is not None:
        config_path = Path(path)
    else:
        # Default: look for config.yaml in the same directory as this file's parent (project root)
        project_root = Path(__file__).resolve().parent.parent
        config_path = project_root / "config.yaml"
    
    # Load YAML if file exists — keep nested structure for pydantic-settings kwargs
    if config_path.exists():
        with open(config_path, 'r') as f:
            yaml_data = yaml.safe_load(f) or {}
        config_dict.update(yaml_data)  # Don't flatten — pass nested dicts to Pydantic
    
    # Override with environment variables (SHINEBRIDGE_ prefix)
    for key, value in os.environ.items():
        if key.startswith("SHINEBRIDGE_"):
            # Convert SHINEBRIDGE_MODBUS_HOST -> modbus.host via nested lookup
            flat_key = key[len("SHINEBRIDGE_"):].lower()
            parts = flat_key.split(".")
            d = config_dict
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value
    
    return AppConfig(**config_dict)
