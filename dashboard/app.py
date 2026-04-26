"""Streamlit dashboard for ShineWiFi-F monitoring."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import AppConfig, load_config as _load_config


# ─── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="ShineWiFi-F Monitor",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state for server control
if "server_status" not in st.session_state:
    st.session_state.server_status = None
if "config_updated" not in st.session_state:
    st.session_state.config_updated = False

# ─── CSS Styling ──────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        border-radius: 12px;
        padding: 20px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .metric-card.green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
    .metric-card.orange { background: linear-gradient(135deg, #f2994a 0%, #f2c94c 100%); }
    .metric-card.red { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }
    .metric-card.blue { background: linear-gradient(135deg, #2193b0 0%, #6dd5ed 100%); }
    .metric-value { font-size: 2.5em; font-weight: bold; margin: 0; }
    .metric-label { font-size: 1em; opacity: 0.9; margin: 5px 0 0 0; }
    .stDataFrame { font-size: 0.85em; }
</style>
""", unsafe_allow_html=True)


# ─── Config & State ──────────────────────────────────────────
@st.cache_resource
def get_config() -> AppConfig:
    """Load config once and cache it."""
    return _load_config()


@st.cache_data(ttl=60)
def load_history_csv(filepath: str, max_rows: int = 1000) -> pd.DataFrame:
    """Load historical CSV data into a DataFrame."""
    if not os.path.exists(filepath):
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            filepath,
            header=None,
            names=["timestamp"] + [f"reg_{i}" for i in range(100)],
            dtype=float,
        )
        # Sort by timestamp and take last N rows
        df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
        df = df.sort_values("datetime").tail(max_rows).reset_index(drop=True)
        return df
    except Exception as e:
        st.warning(f"Error loading history: {e}")
        return pd.DataFrame()


def get_register_info(config: AppConfig) -> dict:
    """Get register metadata from config."""
    info = {}
    for name, addr in config.registers.mapping.items():
        entry = config.registers.register_definitions.get(name, {})
        info[addr] = {
            "name": name,
            "unit": entry.get("unit", ""),
            "description": entry.get("description", ""),
            "reg_type": entry.get("type", "uint16"),
            "multiplier": entry.get("multiplier", 1.0),
        }
    return info


# ─── Server Control Functions ──────────────────────────────────

