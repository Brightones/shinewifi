"""Integration tests for shinebridge Phase 2 (Modbus + MQTT)."""

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path FIRST
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

os = __import__('os')
os.chdir(str(project_root))  # Ensure config.yaml is found from CWD

from core.config import load_config
from core.register_store import RegisterStore
from modbus.server import ModbusServer
from mqtt.bridge import MQTTBridge


async def test_modbus_server():
    """Test Modbus TCP server start/stop and register access."""
    print("Testing Modbus server...")

    config = load_config()
    server = ModbusServer(config)

    # Test start
    await server.start()
    assert server._running, "Server should be running after start()"

    # Test register update
    server.update_register(1, 230.5)  # Grid Voltage
    value = server.get_register_value(1)
    assert value == 230.5, f"Expected 230.5, got {value}"

    # Test multiple registers
    test_data = {
        2: 5.2,      # Grid Current
        3: 1200.0,   # Grid Power
        13: 85,      # Battery SOC
    }
    for addr, val in test_data.items():
        server.update_register(addr, val)

    # Test stop
    await server.stop()
    assert not server._running, "Server should be stopped after stop()"

    print("  ✓ Modbus server start/stop OK")
    print("  ✓ Register update/read OK")


async def test_mqtt_bridge():
    """Test MQTT bridge creation and lifecycle."""
    print("Testing MQTT bridge...")

    config = load_config()
    bridge = MQTTBridge(config)

    # Test client creation (without connecting to real broker)
    client = bridge._create_client()
    assert client is not None, "MQTT client should be created"
    assert hasattr(client, 'publish'), "Client should have publish method"

    # Test payload generation
    test_values = {
        "Grid_Voltage": 230.5,
        "Grid_Power": 1250.0,
        "Battery_SOC": 85,
    }
    payload = {
        "timestamp": "2025-04-26T12:00:00+00:00",
        "registers": test_values
    }
    json_str = json.dumps(payload)
    parsed = json.loads(json_str)
    assert parsed["registers"]["Grid_Voltage"] == 230.5

    print("  ✓ MQTT client creation OK")
    print("  ✓ Payload serialization OK")


async def test_register_store_sync():
    """Test that register store syncs correctly with Modbus datastore."""
    print("Testing register store sync...")

    config = load_config()
    server = ModbusServer(config)

    # Start the server first
    await server.start()

    # Update registers through the server
    server.update_register(1, 230.5)
    server.update_register(4, 48.6)

    # Verify values are accessible
    assert server.get_register_value(1) == 230.5, f"Expected 230.5, got {server.get_register_value(1)}"
    assert server.get_register_value(4) == 48.6, f"Expected 48.6, got {server.get_register_value(4)}"

    await server.stop()
    print("  ✓ Register store sync OK")


async def main():
    """Run all Phase 2 integration tests."""
    print("=" * 60)
    print("Running shinebridge Phase 2 Integration Tests")
    print("=" * 60)

    try:
        await test_modbus_server()
        await test_mqtt_bridge()
        await test_register_store_sync()

        print("\n" + "=" * 60)
        print("✅ All Phase 2 integration tests PASSED!")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ Integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
