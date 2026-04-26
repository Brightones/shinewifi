#!/usr/bin/env python3
"""Wrapper script to start the shinebridge Modbus server."""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent  # go up from bin/ to project root
sys.path.insert(0, str(project_root))

from core.config import load_config
from core.logging_setup import setup_logging
from modbus.server import ModbusServer
import asyncio

def main():
    config = load_config()
    setup_logging(
        level=config.loguru.level,
        rotation=config.loguru.rotation,
        retention=config.loguru.retention,
    )

    server = ModbusServer(config)
    
    try:
        asyncio.run(server.serve_forever())
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
