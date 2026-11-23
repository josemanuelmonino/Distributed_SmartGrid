"""Federated client of ONE home.

  python -m fl.client h1

It subscribes to the global model, trains it on the local data of the home and publishes
only the new weights. When the server announces the final model it prints how much the
federated model helps compared with a model trained alone, and exits.
"""
import argparse
import json
import threading

import numpy as np
import paho.mqtt.client as mqtt

from simulator.config import BASE_TOPIC, HOMES
from . import model
from .dataset import load_home

GLOBAL_TOPIC = f"{BASE_TOPIC}/fl/global"


class FLClient:
    def __init__(self, home_id, epochs):
        self.id, self.epochs = home_id, epochs
        (self.Xtr, self.ytr), (self.Xte, self.yte) = load_home(home_id)   # private data
        self.seen = set()                       # (run, round) already trained: a QoS1 duplicate is ignored
        self.done = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"fl-{home_id}")
        self.client.on_connect = lambda c, u, f, rc, p=None: c.subscribe(GLOBAL_TOPIC, qos=1)
        self.client.on_message = self.on_global

    def on_global(self, client, userdata, msg):
        try:
            d = json.loads(msg.payload)
            w, key = np.array(d["weights"]), (d["run"], d["round"])
        except (ValueError, KeyError, TypeError):
            return
        if key in self.seen:
            return
        self.seen.add(key)
        mae_global = model.mae(w, self.Xte, self.yte)      # how good is the model I just received?
        if d["final"]:
            self.finish(w, mae_global, d["total_rounds"])
            return
        new_w = model.local_train(w, self.Xtr, self.ytr, epochs=self.epochs, seed=d["round"])
        self.client.publish(f"{BASE_TOPIC}/fl/{self.id}/update", json.dumps({
            "run": d["run"], "round": d["round"], "home": self.id, "n": len(self.Xtr),
            "weights": [float(x) for x in new_w], "mae_global": mae_global,
        }), qos=1)
        print(f"[{self.id}] round {d['round']:2d}: MAE of the received model = {mae_global:.4f} kW -> trained and sent")

    def finish(self, w_fed, mae_fed, rounds):
        alone = model.local_train(model.init_weights(), self.Xtr, self.ytr, epochs=rounds * self.epochs)
        print(f"[{self.id}] FINAL  federated MAE = {mae_fed:.4f} kW | trained alone = "
              f"{model.mae(alone, self.Xte, self.yte):.4f} kW")
        self.done.set()

    def run(self, host, port):
        self.client.connect(host, port, keepalive=15)
        self.client.loop_start()
        self.done.wait()
        self.client.loop_stop()
        self.client.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("home", choices=list(HOMES))
    ap.add_argument("--epochs", type=int, default=3, help="local epochs per round")
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    a = ap.parse_args()
    FLClient(a.home, a.epochs).run(a.host, a.port)


if __name__ == "__main__":
    main()
