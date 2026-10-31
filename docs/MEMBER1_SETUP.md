cat > docs/MEMBER1_SETUP.md <<'MD'
# Member 1 - Ryu Controller and Mininet Topology

## Responsibilities

Member 1 provides:

- Mininet topology.
- Open vSwitch switches using OpenFlow 1.3.
- Ryu SDN controller.
- MAC learning and packet forwarding.
- Periodic OpenFlow flow-statistics retrieval.
- JSON export of cumulative flow counters.
- Controller-side IPv4 block and unblock commands.

## Topology

The initial topology contains:

- Hosts: h1, h2, h3, h4
- Switches: s1, s2
- Inter-switch link: 10 Mbps, 5 ms delay
- OpenFlow version: 1.3
- Controller: Ryu, TCP port 6653

Host addresses:

| Host | IP address |
|---|---|
| h1 | 10.0.0.1/24 |
| h2 | 10.0.0.2/24 |
| h3 | 10.0.0.3/24 |
| h4 | 10.0.0.4/24 |

## Dependencies

The Ubuntu machine running the network needs:

- Python 3
- Mininet
- Open vSwitch
- Ryu 4.34

Install system packages:

    sudo apt update
    sudo apt install -y mininet openvswitch-switch iproute2 iperf git python3 python3-pip python3-venv

Create a Python virtual environment for Ryu:

    python3 -m venv ryu-venv
    source ryu-venv/bin/activate
    pip install --upgrade pip wheel
    pip install -r requirements-controller.txt

Ryu 4.34 is an older controller release. Confirm compatibility with
the Python version available on the target Ubuntu machine before the
team's final demonstration.

## Start the controller

From the repository root:

    source ryu-venv/bin/activate
    ryu-manager --ofp-tcp-listen-port 6653 controller/monitoring_controller.py

Keep the controller running.

## Start Mininet

In a second terminal:

    sudo mn -c
    sudo python3 mininet/topology.py

At the Mininet prompt, test host connectivity:

    pingall

## Flow-statistics interface

The controller periodically requests OpenFlow flow statistics.

Default UDP destination:

    FLOW_STATS_HOST=127.0.0.1
    FLOW_STATS_PORT=9998

Each UDP datagram contains one JSON dictionary:

    {
      "switch": "s1",
      "flow_id": "stable-flow-identifier",
      "byte_count": 400000,
      "packet_count": 600,
      "timestamp": 1729420000.0
    }

The fields are compatible with:

    detector.process_flow_stats(flow_sample)

Important:

- byte_count is the cumulative switch byte counter.
- packet_count is the cumulative switch packet counter.
- timestamp is Unix time in seconds.
- flow_id must remain stable for the same flow.
- Do not send interval deltas as byte_count.

The UDP receiver at port 9998 is an integration adapter for
controller statistics. It is not Member 2's host-telemetry server.

Member 4 is responsible for connecting the received dictionary
to NetworkDetector.process_flow_stats().

## Dynamic SDN control interface

The controller listens for JSON commands on:

    CONTROL_HOST=127.0.0.1
    CONTROL_PORT=9999

Block an IPv4 source address:

    {"action": "block_ip", "ip": "10.0.0.1"}

Remove the corresponding controller-installed rule:

    {"action": "unblock_ip", "ip": "10.0.0.1"}

These commands are separate from detector alerts. The integration
layer must explicitly decide when to request an action.

The control listener binds to loopback by default. Do not expose
this unauthenticated UDP interface to an untrusted network.

## Configuration

The controller supports these environment variables:

| Variable | Default | Purpose |
|---|---|---|
| FLOW_STATS_HOST | 127.0.0.1 | Statistics receiver address |
| FLOW_STATS_PORT | 9998 | Statistics receiver UDP port |
| CONTROL_HOST | 127.0.0.1 | Control listener address |
| CONTROL_PORT | 9999 | Control listener UDP port |

Set matching values in the integration adapter.

## Ownership boundaries

- Member 1: topology, Ryu controller, flow statistics, dynamic flow rules.
- Member 2: host telemetry agents, UDP telemetry server and decoding.
- Member 3: monitoring/detector.py, thresholds and detector tests.
- Member 4: integration, application run procedure and final documentation.

## Runtime verification checklist

The teammate running the Ubuntu/Mininet environment should verify:

1. Ryu starts without import or runtime errors.
2. Both switches connect to the controller.
3. OpenFlow 1.3 is negotiated.
4. Mininet hosts can communicate using pingall.
5. The controller sends flow-statistics JSON to the configured receiver.
6. Two or more samples for the same flow have increasing timestamps.
7. byte_count and packet_count are cumulative counters.
8. The integration adapter calls process_flow_stats().
9. The block command installs a drop rule.
10. The unblock command removes that rule.
11. Real outputs and measurements are saved for the final report.

Do not claim end-to-end operation until the team has completed
these tests in the target environment.
MD
