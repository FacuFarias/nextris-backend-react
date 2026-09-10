from apps.services.report_fields import (
    canonical_fields_from_row,
    fields_are_complete,
    merge_template_study_reason,
    normalize_report_payload,
)


def test_legacy_report_is_consolidated_in_documented_order():
    fields = canonical_fields_from_row(
        None, None, None,
        legacy_technique='<p>T</p>',
        legacy_findings='<p>H</p>',
        legacy_impressions='<p>I</p>',
        legacy_conclusion='C',
        reason_fallback='Motivo',
    )
    assert fields['study_reason'] == 'Motivo'
    assert fields['content'].index('Técnica de examen') < fields['content'].index('Hallazgos') < fields['content'].index('Impresiones')
    assert fields['conclusion'] == 'C'


def test_explicit_canonical_empty_values_do_not_reactivate_legacy():
    fields = canonical_fields_from_row(
        '', '', '', legacy_technique='old', legacy_findings='old',
        legacy_impressions='old', legacy_conclusion='old', reason_fallback='reason',
    )
    assert fields == {'study_reason': '', 'content': '', 'conclusion': ''}


def test_mixed_payload_gives_canonical_fields_precedence():
    fields = normalize_report_payload({
        'study_reason': 'R', 'content': 'C', 'findings': 'legacy',
        'conclusions': 'old conclusion', 'conclusion': 'K',
    })
    assert fields == {'study_reason': 'R', 'content': 'C', 'conclusion': 'K'}
    assert fields_are_complete(fields)


def test_examination_reason_fills_template_motive_without_replacing_sections():
    template = (
        '<p><strong>Técnica de examen:</strong></p>'
        '<p><strong>Motivo del estudio: </strong>[[ ]]</p>'
        '<p><strong>Técnica: </strong>Secuencias habituales.</p>'
        '<p><strong>Comparación: </strong>[[No disponible.]]</p>'
    )
    examination_reason = (
        'Razón del estudio: Pie plano bilateral | '
        'Doctor Referente: FRITZLER, GUILLERMO'
    )

    merged = merge_template_study_reason(template, examination_reason)

    assert '<strong>Técnica de examen:</strong>' in merged
    assert '[[Pie plano bilateral | Doctor Referente: FRITZLER, GUILLERMO]]' in merged
    assert '[[Razón del estudio:' not in merged
    assert '<strong>Técnica: </strong>Secuencias habituales.' in merged
    assert '<strong>Comparación: </strong>[[No disponible.]]' in merged


def test_examination_reason_is_html_escaped_inside_single_brackets():
    template = '<p><strong>Motivo del estudio:</strong> [pendiente]</p>'

    merged = merge_template_study_reason(template, 'Dolor < 3 días & edema')

    assert '[Dolor &lt; 3 días &amp; edema]' in merged


def test_existing_template_motive_is_replaced_by_bracketed_examination_reason():
    template = (
        '<p><strong>Motivo del estudio: </strong>Dolor de tobillo.</p>'
        '<p><strong>Técnica: </strong>Secuencias multiplanares.</p>'
    )

    merged = merge_template_study_reason(template, 'Pie plano bilateral')

    assert '<strong>Motivo del estudio: </strong> [[Pie plano bilateral]]</p>' in merged
    assert 'Dolor de tobillo.' not in merged
    assert '<strong>Técnica: </strong>Secuencias multiplanares.' in merged


def test_missing_motive_section_is_added_without_losing_template_text():
    template = '<p><strong>Técnica:</strong> RM sin contraste.</p>'

    merged = merge_template_study_reason(template, 'Dolor de tobillo')

    assert merged.startswith(
        '<p><strong>Motivo del estudio: </strong>[[Dolor de tobillo]]</p>'
    )
    assert template in merged


def test_empty_examination_reason_leaves_template_placeholder_unchanged():
    template = '<p><strong>Motivo del estudio:</strong> [[ ]]</p>'

    assert merge_template_study_reason(template, '') == template