def check_server_status() -> str:
    """Check if the Modbus server service is running."""
    import subprocess
    
    try:
        result = subprocess.run(
            ["systemctl", "is-active", "shinebridge-modbus.service"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip()
    except Exception as e:
        return f"error: {e}"


def start_server():
    """Start the Modbus server service."""
    import subprocess
    
    try:
        # Use sudo with password for automation
        cmd = f"echo 'rainbow' | sudo -S systemctl start shinebridge-modbus.service"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            st.session_state.server_status = "active"
            return True, "Server started successfully"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"Failed to start: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Timeout while starting server"
    except Exception as e:
        return False, f"Error: {e}"


def stop_server():
    """Stop the Modbus server service."""
    import subprocess
    
    try:
        cmd = f"echo 'rainbow' | sudo -S systemctl stop shinebridge-modbus.service"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            st.session_state.server_status = "inactive"
            return True, "Server stopped successfully"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"Failed to stop: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Timeout while stopping server"
    except Exception as e:
        return False, f"Error: {e}"


def restart_server():
    """Restart the Modbus server service."""
    import subprocess
    
    try:
        cmd = f"echo 'rainbow' | sudo -S systemctl restart shinebridge-modbus.service"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            st.session_state.server_status = "active"
            return True, "Server restarted successfully"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip()
            return False, f"Failed to restart: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, "Timeout while restarting server"
    except Exception as e:
        return False, f"Error: {e}"


def update_config(host: str, port: int) -> tuple[bool, str]:
    """Update config.yaml with new host and port settings."""
    import yaml
    
    try:
        config_path = Path(__file__).parent.parent / "config.yaml"
        
        # Read current config
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f) or {}
        
        # Update modbus settings
        if "modbus" not in config_data:
            config_data["modbus"] = {}
        
        config_data["modbus"]["host"] = host
        config_data["modbus"]["port"] = port
        
        # Write back to file
        with open(config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
        
        return True, "Configuration updated successfully"
    except Exception as e:
        return False, f"Failed to update config: {e}"


def get_service_status_icon(status: str) -> str:
    """Get emoji icon for service status."""
    icons = {
        "active": "🟢",
        "inactive": "🔴",
        "failed": "⚠️",
        "error": "❓"
    }
    return icons.get(status, "❓")


# ─── Main App ────────────────────────────────────────────────

st.title("☀️ ShineWiFi-F Monitor")
st.markdown("---")

config = get_config()
register_info = get_register_info(config)

# Sidebar controls
with st.sidebar:
    st.header("⚙️ Controls")
    
    # ─── Server Status & Control ──────────────────────────────
    st.subheader("🖥️ Modbus Server")
    
    # Check and display current status
    if st.session_state.server_status is None or st.session_state.config_updated:
        st.session_state.server_status = check_server_status()
        st.session_state.config_updated = False
    
    status_icon = get_service_status_icon(st.session_state.server_status)
    st.markdown(f"**Status:** {status_icon} `{st.session_state.server_status}`")
    
    # Server control buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("▶️ Start", type="primary", use_container_width=True):
            success, msg = start_server()
            st.session_state.server_status = check_server_status()
            if success:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()
    
    with col2:
        if st.button("⏹️ Stop", type="secondary", use_container_width=True):
            success, msg = stop_server()
            st.session_state.server_status = check_server_status()
            if success:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()
    
    with col3:
        if st.button("🔄 Restart", type="secondary", use_container_width=True):
            success, msg = restart_server()
            st.session_state.server_status = check_server_status()
            if success:
                st.success(msg)
            else:
                st.error(msg)
            st.rerun()
    
    st.divider()
    
    # ─── Server Configuration ──────────────────────────────
    st.subheader("⚙️ Configuration")
    
    new_host = st.text_input(
        "Listen Host",
        value=config.modbus.host,
        help="IP address to bind the Modbus server (e.g., 0.0.0.0 or 192.168.10.165)",
    )
    
    new_port = st.number_input(
        "Listen Port",
        min_value=1,
        max_value=65535,
        value=config.modbus.port,
        help="Port number for the Modbus TCP server (default: 5279)",
    )
    
    if st.button("💾 Apply Configuration", type="primary", use_container_width=True):
        success, msg = update_config(new_host, new_port)
        if success:
            st.session_state.config_updated = True
            config.modbus.host = new_host
            config.modbus.port = new_port
            st.success(msg + " — Please restart the server to apply changes.")
            
            # Auto-restart after config change
            with st.spinner("Restarting server..."):
                _, restart_msg = restart_server()
                st.session_state.server_status = check_server_status()
        else:
            st.error(msg)
    
    st.divider()
    
    # Connection status (existing)
    modbus_host = config.modbus.host
    modbus_port = config.modbus.port
    mqtt_broker = config.mqtt.broker
    mqtt_port = config.mqtt.port
    
    st.info(f"**Modbus:** `{modbus_host}:{modbus_port}`")
    st.info(f"**MQTT:** `{mqtt_broker}:{mqtt_port}`")
    
    # Refresh interval
    refresh_interval = st.slider(
        "Refresh Interval (seconds)",
        min_value=1,
        max_value=30,
        value=config.registers.update_interval,
        help="How often to poll the Modbus server",
    )
    
    # History settings
    history_path = str(Path(__file__).parent.parent / "data" / "history.csv")
    st.markdown(f"**History file:** `{history_path}`")
    
    st.divider()
    
    # Manual register read section
    st.header("🔍 Read Register")
    manual_addr = st.number_input(
        "Register Address",
        min_value=1,
        max_value=99,
        value=1,
        step=1,
    )
    if st.button("Read Value"):
        try:
            from pymodbus.client import ModbusTcpClient
            client = ModbusTcpClient(host=modbus_host, port=modbus_port)
            result = client.read_input_registers(address=manual_addr - 1, count=1)
            client.close()
            
            if not result.isError():
                raw_val = result.registers[0]
                entry = register_info.get(manual_addr, {})
                name = entry.get("name", f"reg_{manual_addr}")
                multiplier = entry.get("multiplier", 1.0)
                decoded = raw_val * multiplier
                
                st.success(f"`{name}` (addr {manual_addr}): **{raw_val}** (decoded: **{decoded:.2f}**)")
            else:
                st.error(f"Error reading register {manual_addr}")
        except Exception as e:
            st.error(f"Connection error: {e}")
    
    # Clear history button
    if os.path.exists(history_path) and st.button("🗑️ Clear History"):
        Path(history_path).unlink()
        st.success("History cleared")


# ─── Real-time Register Values ──────────────────────────────
st.header("📊 Live Register Values")

try:
    from pymodbus.client import ModbusTcpClient
    
    client = ModbusTcpClient(host=modbus_host, port=modbus_port)
    
    # Read all input registers (1-14 for ShineWiFi-F)
    result = client.read_input_registers(address=0, count=15)  # address is 0-indexed in pymodbus
    
    if not result.isError():
        raw_values = result.registers
        
        # Create a grid of metric cards
        cols = st.columns(4)
        
        for i, col in enumerate(cols):
            reg_addr = i + 1
            if reg_addr > len(raw_values):
                break
                
            entry = register_info.get(reg_addr, {})
            name = entry.get("name", f"reg_{reg_addr}")
            unit = entry.get("unit", "")
            
            # Convert raw uint16 to decoded value using multiplier from config
            multiplier = entry.get("multiplier", 1.0)
            decoded_value = raw_values[reg_addr - 1] * multiplier
            
            # Color coding based on register type
            color_class = ""
            if "voltage" in name.lower():
                color_class = "blue"
            elif "current" in name.lower() or "power" in name.lower():
                color_class = "green"
            elif "soc" in name.lower():
                color_class = "orange"
            elif "temperature" in name.lower():
                color_class = "red"
            
            with col:
                st.markdown(f"""
<div class="metric-card {color_class}">
    <p class="metric-value">{decoded_value:.2f}</p>
    <p class="metric-label">{name} [{unit}]</p>
</div>
""", unsafe_allow_html=True)
        
        client.close()
    else:
        st.error("Failed to read registers from Modbus server")

except Exception as e:
    st.error(f"Error connecting to Modbus server: {e}")
    st.info("Make sure the Modbus server is running. Check sidebar for status.")


# ─── Historical Data Charts ──────────────────────────────────
st.header("📈 Historical Trends")

history_path = str(Path(__file__).parent.parent / "data" / "history.csv")
df = load_history_csv(history_path)

if not df.empty:
    # Select which registers to display
    available_regs = [col for col in df.columns if col.startswith("reg_")]
    
    selected_regs = st.multiselect(
        "Select Registers to Display",
        options=available_regs,
        default=[col for col in available_regs[:5]],  # Default first 5
    )
    
    if selected_regs:
        fig = st.plotly_chart(
            pd.DataFrame(df["datetime"], columns=["datetime"]).assign(**{r: df[r] for r in selected_regs}),
            use_container_width=True,
        )
else:
    st.info("📭 No historical data yet. Data will appear once the Modbus server starts logging.")


# ─── Raw Register Table ──────────────────────────────────────
st.header("📋 All Registers")

try:
    from pymodbus.client import ModbusTcpClient
    
    client = ModbusTcpClient(host=modbus_host, port=modbus_port)
    result = client.read_input_registers(address=0, count=100)
    
    if not result.isError():
        data = []
        for addr in range(1, 101):
            raw_val = result.registers[addr - 1] if addr <= len(result.registers) else None
            entry = register_info.get(addr, {})
            name = entry.get("name", "unknown")
            unit = entry.get("unit", "")
            
            # Decode value
            multiplier = entry.get("multiplier", 1.0)
            decoded = raw_val * multiplier if raw_val is not None else None
            
            data.append({
                "Address": addr,
                "Name": name,
                "Raw (uint16)": raw_val,
                f"Decoded [{unit}]": decoded,
                "Description": entry.get("description", ""),
            })
        
        st.dataframe(
            pd.DataFrame(data),
            use_container_width=True,
            hide_index=True,
        )
        
        client.close()
    else:
        st.warning("Could not read all registers. Showing config mapping only.")
        
        # Fallback to showing config mapping
        fallback_data = []
        for name, addr in config.registers.mapping.items():
            entry = config.registers.register_definitions.get(name, {})
            fallback_data.append({
                "Address": addr,
                "Name": name,
                "Type": entry.get("type", "uint16"),
                "Unit": entry.get("unit", ""),
                "Multiplier": entry.get("multiplier", 1.0),
                "Description": entry.get("description", ""),
            })
        
        st.dataframe(
            pd.DataFrame(fallback_data),
            use_container_width=True,
            hide_index=True,
        )

except Exception as e:
    st.warning(f"Could not connect to Modbus server for table data. Showing config mapping only.")
    
    # Fallback to showing config mapping
    fallback_data = []
    for name, addr in config.registers.mapping.items():
        entry = config.registers.register_definitions.get(name, {})
        fallback_data.append({
            "Address": addr,
            "Name": name,
            "Type": entry.get("type", "uint16"),
            "Unit": entry.get("unit", ""),
            "Multiplier": entry.get("multiplier", 1.0),
            "Description": entry.get("description", ""),
        })
    
    st.dataframe(
        pd.DataFrame(fallback_data),
        use_container_width=True,
        hide_index=True,
    )


# ─── Footer ──────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"ShineWiFi-F Monitor v1.0 | "
    f"Modbus Server: `{modbus_host}:{modbus_port}` | "
    f"MQTT Broker: `{mqtt_broker}:{mqtt_port}` | "
    f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
