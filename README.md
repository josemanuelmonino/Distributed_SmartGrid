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

## Node-RED & Dashboard

Once the containers are running, Node-RED is available at [http://localhost:1880](http://localhost:1880), and the live Dashboard is accessible after deploying the flows at [http://localhost:1880/dashboard](http://localhost:1880/dashboard).

> [!IMPORTANT]
> The Node-RED flow requires `@flowfuse/node-red-dashboard`. Before importing or deploying the flows, open **Menu (`☰`) → Manage palette → Install**, search for `@flowfuse/node-red-dashboard`, and install it; otherwise, the dashboard nodes will fail to deploy.
