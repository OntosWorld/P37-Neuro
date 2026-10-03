# Observability

P37 treats observability as part of the deployment contract rather than as optional debugging.

## Runtime metrics

The observability API records:
- active robot ID and model artifact ID;
- control-loop frequency;
- inference p50/p95/p99 latency;
- p95 observation age;
- rejected-command count;
- watchdog events;
- interventions;
- runtime restarts;
- optional GPU-memory use.

`p37_neuro.observability.RuntimeMetrics` maintains a bounded sample window and emits snapshots.

Snapshots can be exported as:
- JSONL for telemetry/log agents;
- Prometheus exposition text.

## Real-time boundary

Metrics export must run outside the actuator-critical real-time path. Telemetry must never delay a stop request, command validation or controller watchdog.

## Enterprise operating model

At deployment, operators should attach at minimum:
- artifact/version labels;
- robot/site/fleet identity;
- latency and command-rejection alerts;
- watchdog/intervention alerts;
- release and rollback events.

Prometheus/OpenTelemetry collectors may consume P37 outputs, but the core remains dependency-light.

## Evidence

Operational telemetry is not automatically capability evidence. A qualification report must explicitly identify which metrics and time window are part of its evidence.
