"""Simple physical models of the devices in a home.

All functions use the simulated hour (float 0-24) and return power in W.
"""
import math
import random


def solar_power(sim_hour: float, peak_w: float, rng: random.Random, cloud: float) -> float:
    """Bell-shaped curve between 07:00 and 19:00, attenuated by cloud cover (0-1)."""
    if peak_w <= 0 or sim_hour < 7 or sim_hour > 19:
        return 0.0
    x = (sim_hour - 7) / 12 * math.pi
    p = peak_w * math.sin(x) ** 1.5 * (1 - 0.7 * cloud)
    return max(0.0, p * (1 + rng.uniform(-0.03, 0.03)))


class Fridge:
    """Compressor cycle: 150 W for roughly one third of the time."""
    def __init__(self, rng):
        self.rng, self.on, self.left = rng, False, rng.uniform(5, 20)

    def step(self, dt_min):
        self.left -= dt_min
        if self.left <= 0:
            self.on = not self.on
            self.left = self.rng.uniform(10, 20) if self.on else self.rng.uniform(20, 40)
        return 150.0 if self.on else 3.0


class Washer:
    """90-minute cycles (2000 W) started at random between 09:00 and 21:00."""
    def __init__(self, rng):
        self.rng, self.left = rng, 0.0

    def step(self, dt_min, sim_hour, allowed=True):
        if self.left > 0:
            if not allowed:
                return 0.0           # paused by a command
            self.left -= dt_min
            return 2000.0
        if 9 <= sim_hour <= 21 and self.rng.random() < 0.002 * dt_min:
            self.left = 90.0
        return 0.0


class AirCon:
    """Air conditioner driven by the outdoor temperature (peak at 16:00)."""
    def __init__(self, rng):
        self.rng = rng

    def step(self, sim_hour, allowed=True):
        temp = 24 + 9 * math.sin((sim_hour - 10) / 24 * 2 * math.pi)
        if not allowed or temp < 28:
            return 0.0
        return min(1800.0, 400 + (temp - 28) * 450) * (1 + self.rng.uniform(-0.05, 0.05))


def lighting(sim_hour: float, rng: random.Random) -> float:
    if 19 <= sim_hour <= 24 or sim_hour < 1:
        return 250.0 * (1 + rng.uniform(-0.1, 0.1))
    if 6.5 <= sim_hour <= 8:
        return 120.0
    return 0.0


def standby(rng: random.Random) -> float:
    return 120.0 * (1 + rng.uniform(-0.1, 0.1))


class EV:
    """Electric vehicle: plugged in between 19:00 and 22:00, charges at 7 kW up to 100% (40 kWh)."""
    CAP_WH = 40000.0 # 40 kWh

    def __init__(self, rng):
        self.rng = rng
        self.soc = rng.uniform(25, 55)
        self.plugged = False
        self.plug_hour = rng.uniform(19, 22)

    def step(self, dt_min, sim_hour, allowed=True):
        self.plugged = self.plug_hour <= sim_hour or sim_hour < 7
        if sim_hour < 0.05:               # new day: the commute uses up battery
            self.soc = max(20.0, self.soc - 20)
        if not self.plugged or self.soc >= 100 or not allowed:
            return 0.0
        self.soc = min(100.0, self.soc + 7000 * dt_min / 60 / self.CAP_WH * 100)
        return 7000.0


class Battery:
    """Home battery with 95% charge/discharge efficiency.

    Modes (set by Node-RED over MQTT): auto | charge_grid | discharge | idle
    - auto: self-consumption (charges from solar surplus, discharges to cover a deficit)
    """
    EFF = 0.95

    def __init__(self, kwh, max_w, soc0):
        self.cap_wh = kwh * 1000
        self.max_w = max_w
        self.soc = soc0
        self.mode = "auto"
        self.present = kwh > 0

    def step(self, dt_min, net_load_w):
        """net_load_w = consumption - generation. Returns battery power (+charge, -discharge)."""
        if not self.present:
            return 0.0
        if self.mode == "idle":
            want = 0.0
        elif self.mode == "charge_grid":
            want = self.max_w
        elif self.mode == "discharge":
            want = -self.max_w
        else:  # auto
            want = max(-self.max_w, min(self.max_w, -net_load_w))
        dt_h = dt_min / 60
        if want > 0:
            room = (100 - self.soc) / 100 * self.cap_wh
            want = min(want, room / (dt_h * self.EFF))
            self.soc += want * dt_h * self.EFF / self.cap_wh * 100
        elif want < 0:
            avail = self.soc / 100 * self.cap_wh
            want = -min(-want, avail * self.EFF / dt_h)
            self.soc += want * dt_h / self.EFF / self.cap_wh * 100
        self.soc = max(0.0, min(100.0, self.soc))
        return want + 0.0
