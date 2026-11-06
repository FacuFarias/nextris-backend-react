#!/usr/bin/env python3
"""Validación determinista del contrato de Hanging Protocols."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run import app  # Inicializa el blueprint y su configuración antes del módulo.
from apps.api.hanging_protocols import _validate_payload


def valid_payload():
    return {
        'name': 'DX frontal y lateral',
        'modality': 'DX',
        'layout': '1x2',
        'isActive': True,
        'viewportRules': [
            {'slot': 0, 'label': 'Frontal', 'match': {'modality': 'DX', 'viewPosition': ['AP', 'PA']}},
            {'slot': 1, 'label': 'Lateral', 'match': {'modality': 'DX', 'viewPosition': ['LAT', 'LL']}},
        ],
    }


class HangingProtocolValidationTest(unittest.TestCase):
    def test_normalizes_the_supported_contract(self):
        with app.app_context():
            result = _validate_payload(valid_payload())
        self.assertEqual(result['modality'], 'DX')
        self.assertEqual(result['layout'], '1x2')
        self.assertTrue(result['is_active'])
        self.assertEqual([rule['slot'] for rule in result['viewport_rules']], [0, 1])

    def test_rejects_wrong_slot_count(self):
        payload = valid_payload()
        payload['viewportRules'] = payload['viewportRules'][:1]
        with app.app_context(), self.assertRaisesRegex(ValueError, 'cantidad de viewports'):
            _validate_payload(payload)

    def test_rejects_mpr_for_non_cross_sectional_modality(self):
        payload = valid_payload()
        payload.update({'layout': 'mpr', 'viewportRules': [payload['viewportRules'][0]]})
        with app.app_context(), self.assertRaisesRegex(ValueError, 'MPR'):
            _validate_payload(payload)

    def test_rejects_unknown_fields_and_invalid_ranges(self):
        payload = valid_payload()
        payload['viewportRules'][0]['match']['unexpected'] = True
        with app.app_context(), self.assertRaisesRegex(ValueError, 'campos no admitidos'):
            _validate_payload(payload)
        payload = valid_payload()
        payload['viewportRules'][0]['match'].update({'seriesNumberMin': 10, 'seriesNumberMax': 2})
        with app.app_context(), self.assertRaisesRegex(ValueError, 'rango de serie'):
            _validate_payload(payload)


if __name__ == '__main__':
    unittest.main()
