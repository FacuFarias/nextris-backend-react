# -*- coding: utf-8 -*-
"""
Analytics API  —  /api/analytics/*
Requires Sysadmin role. All endpoints are read-only.
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity

from apps.api import api_blueprint
from apps.home.services.database_service import DatabaseService


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_sysadmin() -> bool:
    """Returns True if the current JWT user has the Sysadmin role."""
    try:
        identity = get_jwt_identity()
        user_id = identity if isinstance(identity, str) else (
            identity.get("id") or identity.get("guid") or identity.get("user_id")
        )
        if not user_id:
            return False
        row = DatabaseService.execute_query(
            """
            SELECT r.description
            FROM nextris.tbuser u
            JOIN nextris.isrole r ON r.guid = u.idrole
            WHERE u.guid = %s
            LIMIT 1
            """,
            (user_id,),
            fetch_one=True,
            fetch_all=False,
        )
        if not row:
            return False
        role_name = (row[0] or "").strip().lower()
        return role_name in ("sysadmin", "admin", "administrador")
    except Exception:
        return False


def _days_param(default: int = 7) -> int:
    d = request.args.get("days", default, type=int)
    return max(1, min(365, d))


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@api_blueprint.route("/analytics/summary", methods=["GET"])
@jwt_required()
def analytics_summary():
    """
    GET /api/analytics/summary?days=7
    Returns: unique users, sessions, top routes, top countries, avg duration.
    """
    if not _is_sysadmin():
        return jsonify({"success": False, "error": "No autorizado"}), 403

    days = _days_param(7)
    interval = f"{days} days"

    try:
        unique_users = DatabaseService.execute_query(
            "SELECT COUNT(DISTINCT user_id) FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s AND user_id IS NOT NULL",
            (interval,), fetch_one=True, fetch_all=False,
        )

        total_sessions = DatabaseService.execute_query(
            "SELECT COUNT(DISTINCT session_id) FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s AND session_id IS NOT NULL",
            (interval,), fetch_one=True, fetch_all=False,
        )

        total_requests = DatabaseService.execute_query(
            "SELECT COUNT(*) FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s",
            (interval,), fetch_one=True, fetch_all=False,
        )

        avg_duration = DatabaseService.execute_query(
            "SELECT ROUND(AVG(duration_ms)) FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s AND duration_ms IS NOT NULL AND duration_ms > 0",
            (interval,), fetch_one=True, fetch_all=False,
        )

        top_routes = DatabaseService.execute_query(
            "SELECT route, COUNT(*) AS hits FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s AND route IS NOT NULL "
            "GROUP BY route ORDER BY hits DESC LIMIT 10",
            (interval,),
        )

        top_countries = DatabaseService.execute_query(
            "SELECT country, COUNT(*) AS hits FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s AND country IS NOT NULL AND country <> '' "
            "GROUP BY country ORDER BY hits DESC LIMIT 10",
            (interval,),
        )

        daily_activity = DatabaseService.execute_query(
            "SELECT DATE(created_at) AS day, COUNT(*) AS hits "
            "FROM nextris.tb_analytics_events "
            "WHERE created_at >= NOW() - INTERVAL %s "
            "GROUP BY day ORDER BY day ASC",
            (interval,),
        )

        return jsonify({
            "success": True,
            "data": {
                "period_days": days,
                "unique_users": unique_users[0] if unique_users else 0,
                "total_sessions": total_sessions[0] if total_sessions else 0,
                "total_requests": total_requests[0] if total_requests else 0,
                "avg_duration_ms": int(avg_duration[0]) if avg_duration and avg_duration[0] else 0,
                "top_routes": [{"route": r[0], "hits": r[1]} for r in (top_routes or [])],
                "top_countries": [{"country": c[0], "hits": c[1]} for c in (top_countries or [])],
                "daily_activity": [
                    {"day": str(d[0]), "hits": d[1]} for d in (daily_activity or [])
                ],
            },
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_blueprint.route("/analytics/events", methods=["GET"])
@jwt_required()
def analytics_events():
    """
    GET /api/analytics/events?days=1&user_id=...&event_type=...&page=1&limit=50
    Paginated list of raw events.
    """
    if not _is_sysadmin():
        return jsonify({"success": False, "error": "No autorizado"}), 403

    days    = _days_param(1)
    user_id = request.args.get("user_id")
    ev_type = request.args.get("event_type")
    page    = max(1, request.args.get("page", 1, type=int))
    limit   = min(200, max(1, request.args.get("limit", 50, type=int)))
    offset  = (page - 1) * limit

    interval = f"{days} days"
    conditions = ["created_at >= NOW() - INTERVAL %s"]
    params: list = [interval]

    if user_id:
        conditions.append("user_id = %s")
        params.append(user_id)
    if ev_type:
        conditions.append("event_type = %s")
        params.append(ev_type)

    where = " AND ".join(conditions)

    try:
        rows = DatabaseService.execute_query(
            f"""
            SELECT id, event_id, user_id, session_id, facility_id,
                   event_type, route, http_method, http_status,
                   duration_ms, ip_address, country, city, user_agent,
                   extra_data, created_at
            FROM nextris.tb_analytics_events
            WHERE {where}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )

        events = [
            {
                "id": r[0],
                "event_id": str(r[1]) if r[1] else None,
                "user_id": r[2],
                "session_id": r[3],
                "facility_id": r[4],
                "event_type": r[5],
                "route": r[6],
                "http_method": r[7],
                "http_status": r[8],
                "duration_ms": r[9],
                "ip_address": r[10],
                "country": r[11],
                "city": r[12],
                "user_agent": r[13],
                "extra_data": r[14],
                "created_at": r[15].isoformat() if r[15] else None,
            }
            for r in (rows or [])
        ]

        return jsonify({"success": True, "data": events, "page": page, "limit": limit})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_blueprint.route("/analytics/sessions", methods=["GET"])
