"""Local dataset of each home.

Every home owns its own consumption history; it never leaves the home.
Here the history is produced by running the home simulator offline (no broker),
exactly the same model that publishes the MQTT telemetry.

Task: forecast the consumption of the NEXT 10 simulated minutes (kW) from
  - the time of day (sin/cos harmonics: the daily load profile)
  - the current consumption and the current solar generation (kW)
"""
import json
import math

import numpy as np

from simulator.home_sim import HomeSimulator

N_FEATURES = 9      # bias + 6 harmonics + consumption + generation


def collect_summaries(home_id, days=10, start_hour=0.0, speed=600.0, tick_s=1.0):
    """Run the simulator offline and return the list of `summary` messages (dicts)."""
    out = []

    def publish(topic, payload, qos=0, retain=False):
        if topic.endswith("/summary"):
            out.append(json.loads(payload))

    sim = HomeSimulator(home_id, speed, tick_s, start_hour, publish=publish)
    steps_per_day = int(24 * 60 / sim.dt_min)
    for _ in range(days * steps_per_day):
        sim.step()
    return out


def features(sim_hour, consumption_kw, generation_kw):
    w = 2 * math.pi * sim_hour / 24
    return [1.0, math.sin(w), math.cos(w), math.sin(2 * w), math.cos(2 * w),
            math.sin(3 * w), math.cos(3 * w), consumption_kw, generation_kw]


def make_xy(summaries):
    """X[i] = features at step i, y[i] = consumption (kW) at step i+1."""
    X, y = [], []
    for cur, nxt in zip(summaries, summaries[1:]):
        X.append(features(cur["sim_hour"], cur["consumption_w"] / 1000, cur["generation_w"] / 1000))
        y.append(nxt["consumption_w"] / 1000)
    return np.array(X), np.array(y)


def load_home(home_id, days=10, test_days=2):
    """Train/test split by time (the last days are the test set)."""
    X, y = make_xy(collect_summaries(home_id, days))
    n_test = test_days * 144
    return (X[:-n_test], y[:-n_test]), (X[-n_test:], y[-n_test:])
