import unittest

from integration import MonitoringPipeline


class PipelineTests(unittest.TestCase):
    def test_baseline_does_not_publish_false_alert(self):
        received = []
        pipeline = MonitoringPipeline(on_alert=received.append)
        result = pipeline.handle_flow_stats({
            "switch": "s1", "flow_id": "f1", "byte_count": 100,
            "packet_count": 1, "timestamp": 1.0
        })
        self.assertEqual(result["alerts"], [])
        self.assertEqual(received, [])

    def test_high_rate_publishes_only_nested_alert(self):
        received = []
        pipeline = MonitoringPipeline(on_alert=received.append)
        base = {
            "switch": "s1", "flow_id": "f1", "byte_count": 100,
            "packet_count": 1, "timestamp": 1.0
        }
        pipeline.handle_flow_stats(base)
        high = dict(base, byte_count=1_000_100, packet_count=1001, timestamp=2.0)
        result = pipeline.handle_flow_stats(high)
        self.assertGreaterEqual(len(result["alerts"]), 1)
        self.assertEqual(received, result["alerts"])
        self.assertIn("severity", received[0])
        self.assertNotIn("mbps", received[0])

    def test_telemetry_without_alert_is_not_published(self):
        received = []
        pipeline = MonitoringPipeline(on_alert=received.append)
        result = pipeline.handle_telemetry({
            "host": "h1", "timestamp": 10.0,
            "bytes_sent": 100, "packets_sent": 1
        })
        self.assertEqual(result["alerts"], [])
        self.assertEqual(received, [])

    def test_missing_flow_field_is_rejected(self):
        pipeline = MonitoringPipeline()
        with self.assertRaises(ValueError):
            pipeline.handle_flow_stats({"switch": "s1"})


if __name__ == "__main__":
    unittest.main()
