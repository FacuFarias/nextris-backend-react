"""PACS storage monitoring: local cache disk (fs1), Backblaze B2 copies and growth.

Everything is read-only against the dcm4chee catalog (`public` schema). The only write is the
hourly disk snapshot in `nextris.tb_storage_snapshot`, the one figure the catalog cannot rebuild.
dcm4chee stores its timestamps as UTC without time zone.
"""
import datetime as dt
import os
import shutil
from zoneinfo import ZoneInfo

from apps.home.services.database_service import DatabaseService

GIB = 1024 ** 3
LOCAL_STORAGES = ('fs1', 'fs1-retrieve')
REMOTE_STORAGE = 'b2'
SNAPSHOT_RETENTION_DAYS = 400
WARNING_MARGIN = 10 * GIB
PENDING_WARNING_SECONDS = 3600
PENDING_CRITICAL_SECONDS = 6 * 3600


def storage_path():
    return os.getenv('NEXTRIS_PACS_STORAGE_PATH', '/var/local/dcm4chee-arc/storage')


def threshold_bytes():
    return int(float(os.getenv('NEXTRIS_PACS_FREE_THRESHOLD_GIB', '20')) * GIB)


def timezone():
    return ZoneInfo(os.getenv('NEXTRIS_TIMEZONE', 'America/Argentina/Buenos_Aires'))


def disk_status():
    usage = shutil.disk_usage(storage_path())
    threshold = threshold_bytes()
    return dict(path=storage_path(), total=usage.total, used=usage.used, free=usage.free,
                threshold=threshold, margin=usage.free - threshold)


def catalog_totals(cursor):
    """Bytes and objects with a valid (status 0) location, per storage."""
    cursor.execute("""SELECT storage_id, count(*), coalesce(sum(object_size),0)
        FROM public.location WHERE status=0 AND storage_id = ANY(%s) GROUP BY storage_id""",
                   (list(LOCAL_STORAGES) + [REMOTE_STORAGE],))
    found = {row[0]: dict(objects=int(row[1]), bytes=int(row[2])) for row in cursor.fetchall()}
    empty = dict(objects=0, bytes=0)
    return {storage: found.get(storage, dict(empty)) for storage in LOCAL_STORAGES + (REMOTE_STORAGE,)}


def pending_exports(cursor):
    """Local objects that have no valid B2 copy yet: they keep fs1 from being purged."""
    cursor.execute("""SELECT count(*), coalesce(sum(l.object_size),0),
            extract(epoch FROM (now() AT TIME ZONE 'UTC') - min(l.created_time))
        FROM public.location l
        WHERE l.status=0 AND l.storage_id = ANY(%s)
          AND NOT EXISTS (SELECT 1 FROM public.location b
              WHERE b.instance_fk=l.instance_fk AND b.storage_id=%s AND b.status=0
                AND b.object_type=l.object_type)""", (list(LOCAL_STORAGES), REMOTE_STORAGE))
    count, size, age = cursor.fetchone()
    return dict(objects=int(count), bytes=int(size), oldest_age_seconds=int(age) if age is not None else None)


# Per-study size: each instance counts once, with the largest of its valid copies (fs1 and b2
# hold the same object). Studies whose objects are all gone count as 0 bytes.
STUDY_SIZES = """
    WITH instance_size AS (
        SELECT se.study_fk, max(l.object_size) AS size
        FROM public.location l
        JOIN public.instance i ON i.pk=l.instance_fk
        JOIN public.series se ON se.pk=i.series_fk
        WHERE l.status=0 AND l.object_type=0
        GROUP BY l.instance_fk, se.study_fk
    )
    SELECT s.pk, s.created_time, coalesce(sum(x.size),0) AS size
    FROM public.study s LEFT JOIN instance_size x ON x.study_fk=s.pk
    {where}
    GROUP BY s.pk, s.created_time
"""


def _local_day_start(day, tz):
    """Local midnight of `day` as a naive UTC timestamp comparable to dcm4chee columns."""
    return dt.datetime.combine(day, dt.time(), tz).astimezone(dt.timezone.utc).replace(tzinfo=None)


def daily_series(cursor, days, today=None):
    tz = timezone()
    today = today or dt.datetime.now(tz).date()
    first = today - dt.timedelta(days=days - 1)
    cursor.execute("""SELECT ((created_time AT TIME ZONE 'UTC') AT TIME ZONE %s)::date AS day,
                             count(*), coalesce(sum(size),0)
        FROM (""" + STUDY_SIZES.format(where='WHERE s.created_time >= %s') + """) sizes
        GROUP BY 1""", (str(tz), _local_day_start(first, tz)))
    rows = {row[0]: (int(row[1]), int(row[2])) for row in cursor.fetchall()}
    cursor.execute("""SELECT count(*), coalesce(sum(size),0) FROM (""" +
                   STUDY_SIZES.format(where='WHERE s.created_time < %s') + """) sizes""",
                   (_local_day_start(first, tz),))
    studies_before, bytes_before = (int(value) for value in cursor.fetchone())
    series, total_studies, total_bytes = [], studies_before, bytes_before
    for offset in range(days):
        day = first + dt.timedelta(days=offset)
        studies, size = rows.get(day, (0, 0))
        total_studies += studies
        total_bytes += size
        series.append(dict(date=day.isoformat(), studies=studies, bytes=size,
                           cumulative_studies=total_studies, cumulative_bytes=total_bytes))
    return series


