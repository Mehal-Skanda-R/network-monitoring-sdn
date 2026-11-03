# Testing Guide — Member 4

## Status

Local Python verification of the combined detector, telemetry, pipeline and
statistics-receiver components: **22 tests passed** in the preparation
environment. Python compilation also completed successfully.

This does not verify Ryu startup, Open vSwitch, Mininet, or live dynamic
OpenFlow rule enforcement. Those checks must be run in the team's Ubuntu VM.

## Integration test cases

| ID | Test | Expected result |
|---|---|---|
| T1 | Send a valid UDP telemetry message to the server | Server receives and decodes the message |
| T2 | Pass valid telemetry to `handle_telemetry` | Detector processes the agreed telemetry fields |
| T3 | Pass the first cumulative SDN counter sample | Detector establishes a baseline; no rate can be inferred from one sample |
| T4 | Pass a second counter sample for the same flow | Detector calculates traffic rates from counter differences and elapsed time |
| T5 | Generate traffic above a configured threshold | Detector returns an alert if its configured threshold is exceeded |
| T6 | Send a message missing a required field | Integration pipeline raises a clear `ValueError` |
| T7 | Stop updates for a flow and check stale flows | Detector reports stale flows according to its configured timeout |
| T8 | Trigger a detector alert with an alert callback configured | Callback receives the returned alert |
| T9 | Exercise the controller's dynamic response | Controller-side behavior is visibly demonstrated and documented |\n| T10 | Send flow-statistics UDP datagrams to port 9998 | Receiver validates samples and calls the detector pipeline |\n| T11 | Enable `--auto-block` in the isolated lab | HIGH Mbps alert with IPv4 source triggers temporary block and timed unblock |

## Important validation rules

- Use actual switch flow counters for SDN traffic-rate calculations.
- Do not substitute host telemetry counters for switch counters.
- Use at least two counter samples to calculate a rate.
- Check that timestamps are increasing and counter values are meaningful.
- Test malformed UDP messages at the UDP server boundary as well.
- Test dynamic controller behavior separately from alert generation.

## Evidence to capture

For each executed test, record:

- Test ID and purpose.
- Exact command or procedure.
- Environment and configuration.
- Actual output or screenshot.
- Pass/fail result.
- Any issue and its resolution.

Do not fill the results with fabricated outputs or screenshots.
