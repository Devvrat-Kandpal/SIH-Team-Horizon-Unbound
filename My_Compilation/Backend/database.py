"""
Backend/database.py — Project ARJUNA (SIH 26170)
High-reliability persistence adapter supporting production Supabase PostgreSQL
and resilient offline in-memory fallback queues per ECSS-Q-ST-60-02C.
Supports both direct PostgREST HTTP client (httpx/requests) and official supabase client.
"""

from __future__ import annotations

import logging
import os
from collections import deque
from threading import Lock
from typing import Any

logger = logging.getLogger("project_arjuna.database")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    load_dotenv = None

try:
    import httpx
except ImportError:
    httpx = None

try:
    from supabase import Client, create_client  # type: ignore[import-not-found]
except ImportError:
    Client = Any
    create_client = None


def normalize_supabase_url(raw_url: str) -> str:
    """Normalizes dashboard URLs or bare project IDs into standard API endpoints."""
    url = raw_url.strip().rstrip("/")
    if not url:
        return ""
    if "dashboard/project/" in url:
        proj_ref = url.split("dashboard/project/")[-1].split("/")[0].split("?")[0]
        return f"https://{proj_ref}.supabase.co"
    if not url.startswith("http://") and not url.startswith("https://"):
        return f"https://{url}.supabase.co"
    return url


