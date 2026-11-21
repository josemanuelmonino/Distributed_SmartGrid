"""Simulator of one home: publishes MQTT telemetry and receives commands."""
import json
import random
import time
from datetime import datetime, timedelta, timezone

from . import models
from .config import BASE_TOPIC, HOMES, SECONDARY_LOADS


class HomeSimulator:
    def __init__(self, home_id, speed=600.0, tick_s=1.0, start_hour=6.0, publish=None):
        cfg = HOMES[home_id] # the dictionary of the home 
        self.id, self.cfg = home_id, cfg
        self.rng = random.Random(cfg["seed"])
        self.speed, self.tick_s = speed, tick_s #speed the number of seconds that happens every real second and tick_s the real ones
        self.dt_min = speed * tick_s / 60.0          # simulated minutes per tick
        self.clock = datetime(2026, 7, 1, int(start_hour), int((start_hour % 1) * 60)) # 1st of july, it can be changed
        self.cloud = 0.0    # if there are any clouds (range 0,1)
        self.shed = set()                            # loads switched off by command
        self.battery = models.Battery(cfg["battery_kwh"], cfg["battery_max_w"], cfg["battery_soc0"])
        self.fridge, self.washer = models.Fridge(self.rng), models.Washer(self.rng)
        self.ac, self.ev = models.AirCon(self.rng), (models.EV(self.rng) if cfg["ev"] else None)
        self.publish = publish or (lambda topic, payload, qos=0, retain=False: print(topic, payload))

    # ------------------------------------------------------------ commands
    def handle_command(self, topic, payload):
        """"Apply a command received from Node-RED.

        microgrid/<h>/cmd/battery       -> {"mode": "auto|charge_grid|discharge|idle"}
        microgrid/<h>/cmd/load/<name>   -> {"state": "on|off"}

        - battery: sets the operating mode of the home battery.
        - load: switches a secondary load (washer, ac, ev) on or off.
        Invalid messages are ignored.
        """
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            return
        parts = topic.split("/")
        if len(parts) >= 4 and parts[3] == "battery" and data.get("mode") in ("auto", "charge_grid", "discharge", "idle"):
            self.battery.mode = data["mode"]
        elif len(parts) >= 5 and parts[3] == "load" and parts[4] in SECONDARY_LOADS:
            (self.shed.discard if data.get("state") == "on" else self.shed.add)(parts[4])

    # ------------------------------------------------------------ simulation
    def step(self):
        # every instant of the simulation
        h = self.clock.hour + self.clock.minute / 60 + self.clock.second / 3600
        if self.rng.random() < 0.02:
            self.cloud = min(1.0, max(0.0, self.cloud + self.rng.uniform(-0.3, 0.3)))
        loads = {}
        # first the furniture (stores everything in loads)
        for name in self.cfg["loads"]:
            if name == "fridge":
                loads[name] = self.fridge.step(self.dt_min)
            elif name == "washer":
                loads[name] = self.washer.step(self.dt_min, h, "washer" not in self.shed)
            elif name == "ac":
                loads[name] = self.ac.step(h, "ac" not in self.shed)
            elif name == "lighting":
                loads[name] = models.lighting(h, self.rng)
            elif name == "standby":
                loads[name] = models.standby(self.rng)
        if self.ev:
            loads["ev"] = self.ev.step(self.dt_min, h, "ev" not in self.shed)

        # solar production 
        solar = models.solar_power(h, self.cfg["solar_peak_w"], self.rng, self.cloud)
        consumption = sum(loads.values())
        batt = self.battery.step(self.dt_min, consumption - solar) # the difference in the battery
        grid = consumption - solar + batt            # + imports from the grid, - exports

        ts = int(time.time() * 1000)
        base = {"home": self.id, "ts": ts, "sim_time": self.clock.isoformat(timespec="seconds"), "sim_hour": round(h, 3)}
        dt_h = self.dt_min / 60
        for name, p in loads.items():
            self._pub(name, base, power_w=round(p, 1), energy_wh=round(p * dt_h, 2), shed=name in self.shed)
        if self.cfg["solar_peak_w"] > 0:
            self._pub("solar", base, power_w=round(solar, 1), energy_wh=round(solar * dt_h, 2))
        if self.battery.present:
            self._pub("battery", base, power_w=round(batt, 1), soc_pct=round(self.battery.soc, 2), mode=self.battery.mode)
        if self.ev:
            self._pub("ev_state", base, soc_pct=round(self.ev.soc, 1), plugged=self.ev.plugged)
        self._pub("grid", base, power_w=round(grid, 1), energy_wh=round(grid * dt_h, 2))
        self.publish(f"{BASE_TOPIC}/{self.id}/summary", json.dumps({
            **base,
            "generation_w": round(solar, 1), "consumption_w": round(consumption, 1),
            "battery_w": round(batt, 1), "battery_soc_pct": round(self.battery.soc, 2) if self.battery.present else None,
            "battery_mode": self.battery.mode, "grid_w": round(grid, 1),
            "shed_loads": sorted(self.shed),
        }), 0, False)
        self.clock += timedelta(minutes=self.dt_min)

    def _pub(self, device, base, **fields):
        self.publish(f"{BASE_TOPIC}/{self.id}/{device}/telemetry", json.dumps({**base, "device": device, **fields}), 0, False)
    # the message is BASE(common for everyone) + DEVICE(specific)
    # {"home": "h1", "ts": 1795273289705, "sim_time": "2026-07-01T12:00:00",
    # "sim_hour": 12.0, "device": "solar", "power_w": 3213.2, "energy_wh": 535.5}