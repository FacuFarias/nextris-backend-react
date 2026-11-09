#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de Gestión → Almacenamiento.

Uso:
    python3 tests/test_storage_monitor.py

Las reglas del semáforo y la proyección se prueban siempre, sin servidor.
Si ``STORAGE_API_URL`` está definido (p. ej. http://127.0.0.1:5002/api), se prueban además los
endpoints de solo lectura con ``STORAGE_TEST_USER``/``STORAGE_TEST_PASSWORD`` (administrador) y,
si se indican, ``STORAGE_DENIED_USER``/``STORAGE_DENIED_PASSWORD`` (personal sin storage.view).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from apps.services import storage_monitor as sm  # noqa: E402

GIB = sm.GIB


def disk(free, threshold=20 * GIB, total=100 * GIB):
    return dict(total=total, used=total - free, free=free, threshold=threshold, margin=free - threshold)


def pending(objects=0, age=None):
    return dict(objects=objects, bytes=objects * 1000, oldest_age_seconds=age)


def day(studies, size, cumulative_studies):
    return dict(date='x', studies=studies, bytes=size, cumulative_studies=cumulative_studies, cumulative_bytes=0)


def test_status_levels():
    assert sm.status_level(disk(50 * GIB), pending())['level'] == 'green'
    assert sm.status_level(disk(25 * GIB), pending())['level'] == 'yellow'
    assert sm.status_level(disk(19 * GIB), pending())['level'] == 'red'
    assert sm.status_level(disk(50 * GIB), pending(3, 1800))['level'] == 'green'
    assert sm.status_level(disk(50 * GIB), pending(3, 2 * 3600))['level'] == 'yellow'
    assert sm.status_level(disk(50 * GIB), pending(3, 7 * 3600))['level'] == 'red'
    red = sm.status_level(disk(19 * GIB), pending(3, 2 * 3600))
    assert red['level'] == 'red' and len(red['reasons']) == 2


def test_projection():
    series = [day(0, 0, 0), day(0, 0, 0), day(2, 2 * GIB, 2), day(0, 0, 2)]
    result = sm.projection(disk(30 * GIB), series)
    assert result['window_days'] == 2  # archive started inside the window
    assert result['bytes_per_day'] == GIB
    assert result['days_to_threshold'] == 10.0 and result['days_to_full'] == 30.0
    earlier = [day(0, 0, 5), day(2, 2 * GIB, 7)]
    assert sm.projection(disk(30 * GIB), earlier)['window_days'] == 2
    assert sm.projection(disk(30 * GIB), [day(0, 0, 0)])['days_to_threshold'] is None
    assert sm.projection(disk(10 * GIB), series)['days_to_threshold'] == 0


def api_tests(base):
    import requests

    def login(user, password):
        response = requests.post(f'{base}/auth/login', timeout=15,
                                 json=dict(username=user, password=password, user_type='staff'))
        response.raise_for_status()
        return {'Authorization': 'Bearer ' + response.json()['data']['access_token']}

    assert requests.get(f'{base}/storage/overview', timeout=15).status_code == 401
    headers = login(os.environ['STORAGE_TEST_USER'], os.environ['STORAGE_TEST_PASSWORD'])
    response = requests.get(f'{base}/storage/overview', headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()['data']
    assert {'disk', 'local_cache', 'b2', 'pending_b2', 'today', 'study_size', 'projection', 'status'} <= set(data)
    usage = shutil.disk_usage(data['disk']['path'])
    assert abs(usage.total - data['disk']['total']) < GIB
    assert data['status']['level'] in ('green', 'yellow', 'red')
    response = requests.get(f'{base}/storage/history', params={'days': 90}, headers=headers, timeout=15)
    response.raise_for_status()
    history = response.json()['data']
    assert history['days'] == 90 and len(history['daily']) == 90
    assert history['daily'][-1]['cumulative_studies'] >= data['today']['studies']
    if os.getenv('STORAGE_DENIED_USER'):
        denied = login(os.environ['STORAGE_DENIED_USER'], os.environ['STORAGE_DENIED_PASSWORD'])
        assert requests.get(f'{base}/storage/overview', headers=denied, timeout=15).status_code == 403


if __name__ == '__main__':
    test_status_levels()
    test_projection()
    print('Reglas: OK')
    if os.getenv('STORAGE_API_URL'):
        api_tests(os.environ['STORAGE_API_URL'].rstrip('/'))
        print('API: OK')
