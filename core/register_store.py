"""Thread-safe in-memory register map for shinebridge."""

import csv
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RegisterEntry:
    """Single register entry with metadata and value tracking."""
    name: str
    reg_type: str  # 'uint16', 'uint32', 'int32'
    raw_value: int = 0
    decoded_value: float = 0.0
    last_updated: float = field(default_factory=time.time)
    multiplier: float = 1.0


class RegisterStore:
    """Thread-safe in-memory register map serving as single source of truth.

    Both MQTT and Modbus layers read from/write to this store — no direct coupling.
    Uses threading.RLock for concurrent access safety between async Modbus + sync MQTT threads.
    """

    def __init__(self):
        self._lock = threading.RLock()
        # Input registers (0x04) — sensor readings, read-only from device
        self.input_registers: dict[int, RegisterEntry] = {}
        # Holding registers (0x03/0x06) — writable config
        self.holding_registers: dict[int, RegisterEntry] = {}

    def initialize_input(self, mapping: dict[str, int], reg_type: str = "uint16", multiplier: float = 1.0) -> None:
        """Initialize input register map from configuration.

        Args:
            mapping: {register_name: address} dictionary.
            reg_type: Data type for all registers ('uint16', 'uint32', 'int32').
            multiplier: Default multiplier for decoded values.
        """
        with self._lock:
            for name, addr in mapping.items():
                if addr not in self.input_registers:
                    self.input_registers[addr] = RegisterEntry(
                        name=name,
                        reg_type=reg_type,
                        multiplier=multiplier,
                    )

    def initialize_holding(self, mapping: dict[str, int], default_values: Optional[dict[int, int]] = None) -> None:
        """Initialize holding register map from configuration.

        Args:
            mapping: {register_name: address} dictionary.
            default_values: Optional {address: initial_value} overrides.
        """
        with self._lock:
            for name, addr in mapping.items():
                if addr not in self.holding_registers:
                    init_val = (default_values or {}).get(addr, 0)
                    self.holding_registers[addr] = RegisterEntry(
                        name=name,
                        reg_type="uint16",
                        raw_value=init_val,
                    )

    # --- Input Register Operations ---

    def read_input(self, addr: int, count: int = 1) -> list[int]:
        """Read one or more consecutive input registers.

        Args:
            addr: Starting register address.
            count: Number of registers to read.

        Returns:
            List of raw uint16 values (0-65535).
        """
        with self._lock:
            return [self.input_registers.get(addr + i, RegisterEntry(name=f"unknown_{addr+i}", reg_type="uint16")).raw_value for i in range(count)]

    def update_input(self, addr: int, value) -> None:
        """Update an input register with a raw or decoded value.

        Args:
            addr: Register address.
            value: Raw uint16 value (int 0-65535) OR decoded float (will be converted to raw).
        """
        # Convert float to int if needed (handle both raw and decoded values)
        is_decoded = isinstance(value, float)
        if is_decoded:
            entry = self.input_registers.get(addr)
            multiplier = entry.multiplier if entry else 1.0
            raw_val = int(value / multiplier) if multiplier != 1.0 else int(value)
        else:
            raw_val = int(value)

        with self._lock:
            if addr not in self.input_registers:
                # Auto-create entry for unknown registers
                self.input_registers[addr] = RegisterEntry(name=f"unknown_{addr}", reg_type="uint16")
            
            entry = self.input_registers[addr]
            entry.raw_value = raw_val & 0xFFFF  # Mask to uint16
            
            if is_decoded:
                entry.decoded_value = value  # Store the decoded float directly
            else:
                entry.decoded_value = raw_val * entry.multiplier  # Reconstruct from raw
            
            entry.last_updated = time.time()

    def update_input_uint32(self, addr_high: int, value_low: int) -> None:
        """Update a uint32 register (stored as two consecutive uint16 registers).

        The high word is at addr_high, low word at addr_high + 1.

        Args:
            addr_high: Address of the high word register.
            value_low: Value to write to the low word register.
        """
        with self._lock:
            # High word already set via update_input(addr_high, high_value)
            if addr_high + 1 not in self.input_registers:
                entry_hi = self.input_registers.get(addr_high)
                name = (entry_hi.name or "") + "_lo" if entry_hi else "unknown_lo"
                self.input_registers[addr_high + 1] = RegisterEntry(
                    name=name,
                    reg_type="uint32_lo",
                )
            self.input_registers[addr_high + 1].raw_value = value_low & 0xFFFF

    # --- Holding Register Operations ---

    def read_holding(self, addr: int, count: int = 1) -> list[int]:
        """Read one or more consecutive holding registers.

        Args:
            addr: Starting register address.
            count: Number of registers to read.

        Returns:
            List of raw uint16 values (0-65535).
        """
        with self._lock:
            return [self.holding_registers.get(addr + i, RegisterEntry(name=f"unknown_{addr+i}", reg_type="uint16")).raw_value for i in range(count)]

    def write_holding(self, addr: int, values: list[int]) -> None:
        """Write one or more consecutive holding registers.

        Args:
            addr: Starting register address.
            values: List of uint16 values to write (0-65535).
        """
        with self._lock:
            for i, val in enumerate(values):
                reg_addr = addr + i
                if reg_addr not in self.holding_registers:
                    self.holding_registers[reg_addr] = RegisterEntry(
                        name=f"unknown_{reg_addr}",
                        reg_type="uint16",
                    )
                self.holding_registers[reg_addr].raw_value = val & 0xFFFF
                self.holding_registers[reg_addr].last_updated = time.time()

    # --- Metadata Queries ---

    def get_register_info(self, addr: int) -> Optional[RegisterEntry]:
        """Get metadata for a register (input or holding).

        Args:
            addr: Register address.

        Returns:
            RegisterEntry if found, None otherwise.
        """
        with self._lock:
            return self.input_registers.get(addr) or self.holding_registers.get(addr)

    def get_input_names(self) -> dict[int, str]:
        """Get mapping of input register addresses to names.

        Returns:
            {address: name} dictionary.
        """
        with self._lock:
            return {addr: entry.name for addr, entry in self.input_registers.items()}

    def get_holding_names(self) -> dict[int, str]:
        """Get mapping of holding register addresses to names.

        Returns:
            {address: name} dictionary.
        """
        with self._lock:
            return {addr: entry.name for addr, entry in self.holding_registers.items()}

    def get_last_updated(self, addr: int) -> float:
        """Get last update timestamp for a register.

        Args:
            addr: Register address.

        Returns:
            Unix timestamp of last update (0 if not found).
        """
        with self._lock:
            entry = self.input_registers.get(addr) or self.holding_registers.get(addr)
            return entry.last_updated if entry else 0.0

    def is_stale(self, addr: int, threshold_seconds: float = 60.0) -> bool:
        """Check if a register's data is stale (no update within threshold).

        Args:
            addr: Register address.
            threshold_seconds: Maximum age in seconds before considered stale.

        Returns:
            True if data is older than threshold, False otherwise.
        """
        with self._lock:
            entry = self.input_registers.get(addr) or self.holding_registers.get(addr)
            if not entry:
                return True  # Unknown register = stale
            return (time.time() - entry.last_updated) > threshold_seconds

    def get_all_input_values(self) -> dict[int, int]:
        """Get all input register values as {address: value} dictionary.

        Returns:
            Copy of current input register state.
        """
        with self._lock:
            return {addr: entry.raw_value for addr, entry in self.input_registers.items()}

    def get_all_holding_values(self) -> dict[int, int]:
        """Get all holding register values as {address: value} dictionary.

        Returns:
            Copy of current holding register state.
        """
        with self._lock:
            return {addr: entry.raw_value for addr, entry in self.holding_registers.items()}

    def get_all_decoded_values(self) -> dict[int, float]:
        """Get all input register decoded values as {address: value} dictionary.

        Returns:
            Copy of current decoded input register state.
        """
        with self._lock:
            return {addr: entry.decoded_value for addr, entry in self.input_registers.items()}

    def write_history_csv(self, filepath: str) -> None:
        """Write all input register values to a CSV file for historical logging.

        Args:
            filepath: Path to the output CSV file.
        """
        with self._lock:
            values = {addr: entry.decoded_value 
                     for addr, entry in self.input_registers.items() 
                     if not self.is_stale(addr)}
        
        if not values:
            return

        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'a', newline='') as f:
            writer = csv.writer(f)
            timestamp = time.time()
            row = [timestamp] + [values.get(i, 0.0) for i in range(max(values.keys()) + 1)] if values else [timestamp]
            writer.writerow(row)
