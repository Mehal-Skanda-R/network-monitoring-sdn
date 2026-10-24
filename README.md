# Network Monitoring and Alert System — Member 3 Package

This package implements the **monitoring/detection logic** for Project 6. It is designed to be developed and tested on macOS using Python 3, without Mininet or third-party packages.

## Scope

Included:
- Calculate Mbps from successive SDN flow byte-counter samples.
- Optionally calculate packets per second.
- Raise configurable threshold alerts.
- Handle the first sample, non-increasing timestamps, and counter resets.
- Validate basic host telemetry fields.
- Identify flows whose samples have become stale.
- Local unit tests and a demonstration script.

Not included:
- A UDP listener/server.
- Mininet topology or OpenFlow controller.
- Direct retrieval of switch statistics.
- Automatic SDN flow modification or blocking.

Those components belong to other team members and must be integrated and tested in the Ubuntu/Mininet environment. Do not claim end-to-end SDN functionality until it has been demonstrated there.

## Files

```text
monitoring/detector.py       Detection module
tests/test_detector.py      Unit tests
tests/demo_detector.py      Local sample demonstration
docs/INTEGRATION.md         Interface contract for teammates
```

## Run locally on macOS

Check Python:

```bash
python3 --version
```

From the project root:

```bash
python3 -m unittest discover -s tests -p 'test_detector.py' -v
python3 tests/demo_detector.py
```

No `pip install` is required. The code uses the Python standard library.

## Flow-statistics input contract

The SDN/controller adapter should call `NetworkDetector.process_flow_stats()` with one dictionary per flow sample:

```python
{
    "switch": "s1",
    "flow_id": "h1-to-h2",
    "byte_count": 400000,
    "packet_count": 600,
    "timestamp": 102.0
}
```

- `byte_count` and `packet_count` are cumulative counters from the switch, not per-interval deltas.
- `timestamp` is a Unix timestamp in seconds. Samples for a given flow must use the same clock and increasing timestamps.
- The first sample establishes a baseline. A second valid sample is required to calculate a rate.
- `switch` plus `flow_id` identifies the counter stream.
- The example `timestamp` values in tests are synthetic; production code should use real timestamps.

Example:

```python
from monitoring.detector import NetworkDetector

detector = NetworkDetector(max_mbps=5.0)
result = detector.process_flow_stats(flow_stats_dict)
print(result)
```

The result includes `mbps`, `packets_per_second`, `alerts`, and an explanatory `note` where a rate cannot yet be calculated.

## Rate calculation

For two samples from the same flow:

`Mbps = (change in bytes × 8) / elapsed seconds / 1,000,000`

`Packets per second = change in packets / elapsed seconds`

The threshold values are configuration choices for the demonstration, not universal definitions of abnormal traffic. Tune them to the topology and traffic generated.

## Host telemetry contract

The UDP server can pass a decoded telemetry dictionary to `process_telemetry()`:

```python
{
    "host": "h1",
    "timestamp": 1792842000.0,
    "bytes_sent": 9600,
    "packets_sent": 120
}
```

The current implementation validates and normalizes this data; it does not infer switch traffic rates from host-reported counts. Actual network rates must use SDN flow counters.

## Suggested team integration

1. Member 2's UDP server receives and decodes telemetry JSON.
2. Member 2 or Member 4 passes telemetry to `process_telemetry()`.
3. Member 1's controller adapter obtains switch flow counters.
4. Member 4 connects the controller output to `process_flow_stats()`.
5. The application displays returned rates and alerts.
6. The team tests it on Mininet and documents actual outputs.

See `docs/INTEGRATION.md` for the agreed interface and ownership boundaries.

## Known limitation

Threshold alerts are detection only. They do **not** change OpenFlow rules or block traffic. Dynamic SDN action must be implemented by the controller/integration owner and demonstrated separately to satisfy the rubric's dynamic-SDN criterion.
