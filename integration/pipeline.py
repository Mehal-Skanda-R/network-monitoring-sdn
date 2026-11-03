"""Bridge UDP telemetry and SDN flow statistics to NetworkDetector.

The detector returns a result dictionary containing an ``alerts`` list.
This module publishes only actual alert dictionaries to the callback.
"""
from collections.abc import Callable, Mapping
from typing import Any, Optional

from monitoring.detector import NetworkDetector

AlertCallback = Callable[[dict[str, Any]], None]


class MonitoringPipeline:
    def __init__(
        self,
        detector: Optional[NetworkDetector] = None,
        on_alert: Optional[AlertCallback] = None,
    ) -> None:
        self.detector = detector or NetworkDetector()
        self.on_alert = on_alert

    def handle_flow_stats(self, stats: Mapping[str, Any]) -> dict[str, Any]:
        self._require_fields(
            stats,
            ("switch", "flow_id", "byte_count", "packet_count", "timestamp"),
            "SDN flow statistics",
        )
        result = self.detector.process_flow_stats(dict(stats))
        self._publish(result)
        return result

    def handle_telemetry(self, telemetry: Mapping[str, Any]) -> dict[str, Any]:
        self._require_fields(
            telemetry,
            ("host", "timestamp", "bytes_sent", "packets_sent"),
            "UDP host telemetry",
        )
        result = self.detector.process_telemetry(dict(telemetry))
        self._publish(result)
        return result

    def check_stale_flows(self, now: Optional[float] = None) -> list[str]:
        if now is None:
            return self.detector.find_stale_flows()
        return self.detector.find_stale_flows(now=now)

    def _publish(self, detector_result: Any) -> list[dict[str, Any]]:
        """Publish only dictionaries inside detector_result['alerts']."""
        if detector_result is None:
            alerts: list[dict[str, Any]] = []
        elif isinstance(detector_result, Mapping):
            raw_alerts = detector_result.get("alerts", [])
            if not isinstance(raw_alerts, list):
                raise TypeError("detector result 'alerts' field must be a list")
            alerts = [a for a in raw_alerts if isinstance(a, dict)]
        else:
            raise TypeError("detector result must be a mapping containing an alerts list")

        if self.on_alert is not None:
            for alert in alerts:
                self.on_alert(alert)
        return alerts

    @staticmethod
    def _require_fields(
        data: Mapping[str, Any], required: tuple[str, ...], description: str
    ) -> None:
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(
                f"{description} is missing required field(s): {', '.join(missing)}"
            )
