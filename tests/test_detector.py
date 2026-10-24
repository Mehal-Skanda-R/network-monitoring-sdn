"""Local tests for monitoring/detector.py. No Mininet or third-party packages needed."""
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitoring.detector import NetworkDetector


class DetectorTests(unittest.TestCase):
    def test_first_sample_sets_baseline(self):
        detector = NetworkDetector(max_mbps=1.0)
        result = detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 1000,
            "packet_count": 10, "timestamp": 100.0
        })
        self.assertIsNone(result["mbps"])
        self.assertIn("Baseline", result["note"])

    def test_normal_rate_has_no_alert(self):
        detector = NetworkDetector(max_mbps=1.0)
        detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 0,
            "packet_count": 0, "timestamp": 100.0
        })
        result = detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 100_000,
            "packet_count": 100, "timestamp": 101.0
        })
        self.assertAlmostEqual(result["mbps"], 0.8)
        self.assertEqual(result["alerts"], [])

    def test_high_rate_triggers_alert(self):
        detector = NetworkDetector(max_mbps=1.0)
        detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 0,
            "packet_count": 0, "timestamp": 100.0
        })
        result = detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 250_000,
            "packet_count": 500, "timestamp": 101.0
        })
        self.assertAlmostEqual(result["mbps"], 2.0)
        self.assertEqual(result["alerts"][0]["severity"], "HIGH")

    def test_counter_reset_does_not_create_negative_rate(self):
        detector = NetworkDetector(max_mbps=1.0)
        detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 1000,
            "packet_count": 10, "timestamp": 100.0
        })
        result = detector.process_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 10,
            "packet_count": 1, "timestamp": 101.0
        })
        self.assertIsNone(result["mbps"])
        self.assertIn("reset", result["note"].lower())

    def test_telemetry_validation(self):
        detector = NetworkDetector()
        result = detector.process_telemetry({
            "host": "h1", "bytes_sent": 500, "packets_sent": 5,
            "timestamp": 100.0
        })
        self.assertEqual(result["host"], "h1")
        self.assertEqual(result["bytes_sent"], 500)

    def test_invalid_negative_counter_is_rejected(self):
        detector = NetworkDetector()
        with self.assertRaises(ValueError):
            detector.process_flow_stats({
                "switch": "s1", "flow_id": "f1", "byte_count": -1,
                "timestamp": 100.0
            })


if __name__ == "__main__":
    unittest.main(verbosity=2)