@jwt_required()
def analytics_sessions():
    """
    GET /api/analytics/sessions?days=1
    Session-level aggregation: start time, last seen, request count, location.
    """
    if not _is_sysadmin():
        return jsonify({"success": False, "error": "No autorizado"}), 403

    days = _days_param(1)
    interval = f"{days} days"

    try:
        rows = DatabaseService.execute_query(
            """
            SELECT
                session_id,
                user_id,
                facility_id,
                MIN(created_at)  AS session_start,
                MAX(created_at)  AS last_seen,
                COUNT(*)         AS request_count,
                MAX(ip_address)  AS ip_address,
                MAX(country)     AS country,
                MAX(city)        AS city
            FROM nextris.tb_analytics_events
            WHERE created_at >= NOW() - INTERVAL %s
              AND session_id IS NOT NULL
            GROUP BY session_id, user_id, facility_id
            ORDER BY last_seen DESC
            LIMIT 200
            """,
            (interval,),
        )

        sessions = [
            {
                "session_id": r[0],
                "user_id": r[1],
                "facility_id": r[2],
                "session_start": r[3].isoformat() if r[3] else None,
                "last_seen": r[4].isoformat() if r[4] else None,
                "request_count": r[5],
                "ip_address": r[6],
                "country": r[7],
                "city": r[8],
            }
            for r in (rows or [])
        ]

        return jsonify({"success": True, "data": sessions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@api_blueprint.route("/analytics/users", methods=["GET"])
@jwt_required()
def analytics_users():
    """
    GET /api/analytics/users?days=7
    Per-user activity: request count, session count, last seen, last IP, country.
    """
    if not _is_sysadmin():
        return jsonify({"success": False, "error": "No autorizado"}), 403

    days = _days_param(7)
    interval = f"{days} days"

    try:
        rows = DatabaseService.execute_query(
            """
            SELECT
                ae.user_id,
                u.username,
                u.name,
                u.surname,
                COUNT(*)                       AS request_count,
                COUNT(DISTINCT ae.session_id)  AS session_count,
                MAX(ae.created_at)             AS last_seen,
                MAX(ae.ip_address)             AS last_ip,
                MAX(ae.country)                AS country
            FROM nextris.tb_analytics_events ae
            LEFT JOIN nextris.tbuser u ON u.guid = ae.user_id
            WHERE ae.created_at >= NOW() - INTERVAL %s
              AND ae.user_id IS NOT NULL
            GROUP BY ae.user_id, u.username, u.name, u.surname
            ORDER BY last_seen DESC
            LIMIT 200
            """,
            (interval,),
        )

        users = [
            {
                "user_id": r[0],
                "username": r[1],
                "name": r[2],
                "surname": r[3],
                "request_count": r[4],
                "session_count": r[5],
                "last_seen": r[6].isoformat() if r[6] else None,
                "last_ip": r[7],
                "country": r[8],
            }
            for r in (rows or [])
        ]

        return jsonify({"success": True, "data": users})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
