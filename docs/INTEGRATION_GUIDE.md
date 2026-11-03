# Integration guide

## Detector return contract

`NetworkDetector.process_flow_stats()` and `process_telemetry()` return a
result dictionary. The result contains an `alerts` list. The pipeline preserves
the full result and calls `on_alert` only for dictionaries inside that list.
A baseline sample and ordinary telemetry with no alert must not trigger the
callback.

## Flow statistics

Ryu sends one JSON datagram per flow sample to `127.0.0.1:9998`. The receiver
is `integration/stats_receiver.py`. It validates required fields and calls
`MonitoringPipeline.handle_flow_stats()`.

Required fields: `switch`, `flow_id`, `byte_count`, `packet_count`, `timestamp`.
The controller also exports `ipv4_src` and `ipv4_dst` when its flow match
contains IPv4 addresses. Byte and packet counts are cumulative counters.

## Host telemetry

Member 2's UDP telemetry server receives messages on UDP port 9999. In the
Mininet run configuration, the server runs inside `h4` (10.0.0.4) and agents
on `h1`–`h3` send to that address. The optional `--detector` mode routes
telemetry through `MonitoringPipeline` and prints only actual alert entries.

## Dynamic SDN control

The controller control listener uses UDP port 10000. The statistics receiver
can optionally send `block_ip` / `unblock_ip` commands when started with
`--auto-block`. It only attempts a block for a HIGH Mbps alert with an
IPv4 source address. Verify installed rules and traffic effects in Mininet.

## Port ownership

| Component | UDP port |
|---|---:|
| Flow-statistics receiver | 9998 |
| Telemetry server (inside h4) | 9999 |
| Controller control listener (Ubuntu VM loopback) | 10000 |

## Verification status

Local Python unit tests cover the detector, telemetry protocol/server/agent,
and pipeline alert extraction. They do not test Ryu, Open vSwitch, Mininet,
or actual dynamic rule enforcement. Those checks must be run in the Ubuntu VM.
