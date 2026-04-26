# shinebridge — ShineWiFi-F Modbus TCP Server with Web GUI

A Python application that exposes ShineWiFi-F solar inverter data as a **Modbus TCP server** (port 5279) with an optional MQTT bridge and Streamlit dashboard.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  ShineWiFi-F │────▶│  shinebridge │────▶│   MQTT       │
│  (Modbus TCP │     │              │     │   broker     │
│   Server)    │◀────│  Modbus TCP  │◀────│  (optional)  │
└──────────────┘     │  Server      │     └──────────────┘
                     │              │
                     │  Streamlit   │
                     │  Dashboard   │
                     └──────────────┘
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run with default config.yaml
python -m shinebridge

# Custom config path
SHINEBRIDGE_CONFIG_PATH=/path/to/config.yaml python -m shinebridge
```

## Configuration

Edit `config.yaml` to customize:

- **Modbus server**: host, port (default 5279), device ID
- **MQTT bridge**: broker address, topic prefix, credentials
- **Register mapping**: which registers to expose and their data types
- **Dashboard**: Streamlit port (default 8503)
- **Logging**: rotation size, retention period

### Environment Variable Overrides

Prefix all config keys with `SHINEBRIDGE_`:

```bash
export SHINEBRIDGE_MODBUS_PORT=5279
export SHINEBRIDGE_MQTT_BROKER="192.168.10.1"
python -m shinebridge
```

## Register Map (Input Registers)

| Reg | Name              | Type   | Multiplier | Description                  |
|-----|-------------------|--------|------------|------------------------------|
| 0   | Device_Status     | uint32 | 1          | System status flags          |
| 1   | Grid_Voltage      | uint16 | 0.1        | AC grid voltage (V)          |
| 2   | Grid_Current      | uint16 | 0.1        | AC grid current (A)          |
| 3   | Grid_Power        | int32  | 0.1        | AC output power (W, signed)  |
| 4   | Grid_Energy       | uint32 | 0.1        | Total energy exported (kWh)  |
| 5   | Grid_Frequency    | uint16 | 0.1        | AC grid frequency (Hz)       |
| 6   | PV1_Voltage       | uint16 | 0.1        | PV1 panel voltage (V)        |
| 7   | PV1_Current       | uint16 | 0.1        | PV1 panel current (A)        |
| 8   | PV2_Voltage       | uint16 | 0.1        | PV2 panel voltage (V)        |
| 9   | PV2_Current       | uint16 | 0.1        | PV2 panel current (A)        |
| 10  | Battery_Voltage   | uint16 | 0.1        | Battery voltage (V)          |
| 11  | Battery_Current   | int16  | 0.1        | Battery current (A, signed)  |
| 12  | Battery_Power     | int32  | 0.1        | Battery power (W, signed)    |
| 13  | Battery_SOC       | uint16 | 1          | Battery state of charge (%)  |
| 14  | Battery_Temperature|int16 | 0.1        | Battery temperature (°C)     |
| 15  | Inverter_Temp     | int16  | 0.1        | Internal temperature (°C)    |
| 16  | Daily_Energy      | uint32 | 0.1        | Today's energy production    |
| 17  | Total_Energy      | uint32 | 0.1        | Lifetime total energy (kWh)  |

## Modbus TCP Server

- **Port**: 5279 (configurable)
- **Supported functions**: Read Input Registers (0x04), Write Single Register (0x06), Write Multiple Registers (0x10)
- **Register range**: 0–99 (input), 0–99 (holding)

## MQTT Bridge

Publishes register values as JSON every `update_interval` seconds:

```json
{
  "timestamp": "2025-04-26T12:00:00Z",
  "registers": {
    "Grid_Voltage": 230.5,
    "Grid_Power": 1250.0,
    "Battery_SOC": 85
  }
}
```

Topic format: `{topic_prefix}/status` (e.g., `Inverter/status`)

## Streamlit Dashboard

Access at `http://localhost:8503`:

- Real-time register values with color-coded status indicators
- Historical data chart from CSV log
- Manual holding register write interface
- MQTT connection status panel

## Project Structure

```
shinebridge/
├── config.yaml              # Main configuration file
├── requirements.txt         # Python dependencies
├── __main__.py             # Entry point (python -m shinebridge)
├── core/                   # Core infrastructure
│   ├── config.py           # Pydantic-settings config model
│   ├── logging_setup.py    # Loguru initialization
│   ├── register_store.py   # Thread-safe in-memory register map
│   └── decoder.py          # uint16/uint32/int32 decode + encode
├── modbus/                 # Modbus TCP server implementation
│   └── server.py           # (Phase 2)
├── mqtt/                   # MQTT bridge implementation
│   └── bridge.py           # (Phase 2)
├── dashboard/              # Streamlit web UI
│   └── app.py              # (Phase 3)
├── data/                   # Runtime data storage
│   └── history.csv         # Historical register values
├── logs/                   # Log files
└── tests/                  # Test suite
    ├── test_config.py      # Config loading tests
    ├── test_register_store.py  # Register store unit tests
    └── integration/        # Integration tests
```

## Development Phases

- **Phase 1** ✅ — Core infrastructure (config, logging, register store, decoder)
- **Phase 2** ✅ — Modbus TCP server + MQTT bridge
- **Phase 3** ✅ — Streamlit dashboard with real-time updates and historical charts

## Running the Application

### Start Modbus Server Only
```bash
cd /mnt/smb_homes/hermes-agent/shinebridge
python -m modbus.server
```

### Start Full Stack (Server + Dashboard)
```bash
cd /mnt/smb_homes/hermes-agent/shinebridge
streamlit run dashboard/app.py --server.port 8503
```

### Access Points
- **Modbus Server:** `0.0.0.0:5279` (TCP, register map in config.yaml)
- **MQTT Broker:** `localhost:1883` (topic prefix: `shinebridge`)
- **Dashboard:** `http://localhost:8503` (Streamlit web app)

## Configuration

Edit `config.yaml` to customize:
- Modbus server host/port
- MQTT broker settings
- Register mapping and update interval
- History logging path and retention
