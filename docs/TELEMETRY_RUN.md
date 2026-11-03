# Running the UDP telemetry component

Requires Python 3.8+, standard library only. Run everything from the repository root.

## 1. Unit tests (any OS, including macOS)

```bash
python3 -m unittest tests.test_udp_telemetry -v
```

Expected: `Ran 9 tests ... OK`.

## 2. Local smoke test (any OS)

Terminal A:
```bash
python3 -m telemetry.server --port 9999
```
Terminal B:
```bash
python3 -m telemetry.agent --host h1 --simulate --server 127.0.0.1 --port 9999 --count 5
```
Expected: server logs `telemetry {...}` lines; agent prints `sent=5 errors=0`.

## 3. Inside Mininet (Ubuntu/Linux, needs Member 1's topology)

Pick a host for the server (example: `h4` at 10.0.0.4; adjust to the real topology).

```
mininet> h4 python3 -m telemetry.server --bind 0.0.0.0 --port 9999 --detector &
mininet> h1 python3 -m telemetry.agent --host h1 --iface h1-eth0 --server 10.0.0.4 --port 9999 &
mininet> h2 python3 -m telemetry.agent --host h2 --iface h2-eth0 --server 10.0.0.4 --port 9999 &
```

Mininet hosts share the filesystem, so run `mininet` from the repository root. Check the interface
name with `h1 ip link`. The server runs inside h4's network namespace; agents send to h4's Mininet IP.

## Verification evidence (what has actually been run)

- Unit tests: 9 passed on Linux, Python 3.13.
- Loopback smoke test: one server + three simulated agents (h1, h2, h3), 3 reports each, all
  received; a malformed datagram was dropped and logged.
- NOT yet verified: Mininet, real interface counters, `--detector` against the real detector.
