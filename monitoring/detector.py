"""
Network Monitoring and Alert System — detection module.

This module is independent of Mininet and can be tested on macOS.
It accepts normalized telemetry and SDN flow-statistics dictionaries.
The integration layer (UDP server/controller adapter) is responsible for
converting incoming data into the documented formats in README.md.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import time


@dataclass
class Alert:
    severity: str
    source: str
    metric: str
    value: float
    threshold: float
    message: str
    timestamp: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class NetworkDetector:
    """
    Threshold detector and rate calculator.

    Expected flow-statistics fields:
        switch: str
        flow_id: str
        byte_count: int  (cumulative counter)
        packet_count: int (cumulative counter, optional)
        timestamp: float (Unix timestamp; optional, defaults to current time)

    Expected telemetry fields can include:
        host: str
        bytes_sent: int
        packets_sent: int
        timestamp: float

    Rates are calculated from successive cumulative byte counters.
    """

    def __init__(
        self,
        max_mbps: float = 5.0,
        max_packets_per_second: Optional[float] = None,
        stale_after_seconds: float = 10.0,
    ) -> None:
        if max_mbps <= 0:
            raise ValueError("max_mbps must be greater than zero")
        if max_packets_per_second is not None and max_packets_per_second <= 0:
            raise ValueError("max_packets_per_second must be greater than zero")
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be greater than zero")

        self.max_mbps = float(max_mbps)
        self.max_packets_per_second = (
            float(max_packets_per_second)
            if max_packets_per_second is not None else None
        )
        self.stale_after_seconds = float(stale_after_seconds)
        self._previous_flows: Dict[str, Dict[str, float]] = {}
        self._last_seen: Dict[str, float] = {}

    @staticmethod
    def _number(data: Dict[str, Any], key: str) -> float:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"'{key}' must be numeric")
        if value < 0:
            raise ValueError(f"'{key}' cannot be negative")
        return float(value)

    def process_flow_stats(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Process one SDN flow-counter sample and return rates and alerts."""
        switch = str(stats.get("switch", "unknown-switch"))
        flow_id = str(stats.get("flow_id", "unknown-flow"))
        byte_count = self._number(stats, "byte_count")
        packet_count = self._number(stats, "packet_count") if "packet_count" in stats else 0.0
        timestamp = float(stats.get("timestamp", time.time()))
        key = f"{switch}:{flow_id}"
        self._last_seen[key] = timestamp

        previous = self._previous_flows.get(key)
        self._previous_flows[key] = {
            "byte_count": byte_count,
            "packet_count": packet_count,
            "timestamp": timestamp,
        }

        result: Dict[str, Any] = {
            "switch": switch,
            "flow_id": flow_id,
            "byte_count": int(byte_count),
            "packet_count": int(packet_count),
            "timestamp": timestamp,
            "mbps": None,
            "packets_per_second": None,
            "alerts": [],
            "note": None,
        }

        if previous is None:
            result["note"] = "Baseline sample recorded; send another sample to calculate rates."
            return result

        elapsed = timestamp - previous["timestamp"]
        if elapsed <= 0:
            result["note"] = "Rate not calculated: timestamp must increase between samples."
            return result

        byte_delta = byte_count - previous["byte_count"]
        packet_delta = packet_count - previous["packet_count"]

        # Counters can reset when a flow is removed/recreated or a switch restarts.
        if byte_delta < 0 or packet_delta < 0:
            result["note"] = "Counter reset detected; new baseline recorded."
            return result

        mbps = (byte_delta * 8.0) / elapsed / 1_000_000.0
        pps = packet_delta / elapsed
        result["mbps"] = round(mbps, 6)
        result["packets_per_second"] = round(pps, 3)

        if mbps > self.max_mbps:
            result["alerts"].append(
                Alert(
                    severity="HIGH",
                    source=key,
                    metric="mbps",
                    value=round(mbps, 6),
                    threshold=self.max_mbps,
                    message=f"Flow {key} traffic rate {mbps:.3f} Mbps exceeds "
                            f"the {self.max_mbps:.3f} Mbps threshold.",
                    timestamp=timestamp,
                ).to_dict()
            )

        if (
            self.max_packets_per_second is not None
            and pps > self.max_packets_per_second
        ):
            result["alerts"].append(
                Alert(
                    severity="HIGH",
                    source=key,
                    metric="packets_per_second",
                    value=round(pps, 3),
                    threshold=self.max_packets_per_second,
                    message=f"Flow {key} packet rate {pps:.1f} packets/s exceeds "
                            f"the {self.max_packets_per_second:.1f} packets/s threshold.",
                    timestamp=timestamp,
                ).to_dict()
            )

        return result

    def process_telemetry(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and inspect host-reported telemetry.
        This does not replace actual SDN flow statistics.
        """
        host = str(telemetry.get("host", "unknown-host"))
        timestamp = float(telemetry.get("timestamp", time.time()))
        result: Dict[str, Any] = {
            "host": host,
            "timestamp": timestamp,
            "bytes_sent": None,
            "packets_sent": None,
            "alerts": [],
        }

        for field in ("bytes_sent", "packets_sent"):
            if field in telemetry:
                result[field] = int(self._number(telemetry, field))

        return result

    def find_stale_flows(self, now: Optional[float] = None) -> List[str]:
        """Return flow keys whose last sample is older than the configured limit."""
        current = time.time() if now is None else float(now)
        return sorted(
            key for key, seen in self._last_seen.items()
            if current - seen > self.stale_after_seconds
        )
