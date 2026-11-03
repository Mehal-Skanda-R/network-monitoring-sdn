# UDP Telemetry Message Format (Member 2)

Status: implemented in `telemetry/protocol.py`; unit-tested locally. Not yet run inside Mininet.

## Datagram

One UDP datagram carries one UTF-8 JSON object, at most 1024 bytes (real messages are about 100 bytes).

```json
{"host": "h1", "timestamp": 1792842000.0, "bytes_sent": 9600, "packets_sent": 120}
```

| Field          | Type            | Rule                                               |
|----------------|-----------------|----------------------------------------------------|
| `host`         | string          | non-empty, at most 64 characters                   |
| `timestamp`    | number          | finite, >= 0, seconds since epoch (sender clock)   |
| `bytes_sent`   | integer         | >= 0, cumulative interface TX byte counter         |
| `packets_sent` | integer         | >= 0, cumulative interface TX packet counter       |

These are exactly the fields of the agreed input to `NetworkDetector.process_telemetry()`.
Booleans are rejected as integers. Extra fields are ignored and dropped by the server.

## Important boundary

These are host-side counters. They are NOT SDN switch flow counters and must not be fed to
`process_flow_stats()`. Alerting on traffic rate uses the switch counters from Member 1.

## Server behaviour

- Malformed datagrams (bad UTF-8/JSON, missing/ill-typed fields, oversized) are logged, counted in
  `stats["malformed"]`, and dropped. The server keeps running.
- If the handler (for example the detector) raises, the error is logged and counted in
  `stats["handler_errors"]`; the server keeps running.
- `server.silent_hosts(older_than)` lists hosts not heard from recently (dead agent or cut link).
- UDP gives no delivery guarantee: lost or reordered datagrams are not retransmitted. Counters are
  cumulative, so a lost report only coarsens the next rate calculation.

## Interface to other components

```python
from telemetry.server import TelemetryServer
server = TelemetryServer("0.0.0.0", 9999, handler=callable_taking_one_dict)
server.serve_forever()          # or server.start_in_thread()
```

`handler(msg)` receives the validated 4-field dict. CLI `--detector` wires it through `integration.MonitoringPipeline` and prints only actual alert
entries. Local tests cover the detector/pipeline interface; Mininet execution remains unverified.
