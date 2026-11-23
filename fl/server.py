"""Federated aggregator (FedAvg) over MQTT.

  python -m fl.server --rounds 15

Protocol (see docs/CONTRACT.md):
  server -> clients   microgrid/fl/global         QoS1 retained   {run, round, weights, final}
  clients -> server   microgrid/fl/<home>/update  QoS1            {run, round, home, n, weights, mae_global}
  server -> dashboard microgrid/fl/metrics        QoS0            {run, round, mae_avg, mae, clients}

Only model weights travel; the raw consumption data never leaves each home.
"""
import argparse
import json
import threading
import time

import numpy as np
import paho.mqtt.client as mqtt

from simulator.config import BASE_TOPIC, HOMES
from . import model

GLOBAL_TOPIC = f"{BASE_TOPIC}/fl/global"
UPDATE_TOPIC = f"{BASE_TOPIC}/fl/+/update"
METRICS_TOPIC = f"{BASE_TOPIC}/fl/metrics"


class Aggregator:
    def __init__(self, homes, rounds, timeout):
        self.homes, self.rounds, self.timeout = list(homes), rounds, timeout
        self.run_id = int(time.time())          # distinguishes this run from a previous one
        self.updates = {}                       # home -> (weights, n, mae)  (dict: duplicates overwrite)
        self.round = 0
        self.lock = threading.Lock()
        self.complete = threading.Event()
        self.subscribed = threading.Event()

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fl-server")
        self.client.on_connect = lambda c, u, f, rc, p=None: c.subscribe(UPDATE_TOPIC, qos=1)
        self.client.on_subscribe = lambda c, u, mid, rcs, p=None: self.subscribed.set()
        self.client.on_message = self.on_update

    def on_update(self, client, userdata, msg):
        try:
            d = json.loads(msg.payload)
            if d["run"] != self.run_id or d["home"] not in self.homes:
                return
            with self.lock:
                if d["round"] != self.round:     # late or duplicated message of another round
                    return
                self.updates[d["home"]] = (np.array(d["weights"]), d["n"], d["mae_global"])
                if len(self.updates) == len(self.homes):
                    self.complete.set()
        except (ValueError, KeyError, TypeError):
            return                              # invalid messages are ignored

    def publish_global(self, weights, final=False):
        self.client.publish(GLOBAL_TOPIC, json.dumps({
            "run": self.run_id, "round": self.round, "total_rounds": self.rounds,
            "weights": [float(x) for x in weights], "final": final,
        }), qos=1, retain=True).wait_for_publish()

    def run(self, host, port):
        self.client.connect(host, port, keepalive=15)
        self.client.loop_start()
        self.subscribed.wait(10)
        w = model.init_weights()
        print(f"[server] run={self.run_id} homes={self.homes} rounds={self.rounds}")
        for r in range(1, self.rounds + 1):
            with self.lock:
                self.round, self.updates = r, {}
                self.complete.clear()
            self.publish_global(w)                          # "train round r starting from w"
            self.complete.wait(self.timeout)                # wait for all homes (or timeout)
            with self.lock:
                got = dict(self.updates)
            if not got:
                print(f"[server] round {r}: no updates, repeating the same model")
                continue
            w = model.fedavg([(wi, n) for wi, n, _ in got.values()])
            mae = {h: round(m, 4) for h, (_, _, m) in got.items()}
            avg = round(float(np.mean(list(mae.values()))), 4)
            print(f"[server] round {r:2d}: {len(got)}/{len(self.homes)} homes, "
                  f"MAE of the model received (avg) = {avg}  {mae}")
            self.client.publish(METRICS_TOPIC, json.dumps(
                {"run": self.run_id, "round": r, "mae_avg": avg, "mae": mae, "clients": len(got)}), qos=0)
        self.round += 1
        self.publish_global(w, final=True)                  # final model: clients evaluate and exit
        time.sleep(1)
        self.client.loop_stop()
        self.client.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--homes", nargs="+", default=list(HOMES))
    ap.add_argument("--rounds", type=int, default=15)
    ap.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for the homes in each round")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    a = ap.parse_args()
    Aggregator(a.homes, a.rounds, a.timeout).run(a.host, a.port)


if __name__ == "__main__":
    main()
