"""Central UDP monitoring server.

Receives telemetry datagrams from many hosts, validates them, keeps per-host
statistics and hands every valid message to an optional handler (for example
NetworkDetector.process_telemetry). Malformed datagrams are counted and
dropped; they never crash the server.

Run:  python3 -m telemetry.server --port 9999 [--detector]
"""

import argparse
import logging
import socket
import threading
import time

from .protocol import MAX_DATAGRAM, ProtocolError, decode

log = logging.getLogger("telemetry.server")


class TelemetryServer:
    def __init__(self, bind_host="0.0.0.0", port=9999, handler=None):
        self.handler = handler
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((bind_host, port))
        self.sock.settimeout(0.5)  # lets the loop notice stop()
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.stats = {"received": 0, "valid": 0, "malformed": 0, "handler_errors": 0}
        self.hosts = {}  # host -> {"last_seen", "count", "last_msg"}

    # -- lifecycle ---------------------------------------------------------
    def serve_forever(self):
        log.info("listening on UDP port %d", self.port)
        while not self._stop.is_set():
            try:
                data, addr = self.sock.recvfrom(MAX_DATAGRAM + 1)
            except socket.timeout:
                continue
            except OSError as exc:
                if self._stop.is_set():
                    break
                log.warning("recv error: %s", exc)
                continue
            self.handle_datagram(data, addr)
        self.sock.close()

    def stop(self):
        self._stop.set()

    def start_in_thread(self):
        t = threading.Thread(target=self.serve_forever, daemon=True)
        t.start()
        return t

    # -- processing --------------------------------------------------------
    def handle_datagram(self, data, addr):
        with self._lock:
            self.stats["received"] += 1
        try:
            msg = decode(data)
        except ProtocolError as exc:
            with self._lock:
                self.stats["malformed"] += 1
            log.warning("dropped datagram from %s:%s: %s", addr[0], addr[1], exc)
            return None

        with self._lock:
            self.stats["valid"] += 1
            entry = self.hosts.setdefault(msg["host"], {"count": 0})
            entry["count"] += 1
            entry["last_seen"] = time.time()
            entry["last_msg"] = msg
        log.info("telemetry %s", msg)

        if self.handler is not None:
            try:
                self.handler(msg)
            except Exception:  # a bad handler must not kill the server
                with self._lock:
                    self.stats["handler_errors"] += 1
                log.exception("handler failed for %s", msg)
        return msg

    def silent_hosts(self, older_than=10.0, now=None):
        """Hosts not heard from for `older_than` seconds (agent dead / link cut)."""
        now = time.time() if now is None else now
        with self._lock:
            return sorted(h for h, e in self.hosts.items() if now - e["last_seen"] > older_than)


def _detector_handler():
    """Forward telemetry to Member 3's detector and print any alerts."""
    from monitoring.detector import NetworkDetector  # needs repo root on sys.path

    detector = NetworkDetector()

    def handler(msg):
        result = detector.process_telemetry(msg)
        alerts = result if isinstance(result, list) else ([result] if result else [])
        for alert in alerts:
            print("ALERT:", alert, flush=True)

    return handler


def main():
    p = argparse.ArgumentParser(description="UDP telemetry server")
    p.add_argument("--bind", default="0.0.0.0")
    p.add_argument("--port", type=int, default=9999)
    p.add_argument("--detector", action="store_true",
                   help="pass telemetry to monitoring.detector.NetworkDetector")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()
    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

    handler = _detector_handler() if args.detector else None
    server = TelemetryServer(args.bind, args.port, handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.stop()
        print("\nstats:", server.stats)


if __name__ == "__main__":
    main()
