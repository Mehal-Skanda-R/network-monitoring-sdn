"""Tests for the UDP telemetry agent/server. Run from repo root:

    python3 -m unittest tests.test_udp_telemetry -v
"""

import json
import socket
import time
import unittest

from telemetry.agent import TelemetryAgent
from telemetry.server import TelemetryServer
from telemetry.protocol import MAX_DATAGRAM, ProtocolError, decode, encode


def wait_for(predicate, timeout=2.0):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.01)
    return False


class ProtocolTests(unittest.TestCase):
    GOOD = {"host": "h1", "timestamp": 1792842000.0, "bytes_sent": 9600, "packets_sent": 120}

    def test_roundtrip(self):
        self.assertEqual(decode(encode(self.GOOD)), self.GOOD)

    def test_extra_fields_dropped(self):
        msg = dict(self.GOOD, extra="x")
        self.assertEqual(decode(json.dumps(msg).encode()), self.GOOD)

    def test_rejects_bad_messages(self):
        bad = [
            b"not json",
            b"\xff\xfe",
            b"[1,2,3]",
            b'{"host":"h1"}',
            json.dumps(dict(self.GOOD, bytes_sent=-1)).encode(),
            json.dumps(dict(self.GOOD, packets_sent=1.5)).encode(),
            json.dumps(dict(self.GOOD, bytes_sent=True)).encode(),
            json.dumps(dict(self.GOOD, host="")).encode(),
            json.dumps(dict(self.GOOD, timestamp="now")).encode(),
            b"x" * (MAX_DATAGRAM + 1),
        ]
        for data in bad:
            with self.assertRaises(ProtocolError, msg=data[:30]):
                decode(data)


class ServerTests(unittest.TestCase):
    def make_agent(self, host, counters):
        agent = TelemetryAgent(host, self.addr, counters)
        self.addCleanup(agent.close)
        return agent

    def setUp(self):
        self.received = []
        self.server = TelemetryServer("127.0.0.1", 0, handler=self.received.append)
        self.server.start_in_thread()
        self.addr = ("127.0.0.1", self.server.port)

    def tearDown(self):
        self.server.stop()

    def test_multiple_hosts(self):
        counters = {"h1": (1000, 10), "h2": (2000, 20), "h3": (3000, 30)}
        for host, c in counters.items():
            agent = self.make_agent(host, lambda c=c: c)
            self.assertTrue(agent.send_once())
        self.assertTrue(wait_for(lambda: len(self.received) == 3))
        self.assertEqual({m["host"] for m in self.received}, set(counters))
        self.assertEqual(self.server.stats["valid"], 3)

    def test_malformed_does_not_stop_server(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(s.close)
        s.sendto(b"garbage", self.addr)
        s.sendto(b'{"host":"h1"}', self.addr)
        self.make_agent("h1", lambda: (5, 1)).send_once()
        self.assertTrue(wait_for(lambda: len(self.received) == 1))
        self.assertEqual(self.server.stats["malformed"], 2)

    def test_handler_exception_is_contained(self):
        def boom(msg):
            raise RuntimeError("detector bug")

        self.server.handler = boom
        self.make_agent("h1", lambda: (5, 1)).send_once()
        self.assertTrue(wait_for(lambda: self.server.stats["handler_errors"] == 1))
        self.server.handler = self.received.append
        self.make_agent("h2", lambda: (6, 2)).send_once()
        self.assertTrue(wait_for(lambda: len(self.received) == 1))

    def test_silent_hosts(self):
        self.make_agent("h1", lambda: (5, 1)).send_once()
        self.assertTrue(wait_for(lambda: "h1" in self.server.hosts))
        self.assertEqual(self.server.silent_hosts(older_than=10), [])
        self.assertEqual(self.server.silent_hosts(older_than=10, now=time.time() + 60), ["h1"])


class AgentTests(unittest.TestCase):
    def test_counter_failure_does_not_raise(self):
        def broken():
            raise OSError("iface gone")

        agent = TelemetryAgent("h1", ("127.0.0.1", 9), broken)
        self.addCleanup(agent.close)
        self.assertFalse(agent.send_once())
        self.assertEqual(agent.errors, 1)

    def test_unresolvable_server_does_not_raise(self):
        agent = TelemetryAgent("h1", ("no-such-host.invalid", 9), lambda: (1, 1))
        self.addCleanup(agent.close)
        self.assertFalse(agent.send_once())


if __name__ == "__main__":
    unittest.main()
