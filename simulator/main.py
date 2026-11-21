"""Starts the home simulators.

Usage:
  python -m simulator.main                      # all homes, broker at localhost:1883
  python -m simulator.main --homes h1 h4 --speed 1200
  python -m simulator.main --dry-run --ticks 5  # prints to the screen, no broker needed
"""
import argparse
import json
import threading
import time

from .config import BASE_TOPIC, HOMES
from .home_sim import HomeSimulator


def run_home(home_id, args):
    if args.dry_run:
        sim = HomeSimulator(home_id, args.speed, args.tick, args.start_hour)
        for _ in range(args.ticks or 10**9):
            sim.step()
            time.sleep(args.tick if not args.ticks else 0)
        return

    import paho.mqtt.client as mqtt
    status_topic = f"{BASE_TOPIC}/{home_id}/status"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"sim-{home_id}")
    # Last Will: if the simulator dies, the broker publishes "offline" (retained, QoS 1)
    client.will_set(status_topic, json.dumps({"home": home_id, "status": "offline"}), qos=1, retain=True)
    sim = HomeSimulator(home_id, args.speed, args.tick, args.start_hour,
                        publish=lambda t, p, qos=0, retain=False: client.publish(t, p, qos=qos, retain=retain))

    def on_connect(c, userdata, flags, rc, props=None):
        c.subscribe(f"{BASE_TOPIC}/{home_id}/cmd/#", qos=1)
        c.publish(status_topic, json.dumps({"home": home_id, "status": "online"}), qos=1, retain=True)

    client.on_connect = on_connect
    client.on_message = lambda c, u, m: sim.handle_command(m.topic, m.payload.decode())
    client.connect(args.host, args.port, keepalive=15)
    client.loop_start()
    try:
        while True:
            sim.step()
            time.sleep(args.tick)
    finally:
        client.publish(status_topic, json.dumps({"home": home_id, "status": "offline"}), qos=1, retain=True).wait_for_publish()
        client.loop_stop()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--homes", nargs="+", default=list(HOMES))
    ap.add_argument("--host", default="localhost")
    ap.add_argument("--port", type=int, default=1883)
    ap.add_argument("--speed", type=float, default=600.0, help="simulated seconds per real second (600 = 10 simulated min per second)")
    ap.add_argument("--tick", type=float, default=1.0, help="real seconds between publications")
    ap.add_argument("--start-hour", type=float, default=6.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--ticks", type=int, default=0, help="dry-run only: number of steps")
    args = ap.parse_args()
    threads = [threading.Thread(target=run_home, args=(h, args), daemon=True) for h in args.homes]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
