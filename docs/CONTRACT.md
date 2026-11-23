# MQTT contract (v1)

Single source of truth shared by the simulators and Node-RED.
All payloads are UTF-8 JSON. Power in W, energy in Wh, SOC (State of Charge of the battery) in %.
Grid convention: `grid_w > 0` imports from the grid, `< 0` exports. Battery: `+` charging, `-` discharging.

## Telemetry (simulator -> broker)

| Topic | QoS | Retain | Content |
|---|---|---|---|
| `microgrid/{home}/{device}/telemetry` | 0 | no | one device reading (`fridge`, `washer`, `ac`, `lighting`, `standby`, `ev`, `solar`, `battery`, `ev_state`, `grid`) |
| `microgrid/{home}/summary` | 0 | no | home balance: `generation_w`, `consumption_w`, `battery_w`, `battery_soc_pct`, `battery_mode`, `grid_w`, `shed_loads`, `sim_hour` |
| `microgrid/{home}/status` | 1 | **yes** | `{"status":"online"|"offline"}`. `offline` is the **Last Will** |

Common fields: `home`, `ts` (real epoch ms), `sim_time` (ISO, simulated clock), `sim_hour` (0-24).

QoS rationale: telemetry is periodic and a lost sample is replaced by the next one
(at-most-once). Status and commands are events that must not be lost (at-least-once); commands
are idempotent, so duplicates are harmless.

## Commands (Node-RED -> simulator)

| Topic | QoS | Payload |
|---|---|---|
| `microgrid/{home}/cmd/battery` | 1 | `{"mode":"auto"|"charge_grid"|"discharge"|"idle"}` |
| `microgrid/{home}/cmd/load/{washer|ac|ev}` | 1 | `{"state":"on"|"off"}` (off = shed a secondary load) |

## Alarms and decisions (Node-RED -> dashboard)

| Topic | QoS | Retain |
|---|---|---|
| `microgrid/alarms/{home}` | 1 | no |
| `microgrid/decisions/{home}` | 0 | no |


## Federated learning (fl/ scripts <-> fl/ scripts)

Only model weights travel over MQTT; the raw consumption data never leaves each home.
Task: forecast the consumption of the next 10 simulated minutes (linear regression, FedAvg).

| Topic | QoS | Retain | Payload |
|---|---|---|---|
| `microgrid/fl/global` | 1 | **yes** | `{run, round, total_rounds, weights, final}`: model to train in `round` (server -> clients) |
| `microgrid/fl/{home}/update` | 1 | no | `{run, round, home, n, weights, mae_global}`: locally trained weights (client -> server) |
| `microgrid/fl/metrics` | 0 | no | `{run, round, mae_avg, mae, clients}`: progress for the dashboard |

Delivery semantics: QoS 1 (at-least-once) because losing an update would stall the round. Duplicates are
harmless: the server keys updates by `home` and ignores other `(run, round)`; the clients skip a
`(run, round)` they already trained. `global` is retained so a client that starts late gets the current
round immediately. `run` (start timestamp of the server) separates different executions.
The `fl` level never matches `microgrid/+/summary` nor `microgrid/+/status`, so it does not collide with the homes.
