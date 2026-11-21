"""Configuration of the simulated homes (deterministic, seeded)."""

BASE_TOPIC = "microgrid"

# Each home: peak solar power (W), battery (kWh, max W), electric vehicle flag and list of loads.
HOMES = {
    "h1": {
        "seed": 1,
        "solar_peak_w": 4000,
        "battery_kwh": 10.0, "battery_max_w": 3500, "battery_soc0": 50.0,
        "ev": True,
        "loads": ["fridge", "washer", "ac", "lighting", "standby"],
    },
    "h2": {
        "seed": 2,
        "solar_peak_w": 0,          # no solar panels
        "battery_kwh": 0.0, "battery_max_w": 0, "battery_soc0": 0.0,
        "ev": False,
        "loads": ["fridge", "washer", "lighting", "standby"],
    },
    "h3": {
        "seed": 3,
        "solar_peak_w": 3000,
        "battery_kwh": 6.0, "battery_max_w": 2500, "battery_soc0": 40.0,
        "ev": False,
        "loads": ["fridge", "washer", "ac", "lighting", "standby"],
    },
    "h4": {
        "seed": 4,
        "solar_peak_w": 5500,
        "battery_kwh": 13.0, "battery_max_w": 5000, "battery_soc0": 60.0,
        "ev": True,
        "loads": ["fridge", "washer", "ac", "lighting", "standby"],
    },
}

# Secondary loads: Node-RED can switch them off with a command.
SECONDARY_LOADS = {"washer", "ac", "ev"}