def study_size_stats(cursor, recent_days=30):
    tz = timezone()
    since = _local_day_start(dt.datetime.now(tz).date() - dt.timedelta(days=recent_days - 1), tz)
    cursor.execute("""SELECT count(*), coalesce(sum(size),0), coalesce(max(size),0),
            count(*) FILTER (WHERE created_time >= %s), coalesce(sum(size) FILTER (WHERE created_time >= %s),0)
        FROM (""" + STUDY_SIZES.format(where='') + """) sizes""", (since, since))
    count, size, largest, recent_count, recent_size = (int(value) for value in cursor.fetchone())
    return dict(studies=count, total_bytes=size, largest_bytes=largest,
                average_bytes=size // count if count else 0,
                recent_days=recent_days, recent_studies=recent_count, recent_bytes=recent_size,
                recent_average_bytes=recent_size // recent_count if recent_count else 0)


def projection(disk, series):
    """Daily intake over the series window; days until the purge threshold and a full disk.

    When the archive started inside the window, average only from its first day of studies."""
    had_earlier = bool(series) and series[0]['cumulative_studies'] > series[0]['studies']
    active = series if had_earlier else next(
        (series[i:] for i, item in enumerate(series) if item['studies']), series)
    series = active
    window = len(series) or 1
    per_day = sum(item['bytes'] for item in series) / window
    studies_per_day = sum(item['studies'] for item in series) / window

    def days_until(room):
        if room <= 0:
            return 0
        return round(room / per_day, 1) if per_day > 0 else None
    return dict(window_days=window, bytes_per_day=int(per_day), studies_per_day=round(studies_per_day, 2),
                days_to_threshold=days_until(disk['margin']), days_to_full=days_until(disk['free']))


def status_level(disk, pending):
    """green / yellow / red with the reasons, worst first."""
    reasons, level = [], 'green'
    age = pending['oldest_age_seconds'] or 0
    if disk['free'] < disk['threshold']:
        level = 'red'
        reasons.append('El espacio libre está por debajo del umbral: el PACS está retirando copias locales')
    elif disk['free'] < disk['threshold'] + WARNING_MARGIN:
        level = 'yellow'
        reasons.append('El espacio libre está cerca del umbral de purga')
    if pending['objects'] and age >= PENDING_CRITICAL_SECONDS:
        level = 'red'
        reasons.append('Hay imágenes sin copia en B2 desde hace más de 6 horas: no se pueden retirar de fs1')
    elif pending['objects'] and age >= PENDING_WARNING_SECONDS:
        level = 'yellow' if level == 'green' else level
        reasons.append('Hay imágenes esperando su copia a B2 desde hace más de una hora')
    return dict(level=level, reasons=reasons)


def overview(days=30):
    disk = disk_status()
    with DatabaseService.get_db_cursor() as (cursor, connection):
        totals = catalog_totals(cursor)
        pending = pending_exports(cursor)
        series = daily_series(cursor, days)
        sizes = study_size_stats(cursor)
        connection.rollback()
    today = series[-1]
    return dict(
        generated_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        disk=disk,
        local_cache=dict(fs1=totals['fs1'], retrieve=totals['fs1-retrieve'],
                         bytes=totals['fs1']['bytes'] + totals['fs1-retrieve']['bytes']),
        b2=dict(totals[REMOTE_STORAGE], source='catalog'),
        pending_b2=pending,
        today=dict(date=today['date'], studies=today['studies'], bytes=today['bytes']),
        study_size=sizes,
        projection=projection(disk, series),
        status=status_level(disk, pending),
    )


def history(days):
    tz = timezone()
    with DatabaseService.get_db_cursor() as (cursor, connection):
        series = daily_series(cursor, days)
        cursor.execute("""SELECT taken_at, disk_total, disk_free, local_bytes, b2_bytes, pending_b2_bytes
            FROM nextris.tb_storage_snapshot WHERE taken_at >= now() - %s * interval '1 day'
            ORDER BY taken_at""", (days,))
        snapshots = [dict(taken_at=row[0].astimezone(tz).isoformat(), disk_total=int(row[1]),
                          disk_free=int(row[2]), local_bytes=int(row[3]), b2_bytes=int(row[4]),
                          pending_b2_bytes=int(row[5])) for row in cursor.fetchall()]
        connection.rollback()
    return dict(days=days, daily=series, snapshots=snapshots, threshold=threshold_bytes())


def take_snapshot():
    disk = disk_status()
    with DatabaseService.get_db_cursor() as (cursor, connection):
        totals = catalog_totals(cursor)
        pending = pending_exports(cursor)
        cursor.execute("""INSERT INTO nextris.tb_storage_snapshot
            (disk_total, disk_free, local_bytes, b2_bytes, b2_objects, pending_b2_objects, pending_b2_bytes)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING taken_at""",
                       (disk['total'], disk['free'], totals['fs1']['bytes'] + totals['fs1-retrieve']['bytes'],
                        totals[REMOTE_STORAGE]['bytes'], totals[REMOTE_STORAGE]['objects'],
                        pending['objects'], pending['bytes']))
        taken_at = cursor.fetchone()[0]
        cursor.execute("DELETE FROM nextris.tb_storage_snapshot WHERE taken_at < now() - %s * interval '1 day'",
                       (SNAPSHOT_RETENTION_DAYS,))
        connection.commit()
    return taken_at
