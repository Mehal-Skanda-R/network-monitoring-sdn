"""Wire format for host telemetry datagrams.

One UDP datagram = one UTF-8 JSON object with exactly these fields:

    {"host": "h1", "timestamp": 1792842000.0, "bytes_sent": 9600, "packets_sent": 120}

This matches the agreed input of NetworkDetector.process_telemetry().
Unknown extra fields are ignored (dropped) so the format can grow safely.
"""

import json
import math

MAX_DATAGRAM = 1024  # bytes; real messages are ~100 bytes
MAX_HOST_LEN = 64

FIELDS = ("host", "timestamp", "bytes_sent", "packets_sent")


class ProtocolError(ValueError):
    """Raised when a datagram cannot be decoded or fails validation."""


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate(msg):
    """Return a clean dict with only the four agreed fields, or raise ProtocolError."""
    if not isinstance(msg, dict):
        raise ProtocolError("message must be a JSON object")
    missing = [f for f in FIELDS if f not in msg]
    if missing:
        raise ProtocolError("missing field(s): " + ", ".join(missing))

    host = msg["host"]
    if not isinstance(host, str) or not host.strip():
        raise ProtocolError("host must be a non-empty string")
    if len(host) > MAX_HOST_LEN:
        raise ProtocolError("host too long")
    if not _is_number(msg["timestamp"]) or msg["timestamp"] < 0:
        raise ProtocolError("timestamp must be a finite non-negative number")
    for name in ("bytes_sent", "packets_sent"):
        if not _is_int(msg[name]) or msg[name] < 0:
            raise ProtocolError(name + " must be a non-negative integer")

    return {f: msg[f] for f in FIELDS}


def encode(msg):
    """Validate and serialise a telemetry dict to bytes."""
    data = json.dumps(validate(msg), separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_DATAGRAM:
        raise ProtocolError("encoded message exceeds MAX_DATAGRAM")
    return data


def decode(data):
    """Parse and validate one datagram. Raises ProtocolError on any problem."""
    if len(data) > MAX_DATAGRAM:
        raise ProtocolError("datagram too large")
    try:
        obj = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("not valid UTF-8 JSON: %s" % exc)
    return validate(obj)
