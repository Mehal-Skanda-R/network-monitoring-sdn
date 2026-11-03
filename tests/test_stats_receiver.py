import json
import unittest

from integration.stats_receiver import StatsReceiver


class StatsReceiverTests(unittest.TestCase):
    def setUp(self):
        self.receiver = StatsReceiver(host="127.0.0.1", port=0)

    def tearDown(self):
        self.receiver.sock.close()
        self.receiver.control_sock.close()

    def sample(self, byte_count, timestamp):
        return {
            "switch": "s1",
            "flow_id": "f1",
            "byte_count": byte_count,
            "packet_count": byte_count // 100,
            "timestamp": timestamp,
            "ipv4_src": "10.0.0.1",
        }

    def test_baseline_is_processed_without_alert(self):
        result = self.receiver.handle_datagram(
            json.dumps(self.sample(100, 1.0)).encode()
        )
        self.assertEqual(result["alerts"], [])
        self.assertEqual(self.receiver.received, 1)

    def test_high_rate_sample_generates_alert(self):
        self.receiver.handle_datagram(json.dumps(self.sample(100, 1.0)).encode())
        result = self.receiver.handle_datagram(
            json.dumps(self.sample(1_000_100, 2.0)).encode()
        )
        self.assertGreaterEqual(len(result["alerts"]), 1)
        self.assertEqual(self.receiver.received, 2)

    def test_invalid_datagram_is_dropped(self):
        result = self.receiver.handle_datagram(b"not-json")
        self.assertIsNone(result)
        self.assertEqual(self.receiver.invalid, 1)


if __name__ == "__main__":
    unittest.main()
