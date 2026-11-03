"""UDP receiver for Ryu flow-statistics datagrams.

Run from the repository root on the Ubuntu VM:
    python3 -m integration.stats_receiver --port 9998

Optional demo response:
    python3 -m integration.stats_receiver --auto-block --block-seconds 10

Auto-block is opt-in. It only acts when a HIGH Mbps alert includes an IPv4
source address, and it sends a timed unblock command after the configured
duration. Test this only in the isolated Mininet lab.
"""
import argparse
import json
import logging
import socket
import threading

from integration import MonitoringPipeline

LOG = logging.getLogger("integration.stats_receiver")


class StatsReceiver:
    REQUIRED = ("switch", "flow_id", "byte_count", "packet_count", "timestamp")

    def __init__(self, host="127.0.0.1", port=9998, control_host="127.0.0.1",
                 control_port=10000, auto_block=False, block_seconds=10.0):
        self.host = host
        self.port = port
        self.control_addr = (control_host, control_port)
        self.auto_block = auto_block
        self.block_seconds = block_seconds
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.settimeout(0.5)
        self.control_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.pipeline = MonitoringPipeline(on_alert=self._on_alert)
        self.received = 0
        self.invalid = 0
        self._stop = threading.Event()

    def _send_control(self, action, ip):
        payload = json.dumps({"action": action, "ip": ip}).encode("utf-8")
        self.control_sock.sendto(payload, self.control_addr)
        LOG.warning("Sent controller command: %s %s", action, ip)

    def _on_alert(self, alert):
        LOG.warning("ALERT %s", json.dumps(alert, sort_keys=True))

    def _maybe_block(self, sample, alerts):
        if not self.auto_block:
            return
        ip = sample.get("ipv4_src")
        if not ip or not any(
            a.get("severity") == "HIGH" and a.get("metric") == "mbps"
            for a in alerts
        ):
            return
        self._send_control("block_ip", ip)

        def restore():
            try:
                self._send_control("unblock_ip", ip)
            except OSError:
                LOG.exception("Could not send unblock command for %s", ip)

        timer = threading.Timer(self.block_seconds, restore)
        timer.daemon = True
        timer.start()

    def handle_datagram(self, data, address=("unknown", 0)):
        """Validate and process one controller flow-statistics datagram."""
        try:
            sample = json.loads(data.decode("utf-8"))
            if not isinstance(sample, dict):
                raise ValueError("datagram must contain a JSON object")
            missing = [f for f in self.REQUIRED if f not in sample]
            if missing:
                raise ValueError("missing fields: " + ", ".join(missing))
            result = self.pipeline.handle_flow_stats(sample)
            self.received += 1
            LOG.info(
                "FLOW %s %s Mbps=%s pps=%s",
                result.get("switch"), result.get("flow_id"),
                result.get("mbps"), result.get("packets_per_second")
            )
            self._maybe_block(sample, result.get("alerts", []))
            return result
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self.invalid += 1
            LOG.warning("Dropped invalid sample from %s: %s", address, exc)
            return None

    def stop(self):
        self._stop.set()

    def serve_forever(self):
        LOG.info("Listening for flow statistics on %s:%d", self.host, self.port)
        try:
            while not self._stop.is_set():
                try:
                    data, address = self.sock.recvfrom(65535)
                except socket.timeout:
                    continue
                self.handle_datagram(data, address)
        except KeyboardInterrupt:
            LOG.info("Stopping receiver")
        finally:
            self.sock.close()
            self.control_sock.close()


def main():
    parser = argparse.ArgumentParser(description="Receive Ryu UDP flow statistics")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9998)
    parser.add_argument("--control-host", default="127.0.0.1")
    parser.add_argument("--control-port", type=int, default=10000)
    parser.add_argument("--auto-block", action="store_true",
                        help="temporarily block source IP on HIGH Mbps alerts")
    parser.add_argument("--block-seconds", type=float, default=10.0)
    args = parser.parse_args()
    if args.block_seconds <= 0:
        parser.error("--block-seconds must be greater than zero")
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    StatsReceiver(
        args.bind, args.port, args.control_host, args.control_port,
        args.auto_block, args.block_seconds
    ).serve_forever()


if __name__ == "__main__":
    main()
