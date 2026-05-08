# -*- coding: utf-8 -*-
"""
Analytics service: geo-IP lookup with in-memory cache + DB write helper.
All public functions fail silently — they must never raise exceptions that
would interrupt a request.
"""

import time
import threading
from typing import Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Geo-IP lookup (ip-api.com free tier, 45 req/min, no key needed)
# Results are cached for 1 hour per IP to avoid rate-limit issues.
# ─────────────────────────────────────────────────────────────────────────────

_GEO_CACHE: dict = {}
_GEO_CACHE_TTL = 3600  # seconds
_GEO_LOCK = threading.Lock()


def _geo_lookup_http(ip: str) -> Tuple[str, str]:
    """Returns (country, city). Never raises."""
    try:
        import requests as req
        resp = req.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,country,city"},
            timeout=2,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return data.get("country", ""), data.get("city", "")
    except Exception:
        pass
    return "", ""


def get_geo_info(ip: Optional[str]) -> Tuple[str, str]:
    """
    Returns (country, city) for an IP address.
    Uses a TTL cache. Returns ("", "") on any failure.
    """
    if not ip or ip in ("127.0.0.1", "::1", "localhost", ""):
        return "Local", ""

    now = time.monotonic()
    with _GEO_LOCK:
        cached = _GEO_CACHE.get(ip)
        if cached and (now - cached["ts"]) < _GEO_CACHE_TTL:
            return cached["data"]

    country, city = _geo_lookup_http(ip)

    with _GEO_LOCK:
        _GEO_CACHE[ip] = {"ts": now, "data": (country, city)}

    return country, city


def evict_old_geo_cache() -> None:
    """Optional periodic cleanup of expired cache entries."""
    now = time.monotonic()
    with _GEO_LOCK:
        expired = [k for k, v in _GEO_CACHE.items() if (now - v["ts"]) >= _GEO_CACHE_TTL]
        for k in expired:
            del _GEO_CACHE[k]


# ─────────────────────────────────────────────────────────────────────────────
# DB write
# ─────────────────────────────────────────────────────────────────────────────

def record_event(
    *,
    event_type: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    route: Optional[str] = None,
    http_method: Optional[str] = None,
    http_status: Optional[int] = None,
    duration_ms: Optional[int] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    extra_data: Optional[dict] = None,
    run_geo_async: bool = True,
) -> Optional[int]:
    """
    Inserts an analytics event row.  Returns the new row id, or None on error.
    Geo-lookup is performed in a background thread to avoid blocking the request.
    """
    try:
        from apps.home.services.database_service import DatabaseService
        import json as _json

        row = DatabaseService.execute_query(
            """
            INSERT INTO nextris.tb_analytics_events
                (event_type, user_id, session_id, facility_id,
                 route, http_method, http_status, duration_ms,
                 ip_address, user_agent, extra_data, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
            """,
            (
                event_type,
                user_id,
                session_id,
                facility_id,
                route,
                http_method,
                http_status,
                duration_ms,
                ip_address,
                (user_agent or "")[:500],
                _json.dumps(extra_data) if extra_data else None,
            ),
            fetch_one=True,
            fetch_all=False,
            commit=True,
        )

        event_id: Optional[int] = row[0] if row else None

        if event_id and ip_address and run_geo_async:
            _start_geo_update(event_id, ip_address)

        return event_id
    except Exception:
        return None


def _geo_update_worker(event_id: int, ip: str) -> None:
    """Background thread: resolve geo and update the row."""
    try:
        country, city = get_geo_info(ip)
        if not country:
            return
        from apps.home.services.database_service import DatabaseService
        DatabaseService.execute_query(
            "UPDATE nextris.tb_analytics_events SET country=%s, city=%s WHERE id=%s",
            (country, city, event_id),
            commit=True,
        )
    except Exception:
        pass


def _start_geo_update(event_id: int, ip: str) -> None:
    t = threading.Thread(target=_geo_update_worker, args=(event_id, ip), daemon=True)
    t.start()
