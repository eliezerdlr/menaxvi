"""Append-only, redacted, hash-chained JSONL evidence log."""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "passwd",
    "password",
    "private_key",
    "secret",
    "session",
    "token",
    "api_key",
}
_SENSITIVE_SUFFIXES = tuple(f"_{key}" for key in _SENSITIVE_KEYS - {"authorization"})


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith(_SENSITIVE_SUFFIXES)


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evidence timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def redact(value: Any, *, key: str | None = None) -> Any:
    """Return deterministic JSON-compatible evidence with sensitive values removed."""
    if key is not None and _is_sensitive_key(key):
        return _REDACTED
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bytes):
        return {"type": "bytes", "sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
    if isinstance(value, Mapping):
        return {
            str(item_key): redact(item_value, key=str(item_key))
            for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [redact(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True, ensure_ascii=False))
    return {"type": type(value).__name__}


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class EvidenceEvent:
    sequence: int
    timestamp: str
    execution_id: str
    event_type: str
    data: dict[str, Any]
    previous_hash: str | None
    event_hash: str


@dataclass(frozen=True)
class EvidenceVerification:
    valid: bool
    event_count: int
    error: str | None = None


class EvidenceLog:
    """Write one complete JSON event per line and link events by SHA-256.

    The log fails closed on malformed existing content. A process-local lock and
    append mode prevent interleaving between threads. Deployments with multiple
    writer processes must provide a single-writer service or an external lock.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def append(self, execution_id: str, event_type: str, data: Mapping[str, Any]) -> EvidenceEvent:
        if not execution_id.strip():
            raise ValueError("execution_id must not be empty")
        if not event_type.strip():
            raise ValueError("event_type must not be empty")

        with self._lock:
            verification = self.verify()
            if not verification.valid:
                raise ValueError(f"existing evidence log is invalid: {verification.error}")
            previous = self._read_last_event()
            body = {
                "sequence": verification.event_count + 1,
                "timestamp": _timestamp(self._clock()),
                "execution_id": execution_id,
                "event_type": event_type,
                "data": redact(dict(data)),
                "previous_hash": previous.event_hash if previous else None,
            }
            event_hash = hashlib.sha256(_canonical(body)).hexdigest()
            payload = {**body, "event_hash": event_hash}
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
            descriptor = os.open(self.path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                encoded = line.encode("utf-8")
                written = 0
                while written < len(encoded):
                    count = os.write(descriptor, encoded[written:])
                    if count == 0:
                        raise OSError("evidence log write made no progress")
                    written += count
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return EvidenceEvent(**payload)

    def events(self) -> tuple[EvidenceEvent, ...]:
        if not self.path.exists():
            return ()
        result: list[EvidenceEvent] = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.endswith("\n"):
                    raise ValueError(f"line {line_number} is incomplete")
                try:
                    payload = json.loads(line)
                    result.append(EvidenceEvent(**payload))
                except (json.JSONDecodeError, TypeError) as error:
                    raise ValueError(f"line {line_number} is malformed: {error}") from error
        return tuple(result)

    def verify(self) -> EvidenceVerification:
        try:
            events = self.events()
        except ValueError as error:
            return EvidenceVerification(False, 0, str(error))

        previous_hash: str | None = None
        for expected_sequence, event in enumerate(events, 1):
            if event.sequence != expected_sequence:
                return EvidenceVerification(
                    False, expected_sequence - 1, f"event {expected_sequence} has invalid sequence"
                )
            if event.previous_hash != previous_hash:
                return EvidenceVerification(
                    False, expected_sequence - 1, f"event {expected_sequence} breaks the hash chain"
                )
            body = asdict(event)
            recorded_hash = body.pop("event_hash")
            calculated_hash = hashlib.sha256(_canonical(body)).hexdigest()
            if recorded_hash != calculated_hash:
                return EvidenceVerification(
                    False, expected_sequence - 1, f"event {expected_sequence} hash does not match"
                )
            previous_hash = recorded_hash
        return EvidenceVerification(True, len(events))

    def _read_last_event(self) -> EvidenceEvent | None:
        events = self.events()
        return events[-1] if events else None