class TelemetryStore:
    """Production Supabase persistence with non-blocking offline in-memory fallback."""

    def __init__(self, history_limit: int = 2000, events_limit: int = 500) -> None:
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._events: deque[dict[str, Any]] = deque(maxlen=events_limit)
        self._lock = Lock()
        self.client: Any = None
        self.http_client = None
        self.enabled: bool = os.getenv("SUPABASE_ENABLED", "false").lower() == "true"

        raw_url = os.getenv("SUPABASE_URL", "").strip()
        self.url: str = normalize_supabase_url(raw_url)
        self.key: str = os.getenv("SUPABASE_KEY", "").strip()

        self.total_inserted_telemetry: int = 0
        self.total_inserted_events: int = 0
        self.last_error: str | None = None

        if self.enabled and self.url and self.key:
            # 1. Try official supabase client if installed
            if create_client:
                try:
                    self.client = create_client(self.url, self.key)
                    logger.info(
                        "Supabase client initialized successfully for: %s", self.url
                    )
                except Exception as e:
                    self.client = None
                    self.last_error = str(e)

            # 2. Also initialize direct httpx PostgREST client for high-throughput resilience
            if httpx:
                try:
                    self.http_client = httpx.Client(
                        headers={
                            "apikey": self.key,
                            "Authorization": f"Bearer {self.key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        },
                        timeout=4.0,
                    )
                    logger.info(
                        "Supabase PostgREST HTTP client active for: %s", self.url
                    )
                except Exception as he:
                    self.http_client = None
                    logger.warning("HTTP client init failed: %s", he)

    @property
    def available(self) -> bool:
        """True if Supabase client or PostgREST HTTP client is operational."""
        return (self.client is not None or self.http_client is not None) and bool(
            self.url and self.key
        )

    def get_status(self) -> dict[str, Any]:
        """Returns persistence status view."""
        return {
            "supabase_enabled": self.enabled,
            "supabase_available": self.available,
            "supabase_url": self.url[:28] + "..." if len(self.url) > 28 else self.url,
            "in_memory_records": len(self._history),
            "in_memory_events": len(self._events),
            "total_telemetry_logged": self.total_inserted_telemetry,
            "total_events_logged": self.total_inserted_events,
            "last_error": self.last_error,
        }

    @staticmethod
    def _format_telemetry_payload(telemetry: dict[str, Any]) -> dict[str, Any]:
        """Formats telemetry to strictly match migrations/supabase_schema.sql."""
        iddq_val = float(
            telemetry.get(
                "iddq_uA", telemetry.get("iddq_ua", telemetry.get("iddq", 10.0))
            )
        )
        return {
            "timestamp": telemetry.get("timestamp"),
            "voltage": float(telemetry.get("voltage", 5.0)),
            "current": float(telemetry.get("current", 1.20)),
            "temperature": float(telemetry.get("temperature", 125.0)),
            "iddq_uA": iddq_val,
            "prop_delay": float(telemetry.get("prop_delay", 4.50)),
            "anomaly_score": float(telemetry.get("anomaly_score", 0.032)),
            "isolation_anomaly": bool(
                telemetry.get("is_anomaly", telemetry.get("isolation_anomaly", False))
            ),
            "drift_anomaly": bool(
                telemetry.get(
                    "cusum_drift_detected", telemetry.get("drift_anomaly", False)
                )
            ),
            "fault_type": str(telemetry.get("fault_type", "NORMAL")),
            "criticality_level": int(telemetry.get("criticality_level", 2)),
            "system_status": str(telemetry.get("system_status", "NOMINAL")),
        }

    def record_telemetry(self, telemetry: dict[str, Any]) -> None:
        """Records a single telemetry frame to Supabase or local deque."""
        payload = self._format_telemetry_payload(telemetry)
        with self._lock:
            self._history.append(dict(telemetry))
            self.total_inserted_telemetry += 1

        if self.http_client and self.url:
            try:
                # PostgreSQL unquoted identifiers are lowercase in PostgREST schema cache
                http_payload = dict(payload)
                if "iddq_uA" in http_payload:
                    http_payload["iddq_ua"] = http_payload.pop("iddq_uA")

                res = self.http_client.post(
                    f"{self.url}/rest/v1/telemetry_logs", json=http_payload
                )
                if res.status_code in (200, 201):
                    return
                # Fallback: if database preserved exact case iddq_uA
                if "iddq_ua" in res.text:
                    self.http_client.post(
                        f"{self.url}/rest/v1/telemetry_logs", json=payload
                    )
            except Exception as exc:
                self.last_error = f"Insert error: {exc}"
                logger.debug("PostgREST insert failed; local deque preserved: %s", exc)
        elif self.client:
            try:
                self.client.table("telemetry_logs").insert(payload).execute()
            except Exception as exc:
                self.last_error = f"Insert error: {exc}"
                logger.debug(
                    "Supabase client insert failed; local deque preserved: %s", exc
                )

    def record_event(
        self, event_type: str, severity: str, message: str, criticality_level: int = 2
    ) -> None:
        """Records a system or audit event."""
        event_dict = {
            "event_type": str(event_type),
            "severity": str(severity),
            "message": str(message),
            "criticality_level": int(criticality_level),
        }
        with self._lock:
            self._events.append(event_dict)
            self.total_inserted_events += 1

        if self.http_client and self.url:
            try:
                self.http_client.post(
                    f"{self.url}/rest/v1/system_events", json=event_dict
                )
            except Exception as exc:
                self.last_error = f"Event error: {exc}"
        elif self.client:
            try:
                self.client.table("system_events").insert(event_dict).execute()
            except Exception as exc:
                self.last_error = f"Event error: {exc}"

    def recent(
        self, limit: int = 100, fault_type: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves recent telemetry with optional fault_type filtering.
        Queries Supabase if active, otherwise reads from local synchronized buffer.
        """
        limit = max(1, min(int(limit), 1000))

        if self.http_client and self.url:
            try:
                query_url = f"{self.url}/rest/v1/telemetry_logs?select=*&order=timestamp.desc&limit={limit}"
                if fault_type and fault_type != "ALL":
                    query_url += f"&fault_type=eq.{fault_type.upper()}"
                res = self.http_client.get(query_url)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception as exc:
                self.last_error = f"Query error: {exc}"
        elif self.client:
            try:
                query = (
                    self.client.table("telemetry_logs")
                    .select("*")
                    .order("timestamp", desc=True)
                )
                if fault_type and fault_type != "ALL":
                    query = query.eq("fault_type", fault_type.upper())
                res = query.limit(limit).execute()
                if res.data:
                    return res.data
            except Exception as exc:
                self.last_error = f"Query error: {exc}"

        with self._lock:
            records = list(self._history)
            if fault_type and fault_type != "ALL":
                records = [
                    r for r in records if r.get("fault_type") == fault_type.upper()
                ]
            return list(reversed(records[-limit:]))

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieves recent audit events."""
        limit = max(1, min(int(limit), 200))
        if self.http_client and self.url:
            try:
                res = self.http_client.get(
                    f"{self.url}/rest/v1/system_events?select=*&order=created_at.desc&limit={limit}"
                )
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 0:
                        return data
            except Exception:
                pass
        elif self.client:
            try:
                res = (
                    self.client.table("system_events")
                    .select("*")
                    .order("created_at", desc=True)
                    .limit(limit)
                    .execute()
                )
                if res.data:
                    return res.data
            except Exception:
                pass

        with self._lock:
            return list(reversed(list(self._events)[-limit:]))


telemetry_store = TelemetryStore()

# Team-compatible exports
insert_telemetry = telemetry_store.record_telemetry
log_event = telemetry_store.record_event
get_recent_telemetry = telemetry_store.recent
