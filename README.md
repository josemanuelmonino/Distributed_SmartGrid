# Smart Microgrid

Simulated Home Energy Management System built with MQTT, Node-RED and Federated Learning.
Distributed Systems course project, 2026-2027.

## Quick start

```bash
docker compose up -d                # Mosquitto (1883) and Node-RED (1880)
pip install -r requirements.txt
python -m simulator.main            # 4 homes, 10 simulated minutes per second
python -m simulator.main --dry-run --ticks 5 --homes h1   # no broker needed
```

Topic and message contract: [docs/CONTRACT.md](docs/CONTRACT.md).

## Federated learning

```bash
python -m fl.offline_demo                 # FedAvg in one process, no broker (to understand it)
python -m fl.server --rounds 15           # aggregator (needs the broker)
python -m fl.client h1                    # one terminal per home: h1, h2, h3, h4
```
