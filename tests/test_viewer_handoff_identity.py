#!/usr/bin/env python3
"""Checks that viewer handoff storage supports both identity namespaces."""

import unittest
import os

import psycopg2


@unittest.skipUnless(os.getenv('NEXTRIS_GENERAL_TESTS') == '1', 'Explicit disposable database required')
class ViewerHandoffIdentityTest(unittest.TestCase):
    def test_handoff_table_has_no_single_tbuser_foreign_key(self):
        connection = psycopg2.connect(
            host=os.environ['DB_HOST'], port=os.environ['DB_PORT'], dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'], password=os.environ['DB_PASS']
        )
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT 1
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = 'nextris'
                      AND t.relname = 'tb_viewer_handoff'
                      AND c.conname = 'tb_viewer_handoff_user_id_fkey'
                """)
                self.assertIsNone(cursor.fetchone())
        finally:
            connection.close()


if __name__ == '__main__':
    unittest.main()
