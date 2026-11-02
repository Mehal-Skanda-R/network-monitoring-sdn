"""UDP telemetry agent: runs on each Mininet host and reports its own
transmit counters to the central server.

These host-side numbers are informational. Traffic-rate alerting must use the
SDN switch flow counters, not these values.

Mininet usage (inside a host, interface is usually <host>-eth0):
    h1 python3 -m telemetry.agent --host h1 --iface h1-eth0 --server 10.0.0.100 --port 9999

Test anywhere (no Linux counters needed):
    python3 -m telemetry.agent --host h1 --simulate --server 127.0.0.1 --count 5
"""

import argparse
import logging
import socket
import time

from .protocol import ProtocolError, encode

log = logging.getLogger("telemetry.agent")


def read_interface_counters(iface):
    """Cumulative (tx_bytes, tx_packets) from Linux sysfs."""
    base = "/sys/class/net/%s/statistics/" % iface
    with open(base + "tx_bytes") as f:
        tx_bytes = int(f.read())
    with open(base + "tx_packets") as f:
        tx_packets = int(f.read())
    return tx_bytes, tx_packets


class SimulatedCounters:
    """Monotonic fake counters for development off Linux."""

    def __init__(self, bytes_per_sec=100000, packets_per_sec=100):
        self.bps, self.pps = bytes_per_sec, packets_per_sec
        self.start = time.time()

    def __call__(self):
        elapsed = time.time() - self.start
        return int(self.bps * elapsed), int(self.pps * elapsed)


class TelemetryAgent:
    def __init__(self, host, server_addr, counter_source, interval=1.0):
        self.host = host
        self.server_addr = server_addr
        self.counter_source = counter_source
        self.interval = interval
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sent = 0
        self.errors = 0

    def close(self):
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def build_message(self):
        tx_bytes, tx_packets = self.counter_source()
        return {
            "host": self.host,
            "timestamp": time.time(),
            "bytes_sent": tx_bytes,
            "packets_sent": tx_packets,
        }

    def send_once(self):
        """Send one report. Returns True on success; never raises on network/IO errors."""
        try:
            data = encode(self.build_message())
            self.sock.sendto(data, self.server_addr)
        except (OSError, ProtocolError, ValueError) as exc:
            self.errors += 1
            log.warning("send failed: %s", exc)
            return False
        self.sent += 1
        return True

    def run(self, count=None):
        n = 0
        while count is None or n < count:
            self.send_once()
            n += 1
            if count is None or n < count:
                time.sleep(self.interval)


def main():
    p = argparse.ArgumentParser(description="UDP telemetry agent")
    p.add_argument("--host", required=True, help="host name, e.g. h1")
    p.add_argument("--server", required=True, help="server IP or name")
    p.add_argument("--port", type=int, default=9999)
    p.add_argument("--iface", help="interface to read counters from, e.g. h1-eth0")
    p.add_argument("--simulate", action="store_true", help="use fake counters")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--count", type=int, help="stop after N reports (default: forever)")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.simulate:
        source = SimulatedCounters()
    elif args.iface:
        source = lambda: read_interface_counters(args.iface)
    else:
        p.error("give --iface or --simulate")

    with TelemetryAgent(args.host, (args.server, args.port), source, args.interval) as agent:
        try:
            agent.run(args.count)
        except KeyboardInterrupt:
            pass
        print("sent=%d errors=%d" % (agent.sent, agent.errors))


if __name__ == "__main__":
    main()
