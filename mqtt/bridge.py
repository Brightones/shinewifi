"""MQTT bridge for publishing ShineWiFi-F register data."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import paho.mqtt.client as mqtt
from loguru import logger

from core.config import AppConfig


class MQTTBridge:
    """Bridges Modbus register values to MQTT topics."""

    def __init__(self, config: AppConfig):
        self.config = config
        self._client: Optional[mqtt.Client] = None
        self._running = False
        self._publish_task: Optional[asyncio.Task] = None
        self._register_values: dict[str, float] = {}

    def _create_client(self) -> mqtt.Client:
        """Create and configure the MQTT client."""
        client_id = f"shinebridge-{id(self):x}"[:23]  # Max 23 chars for MQTT client ID
        client = mqtt.Client(client_id=client_id, clean_session=True)

        if self.config.mqtt.username:
            client.username_pw_set(
                username=self.config.mqtt.username,
                password=self.config.mqtt.password or ""
            )

        # Set callbacks
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.on_publish = self._on_publish

        return client

    def _on_connect(self, client, userdata, flags, rc):
        """Called when MQTT connection is established."""
        if rc == 0:
            logger.info(f"MQTT connected to {self.config.mqtt.broker}:{self.config.mqtt.port}")
            # Subscribe to command topics (for future write-back)
            cmd_topic = f"{self.config.mqtt.topic_prefix}/command/+"
            client.subscribe(cmd_topic, qos=self.config.mqtt.qos)
            logger.info(f"Subscribed to {cmd_topic}")
        else:
            error_msg = {0: "Success", 1: "Connection refused (incorrect protocol)",
                        2: "Connection refused (bad identifier)", 3: "Connection refused (server unavailable)",
                        4: "Connection refused (bad username/password)", 5: "Connection refused (not authorized)"}[rc]
            logger.error(f"MQTT connection failed: {error_msg}")

    def _on_disconnect(self, client, userdata, rc):
        """Called when MQTT connection is lost."""
        if rc != 0:
            logger.warning(f"MQTT disconnected unexpectedly (rc={rc})")
        else:
            logger.info("MQTT disconnected normally")

    def _on_publish(self, client, userdata, mid):
        """Called when a message is published."""
        pass  # Could add retry logic here if needed

    async def start(self):
        """Start the MQTT bridge."""
        if self._running:
            logger.warning("MQTT bridge already running")
            return

        try:
            self._client = self._create_client()
            self._client.connect(
                host=self.config.mqtt.broker,
                port=self.config.mqtt.port,
                keepalive=60
            )
            self._client.loop_start()  # Start network thread
            self._running = True

            # Wait for connection
            await asyncio.sleep(1)

            if self._client.is_connected():
                logger.info(f"MQTT bridge started on {self.config.mqtt.broker}:{self.config.mqtt.port}")
            else:
                logger.warning("MQTT client created but not yet connected")

        except Exception as e:
            logger.error(f"Failed to start MQTT bridge: {e}")
            self._running = False

    async def stop(self):
        """Stop the MQTT bridge."""
        if not self._running or not self._client:
            return

        logger.info("Stopping MQTT bridge...")
        self._running = False

        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception as e:
            logger.error(f"Error stopping MQTT client: {e}")

        self._client = None
        logger.info("MQTT bridge stopped")

    async def publish_registers(self, register_values: dict[str, float]):
        """Publish all register values to MQTT."""
        if not self._running or not self._client or not self._client.is_connected():
            return

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "registers": {}
        }

        for name, value in register_values.items():
            # Round to reasonable precision
            if abs(value) >= 100:
                payload["registers"][name] = round(value, 1)
            elif abs(value) >= 1:
                payload["registers"][name] = round(value, 2)
            else:
                payload["registers"][name] = round(value, 3)

        topic = f"{self.config.mqtt.topic_prefix}/status"
        try:
            result = self._client.publish(
                topic,
                json.dumps(payload),
                qos=self.config.mqtt.qos,
                retain=False
            )
            result.wait_for_publish()
            logger.debug(f"Published {len(payload['registers'])} registers to {topic}")
        except Exception as e:
            logger.error(f"Failed to publish MQTT message: {e}")

    async def periodic_publish(self, register_store):
        """Periodically publish register values from the store."""
        while self._running:
            try:
                # Collect all non-stale register values
                values = {}
                for reg_addr in range(100):
                    entry = register_store.input_registers.get(reg_addr)
                    if entry and hasattr(entry, 'decoded_value') and not register_store.is_stale(reg_addr):
                        name = entry.name or f"reg_{reg_addr}"
                        values[name] = entry.decoded_value

                if values:
                    await self.publish_registers(values)
            except Exception as e:
                logger.error(f"Error in periodic publish: {e}")

            await asyncio.sleep(self.config.registers.update_interval)

    async def run_periodic(self, register_store):
        """Start the MQTT bridge and begin periodic publishing."""
        await self.start()
        if not self._running:
            return

        self._publish_task = asyncio.create_task(
            self.periodic_publish(register_store)
        )

        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._publish_task:
                self._publish_task.cancel()
            await self.stop()

    def get_client(self) -> Optional[mqtt.Client]:
        """Get the underlying MQTT client for direct use."""
        return self._client
