# Network Monitoring and Alert System — Question 6

A four-component Computer Networks project combining UDP host telemetry,
Mininet/Open vSwitch, a Ryu SDN controller, flow-statistics monitoring and
threshold-based alerting.

## Architecture

- **Member 1:** Mininet topology and Ryu controller; exports cumulative
  OpenFlow flow counters over UDP and accepts explicit block/unblock commands.
- **Member 2:** UDP telemetry agents, JSON protocol and central telemetry server.
- **Member 3:** `monitoring/detector.py`; calculates Mbps/packets-per-second
  from successive switch counters and generates threshold alerts.
- **Member 4:** `integration/`; connects detector results, receives controller
  flow-statistics datagrams and maintains integration documentation.

## Repository layout

```text
controller/       Ryu OpenFlow 1.3 controller
mininet/          Two-switch/four-host Mininet topology
telemetry/        UDP agent, server and JSON protocol
monitoring/       Traffic-rate detector
integration/      Detector pipeline and flow-statistics UDP receiver
tests/            Unit tests for detector, telemetry and integration
docs/             Setup, message format, integration, testing and demo guides
```

## Network and port plan

All processes below are expected to run on the same Ubuntu VM except that
host telemetry agents/server run inside Mininet host namespaces.

| Purpose | Transport | Address/port |
|---|---|---|
| Ryu OpenFlow listener | TCP | `127.0.0.1:6653` |
| Controller flow-statistics export | UDP | `127.0.0.1:9998` |
| Host telemetry server in Mininet h4 | UDP | `10.0.0.4:9999` |
| Controller block/unblock listener | UDP | `127.0.0.1:10000` |

The controller control port is deliberately different from the host telemetry
port. The telemetry server runs inside Mininet host `h4`, so its UDP port 9999
does not conflict with the controller process in the Ubuntu root namespace.

## Local tests (macOS or Linux)

From the repository root:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q controller mininet monitoring telemetry integration tests
```

The detector, telemetry, pipeline and statistics-receiver unit tests do not
require Mininet or Ryu. During this integration pass, all **22 tests passed**.
This is local Python verification only; it is not an end-to-end Mininet test.

## Ubuntu/Mininet setup

Use the team's Ubuntu VM. Mininet and Open vSwitch require Linux networking
features and should not be run natively on macOS.

Install system packages:

```bash
sudo apt update
sudo apt install -y mininet openvswitch-switch iproute2 iperf git python3 python3-venv
```

Create a virtual environment for Ryu and install the pinned controller dependency:

```bash
python3 -m venv ryu-venv
source ryu-venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements-controller.txt
```

**Compatibility note:** Ryu 4.34 is an older release. Confirm that it installs
and starts under the Python version in the team's Ubuntu VM before the final
demo. Do not change the controller version independently of the team.

### Terminal 1 — Start Ryu

From the repository root, with `ryu-venv` activated:

```bash
ryu-manager --ofp-tcp-listen-port 6653 controller/monitoring_controller.py
```

### Terminal 2 — Start the flow-statistics receiver

```bash
python3 -m integration.stats_receiver --port 9998
```

For an isolated lab demonstration of temporary dynamic blocking, use the
explicit opt-in mode:

```bash
python3 -m integration.stats_receiver --port 9998 --auto-block --block-seconds 10
```

Auto-block mode sends a block command only for a HIGH Mbps alert with an
IPv4 source address, then requests an unblock after the configured duration.
Use it only in the isolated Mininet lab. Verify the actual OpenFlow rule and
traffic effect; a log message alone is not proof of enforcement.

### Terminal 3 — Start Mininet

```bash
sudo mn -c
sudo python3 mininet/topology.py
```

At the Mininet prompt:

```text
pingall
```

The topology uses `h1`–`h4` with addresses `10.0.0.1`–`10.0.0.4`, switches
`s1` and `s2`, and a 10 Mbps / 5 ms inter-switch link.

### Start host telemetry inside Mininet

At the Mininet prompt, start the telemetry server inside `h4`:

```text
h4 python3 -m telemetry.server --bind 0.0.0.0 --port 9999 --detector &
```

Start agents on the other hosts:

```text
h1 python3 -m telemetry.agent --host h1 --iface h1-eth0 --server 10.0.0.4 --port 9999 &
h2 python3 -m telemetry.agent --host h2 --iface h2-eth0 --server 10.0.0.4 --port 9999 &
h3 python3 -m telemetry.agent --host h3 --iface h3-eth0 --server 10.0.0.4 --port 9999 &
```

If the Python package is not found inside a Mininet host, check the current
working directory and Python path from that host. The repository directory
must be visible inside each host namespace.

## Generate traffic and inspect results

At the Mininet prompt, use ping for connectivity and `iperf`/`iperf3` where
available to generate traffic between hosts. Generate traffic across the
inter-switch link to exercise the configured bottleneck.

The flow-statistics receiver logs samples and detector rates. The first sample
for each flow establishes a baseline; subsequent samples are required to
calculate rates. Tune `NetworkDetector(max_mbps=...)` to the experiment and
record the selected threshold in the report.

## Dynamic SDN response

The Ryu controller accepts these local UDP JSON commands on port 10000:

```json
{"action": "block_ip", "ip": "10.0.0.1"}
{"action": "unblock_ip", "ip": "10.0.0.1"}
```

The optional receiver `--auto-block` mode connects a HIGH Mbps alert with
the source IP carried by an IPv4 flow-statistics sample to the controller.
The controller installs a higher-priority source-IP drop rule and later
removes its own matching rule when the timed unblock command arrives.

This behavior must be verified in Mininet by checking the OpenFlow rules and
measuring the affected traffic. Do not claim it has been demonstrated until
the team has run that test.

## Evaluation and submission evidence

The team still needs to execute and document:
- Mininet startup and switch/controller connection.
- `pingall` and multi-host UDP telemetry.
- Actual switch-flow samples and calculated rates.
- Normal and above-threshold traffic cases.
- Dynamic block/unblock behavior and recovery.
- Performance comparison against a clearly defined baseline.
- Screenshots, exact commands, measured results and environment versions.

Do not invent performance values or mark unrun tests as passed. See
`docs/TESTING_GUIDE.md` and `docs/DEMO_GUIDE.md`.

## Important limitations

- Host telemetry counters are informational; traffic-rate detection uses
  cumulative SDN switch flow counters.
- The detector's first sample is a baseline, not an alert.
- Dynamic blocking is optional at receiver startup and must be verified.
- Full Mininet/Ryu end-to-end operation has not been verified by the local
  Python unit tests.
