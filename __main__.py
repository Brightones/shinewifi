"""shinebridge — ShineWiFi-F Modbus TCP Server with Web GUI.

Usage:
    python -m shinebridge              # Start server (default config.yaml)
    SHINEBRIDGE_CONFIG_PATH=/path/to/config.yaml python -m shinebridge  # Custom path
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def main():
    parser = argparse.ArgumentParser(description="ShineWiFi-F Modbus TCP Server")
    parser.add_argument("--config", "-c", default=None, help="Path to config.yaml")
    args = parser.parse_args()

    # Import after path setup
    from core.config import load_config
    from core.logging_setup import setup_logging
    from modbus.server import ModbusServer
    from mqtt.bridge import MQTTBridge
    from dashboard.app import run_dashboard

    # Load config and logging
    config = load_config(args.config)
    setup_logging(
        level=config.loguru.level,
        rotation=config.loguru.rotation,
        retention=config.loguru.retention,
    )

    logger.info("Starting shinebridge...")
    logger.info(f"  Modbus: {config.modbus.host}:{config.modbus.port}")
    logger.info(f"  MQTT:   {config.mqtt.broker}:{config.mqtt.port}/{config.mqtt.topic_prefix}")
    logger.info(f"  Dashboard: http://0.0.0.0:{config.dashboard.port}")

    # Initialize components
    server = ModbusServer(config)
    mqtt_bridge = MQTTBridge(config) if config.mqtt.enabled else None

    try:
        # Start Modbus TCP server (blocking)
        logger.info("Modbus TCP server started")
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if mqtt_bridge:
            mqtt_bridge.disconnect()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    main()
