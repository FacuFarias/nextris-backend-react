# -*- encoding: utf-8 -*-
"""Utilidades para manejar fechas de citas de forma consistente.

Las columnas historicas de agenda son ``timestamp without time zone``. En
NextRIS esos valores se almacenan como UTC naive; la zona se agrega solo al
leer o escribir datos.
"""

from datetime import datetime

import pytz


DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
UTC = pytz.UTC


def get_timezone(timezone_name=None):
    """Devuelve una zona valida, usando Argentina como fallback."""
    try:
        return pytz.timezone(timezone_name or DEFAULT_TIMEZONE)
    except pytz.exceptions.UnknownTimeZoneError:
        return pytz.timezone(DEFAULT_TIMEZONE)


def to_utc_naive(value, timezone_name=DEFAULT_TIMEZONE):
    """Convierte una fecha local o ISO con offset a UTC sin tzinfo.

    Los strings sin offset representan hora de la ubicacion. Los strings con
    ``Z`` u offset representan un instante absoluto y no se vuelven a ajustar.
    """
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))

    if parsed.tzinfo is None:
        parsed = get_timezone(timezone_name).localize(parsed)

    return parsed.astimezone(UTC).replace(tzinfo=None)


def from_utc_naive(value, timezone_name=DEFAULT_TIMEZONE):
    """Convierte un UTC naive almacenado a datetime de la ubicacion."""
    if value is None:
        return None

    if value.tzinfo is None:
        value = UTC.localize(value)

    return value.astimezone(get_timezone(timezone_name))


def format_local_datetime(value, timezone_name=DEFAULT_TIMEZONE, separator="T"):
    """Formatea un datetime almacenado como UTC en hora local sin offset."""
    local_value = from_utc_naive(value, timezone_name)
    return local_value.strftime(f"%Y-%m-%d{separator}%H:%M:%S")
