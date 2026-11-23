"""FedAvg in a single process (no MQTT): used to understand and validate the algorithm.

  python -m fl.offline_demo
"""
import numpy as np

from simulator.config import HOMES
from . import model
from .dataset import load_home

ROUNDS, EPOCHS = 15, 3


def main():
    data = {h: load_home(h) for h in HOMES}
    print("samples per home:", {h: len(d[0][0]) for h, d in data.items()})

    # 1) each home trains alone (same total effort: ROUNDS * EPOCHS epochs)
    local = {h: model.local_train(model.init_weights(), *data[h][0], epochs=ROUNDS * EPOCHS) for h in HOMES}

    # 2) federated: only weights travel
    g = model.init_weights()
    for r in range(1, ROUNDS + 1):
        updates = [(model.local_train(g, *data[h][0], epochs=EPOCHS, seed=r), len(data[h][0][0])) for h in HOMES]
        g = model.fedavg(updates)
        avg = np.mean([model.mae(g, *data[h][1]) for h in HOMES])
        print(f"round {r:2d}  global MAE on the test sets: {avg:.4f} kW")

    base = {h: model.mae(model.init_weights(), *data[h][1]) for h in HOMES}
    print(f"\n{'home':5s} {'no model':>9s} {'local only':>11s} {'federated':>10s}   (MAE in kW, lower is better)")
    for h in HOMES:
        print(f"{h:5s} {base[h]:9.4f} {model.mae(local[h], *data[h][1]):11.4f} {model.mae(g, *data[h][1]):10.4f}")


if __name__ == "__main__":
    main()
