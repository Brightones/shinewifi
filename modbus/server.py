"""Modbus TCP server implementation using pymodbus 3.x."""

import asyncio
import csv
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusDeviceContext,
    ModbusServerContext,
)
from pymodbus.server import StartAsyncTcpServer

from core.config import AppConfig
from core.register_store import RegisterStore


class ModbusServer:
    """Modbus TCP server that exposes ShineWiFi-F register data."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.store = RegisterStore()  # No config argument
        self._context: Optional[ModbusServerContext] = None
        self._server_task: Optional[asyncio.Task] = None
        self._running = False

    async def _create_datastore(self) -> ModbusDeviceContext:
        """Create the pymodbus datastore backed by our RegisterStore."""
        # Initialize register arrays with defaults from config mapping
        input_values = [0] * 100
        holding_values = [0] * 100

        for reg_name, reg_addr in self.config.registers.mapping.items():
            if reg_addr < 100:
                entry = self.store.input_registers.get(reg_addr)
                if entry and hasattr(entry, 'default_value'):
                    raw_val = int(
                        entry.default_value / entry.multiplier
                    ) if entry.multiplier else entry.default_value
                    holding_values[reg_addr] = max(0, min(raw_val, 65535))

        # Create sequential data blocks for input and holding registers
        # Note: pymodbus 3.x requires start address >= 1 (address-1 is used internally)
        input_block = ModbusSequentialDataBlock(1, input_values)
        holding_block = ModbusSequentialDataBlock(1, holding_values)

        # Create device context with the register blocks
        return ModbusDeviceContext(ir=input_block, hr=holding_block)

    async def start(self):
        """Start the Modbus TCP server."""
        if self._running:
            logger.warning("Modbus server already running")
            return

        logger.info(f"Starting Modbus TCP server on {self.config.modbus.host}:{self.config.modbus.port}")

        # Create datastore and context
        device = await self._create_datastore()
        self._context = ModbusServerContext(devices=device)

        # Start async TCP server
        self._server_task = asyncio.create_task(
            StartAsyncTcpServer(
                context=self._context,
                address=(self.config.modbus.host, self.config.modbus.port),
            )
        )

        self._running = True
        logger.info(f"Modbus TCP server listening on {self.config.modbus.host}:{self.config.modbus.port}")

    async def stop(self):
        """Stop the Modbus TCP server."""
        if not self._running:
            return

        logger.info("Stopping Modbus TCP server...")
        self._running = False

        if self._server_task:
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass

        # Clear datastore references to free resources
        if self._context:
            devices = self._context.simdevices
            device_list = devices if isinstance(devices, list) else list(devices.values()) if hasattr(devices, 'values') else [devices]
            for dev in device_list:
                if hasattr(dev, 'ir') and isinstance(dev.ir, ModbusSequentialDataBlock):
                    dev.ir.clear()
                if hasattr(dev, 'hr') and isinstance(dev.hr, ModbusSequentialDataBlock):
                    dev.hr.clear()
            self._context = None

        logger.info("Modbus TCP server stopped")

    def update_register(self, reg_addr: int, value: float):
        """Update a register value from external source (MQTT, manual write)."""
        if not self._running or not self._context:
            return

        # Update our in-memory store
        self.store.update_input(reg_addr, value)

        # Sync to pymodbus datastore using async_setValues
        devices = self._context.simdevices
        if isinstance(devices, list):
            device = devices[0] if devices else None
        elif isinstance(devices, dict):
            device = list(devices.values())[0]
        else:
            device = devices

        if not device:
            return

        if hasattr(device, 'ir') and isinstance(device.ir, ModbusSequentialDataBlock):
            entry = self.store.input_registers.get(reg_addr)
            multiplier = entry.multiplier if entry else 1.0
            raw_val = int(value / multiplier) if multiplier != 1.0 else int(value)
            device.ir.setValues(0, [reg_addr], [max(0, min(raw_val, 65535))])

    def get_register_value(self, reg_addr: int) -> Optional[float]:
        """Get the current decoded value of a register."""
        entry = self.store.input_registers.get(reg_addr)
        if not entry or not hasattr(entry, 'decoded_value'):
            return None
        # Return the stored decoded value directly (already has multiplier applied)
        return entry.decoded_value

    async def serve_forever(self):
        """Start and run the server until cancelled."""
        await self.start()
        
        # Start periodic history logging if enabled
        self._history_task = None
        if self.config.logging.history_enabled:
            self._history_task = asyncio.create_task(
                self._periodic_history_logging()
            )
        
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._history_task:
                self._history_task.cancel()
                try:
                    await self._history_task
                except asyncio.CancelledError:
                    pass
            await self.stop()

    async def _periodic_history_logging(self):
        """Periodically write register values to CSV for historical tracking."""
        while self._running:
            try:
                # Get all non-stale register values
                values = {}
                for reg_addr in range(100):
                    entry = self.store.input_registers.get(reg_addr)
                    if entry and hasattr(entry, 'decoded_value') and not self.store.is_stale(reg_addr):
                        name = entry.name or f"reg_{reg_addr}"
                        values[name] = entry.decoded_value
                
                if values:
                    # Write to CSV
                    filepath = self.config.logging.history_filepath
                    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
                    
                    timestamp = time.time()
                    row = [timestamp] + [values.get(i, 0.0) for i in range(max(values.keys()) + 1)] if values else [timestamp]
                    
                    with open(filepath, 'a', newline='') as f:
                        writer = csv.writer(f)
                        writer.writerow(row)
                
                await asyncio.sleep(self.config.registers.update_interval * 5)  # Log every N refreshes

            except Exception as e:
                logger.error(f"Error in history logging: {e}")
