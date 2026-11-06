#!/usr/bin/env python3
"""Focused integration checks for append-only examination notes."""

import os
import sys
import uuid

import psycopg2
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from apps.api.utils import get_db_config


BASE_URL = os.getenv("NEXTRIS_TEST_BASE_URL", "http://127.0.0.1:5001/api")
USERNAME = os.getenv("NEXTRIS_TEST_USERNAME", "sysadmin")
PASSWORD = os.getenv("NEXTRIS_TEST_PASSWORD", "1234")


def main():
    login = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD, "user_type": "staff"},
        timeout=15,
    )
    assert login.status_code == 200, login.text
    token = login.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    listing = requests.get(
        f"{BASE_URL}/examinations/for-reporting",
        params={
            "show_ready": "true",
            "show_reported": "true",
            "show_no_image": "true",
            "show_without_order": "true",
            "per_page": 1,
        },
        headers=headers,
        timeout=15,
    )
    assert listing.status_code == 200, listing.text
    studies = listing.json()["data"]["data"]
    if not studies:
        print("SKIP: no examination available")
        return

    exam_id = studies[0]["guid"]
    message = f"Nota de prueba {uuid.uuid4()}"
    note_id = None
    try:
        empty = requests.post(
            f"{BASE_URL}/examinations/{exam_id}/notes",
            json={"message": "   "},
            headers=headers,
            timeout=15,
        )
        assert empty.status_code == 400, empty.text

        created = requests.post(
            f"{BASE_URL}/examinations/{exam_id}/notes",
            json={
                "message": message,
                "author_username": "forged-author",
                "author_display_name": "Forged Author",
            },
            headers=headers,
            timeout=15,
        )
        assert created.status_code == 201, created.text
        note = created.json()["data"]
        note_id = note["id"]
        assert note["message"] == message
        assert note["author_username"] == USERNAME
        assert note["author_username"] != "forged-author"
        assert note["created_on"]

        history = requests.get(
            f"{BASE_URL}/examinations/{exam_id}/notes",
            headers=headers,
            timeout=15,
        )
        assert history.status_code == 200, history.text
        notes = history.json()["data"]["notes"]
        assert notes[0]["id"] == note_id
        assert notes[0]["message"] == message

        refreshed = requests.get(
            f"{BASE_URL}/examinations/for-reporting",
            params={
                "show_ready": "true",
                "show_reported": "true",
                "show_no_image": "true",
                "show_without_order": "true",
                "per_page": 1,
            },
            headers=headers,
            timeout=15,
        )
        assert refreshed.status_code == 200, refreshed.text
        recent_notes = refreshed.json()["data"]["data"][0]["recent_notes"]
        assert len(recent_notes) <= 3
        assert isinstance(refreshed.json()["data"]["data"][0]["notes_count"], int)

        deleted = requests.delete(
            f"{BASE_URL}/examinations/{exam_id}/notes/{note_id}",
            headers=headers,
            timeout=15,
        )
        assert deleted.status_code == 200, deleted.text
        note_id = None

        missing = requests.post(
            f"{BASE_URL}/examinations/00000000-0000-0000-0000-000000000000/notes",
            json={"message": "test"},
            headers=headers,
            timeout=15,
        )
        assert missing.status_code == 404, missing.text

        unauthenticated = requests.get(
            f"{BASE_URL}/examinations/{exam_id}/notes",
            timeout=15,
        )
        assert unauthenticated.status_code == 401, unauthenticated.text
        print("PASS: examination notes API")
    finally:
        if note_id:
            connection = psycopg2.connect(**get_db_config())
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM nextris.tbexaminationnote WHERE guid = %s",
                        (note_id,),
                    )
                connection.commit()
            finally:
                connection.close()


if __name__ == "__main__":
    main()
