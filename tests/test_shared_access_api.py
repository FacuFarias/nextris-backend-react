#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de integración no destructivas para accesos externos compartidos.

Uso:
    python3 tests/test_shared_access_api.py

El backend debe estar disponible en ``SHARED_ACCESS_API_URL`` o en
``http://127.0.0.1:5001/api``.
"""

import os
from datetime import datetime, timedelta, timezone

import requests


BASE_URL = os.getenv("SHARED_ACCESS_API_URL", "http://127.0.0.1:5001/api")
USERNAME = os.getenv("SHARED_ACCESS_TEST_USER", "sysadmin")
PASSWORD = os.getenv("SHARED_ACCESS_TEST_PASSWORD", "1234")


def login():
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD, "user_type": "staff"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    assert payload.get("success")
    return {"Authorization": f"Bearer {payload['data']['access_token']}"}


def test_lists_are_separated(headers):
    for link_type in ("case_link", "image_share"):
        response = requests.get(
            f"{BASE_URL}/general/shared-access-links",
            headers=headers,
            params={"type": link_type, "status": "all", "page": 1, "per_page": 2},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()["data"]
        assert isinstance(data["items"], list)
        assert all(item["type"] == link_type for item in data["items"])
        assert {"created_at", "expires_at", "revoked_at", "open_count", "status"} <= set(data["items"][0]) if data["items"] else True


def test_invalid_type_is_rejected(headers):
    response = requests.get(
        f"{BASE_URL}/general/shared-access-links",
        headers=headers,
        params={"type": "invalid"},
        timeout=15,
    )
    assert response.status_code == 400


def test_expiration_must_be_future(headers):
    response = requests.patch(
        f"{BASE_URL}/general/shared-access-links/not-found",
        headers=headers,
        json={"expires_at": datetime.now(timezone.utc).isoformat()},
        timeout=15,
    )
    assert response.status_code == 400


def test_missing_link_actions_are_not_found(headers):
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    extend_response = requests.patch(
        f"{BASE_URL}/general/shared-access-links/not-found",
        headers=headers,
        json={"expires_at": future},
        timeout=15,
    )
    revoke_response = requests.post(
        f"{BASE_URL}/general/shared-access-links/not-found/revoke",
        headers=headers,
        timeout=15,
    )
    assert extend_response.status_code == 404
    assert revoke_response.status_code == 404


def main():
    headers = login()
    tests = [test_lists_are_separated, test_invalid_type_is_rejected, test_expiration_must_be_future, test_missing_link_actions_are_not_found]
    for test in tests:
        test(headers)
        print(f"PASS: {test.__name__}")


if __name__ == "__main__":
    main()
