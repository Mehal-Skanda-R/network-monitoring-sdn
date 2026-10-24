"""Run a short local demonstration of normal and high traffic."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from monitoring.detector import NetworkDetector

detector = NetworkDetector(max_mbps=1.0, max_packets_per_second=300)

samples = [
    {"switch": "s1", "flow_id": "h1-to-h2", "byte_count": 0,
     "packet_count": 0, "timestamp": 100.0},
    {"switch": "s1", "flow_id": "h1-to-h2", "byte_count": 50_000,
     "packet_count": 100, "timestamp": 101.0},
    {"switch": "s1", "flow_id": "h1-to-h2", "byte_count": 400_000,
     "packet_count": 600, "timestamp": 102.0},
]

for sample in samples:
    result = detector.process_flow_stats(sample)
    print(json.dumps(result, indent=2))
