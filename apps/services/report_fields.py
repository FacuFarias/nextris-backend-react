"""Canonical report field handling.

The application now stores report body text in three fields.  The historical
columns are deliberately kept in the database and are only consulted when a
row has not been migrated to the canonical shape.  This module is shared by
the REST APIs, legacy routes, integrations and PDF renderer so that every
consumer applies the same compatibility rules.
"""

from __future__ import annotations

from html import escape as html_escape, unescape
import re
from typing import Any, Mapping


_STUDY_MOTIVE_LABEL_RE = re.compile(
    r"(?is)(?:motivo|raz[oó]n)\s+(?:del\s+)?estudio\s*:"
)
_EXAMINATION_REASON_PREFIX_RE = re.compile(
    r"(?is)^\s*raz[oó]n\s+(?:del\s+)?estudio\s*:\s*"
)
_BRACKET_FIELD_RE = re.compile(r"\[\[([^\]]*)\]\]|\[([^\[\]]*)\]")


def _value(value: Any) -> str:
    return "" if value is None else str(value)


def has_value(value: Any) -> bool:
    """Return whether a rich/text field contains meaningful content."""
    text = _value(value)
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>|</div\s*>|</li\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text).replace("\u200b", "")
    return bool(text.strip() or re.search(r"<img\b|data-(?:variable|criterion)-chip", _value(value), re.I))


def merge_template_study_reason(template_reason: Any, examination_reason: Any) -> str:
    """Place the examination reason in the template's motive bracket.

    Report templates commonly keep technique, motive and comparison together in
    ``study_reason``. The order's clinical text must fill the motive field, not
    replace that complete template section.
    """
    template = _value(template_reason)
    reason = _EXAMINATION_REASON_PREFIX_RE.sub(
        "",
        _value(examination_reason).strip(),
        count=1,
    ).strip()

    if not reason:
        return template
    if not has_value(template):
        return f"<p><strong>Motivo del estudio: </strong>[[{html_escape(reason)}]]</p>"

    escaped_reason = html_escape(reason)
    label_match = _STUDY_MOTIVE_LABEL_RE.search(template)
    if not label_match:
        return (
            f"<p><strong>Motivo del estudio: </strong>[[{escaped_reason}]]</p>"
            f"{template}"
        )

    # Only inspect the label's paragraph/line. This prevents accidentally
    # filling a bracket that belongs to Técnica or Comparación.
    paragraph_end = template.find("</p>", label_match.end())
    newline_end = template.find("\n", label_match.end())
    candidate_ends = [end for end in (paragraph_end, newline_end) if end >= 0]
    section_end = min(candidate_ends) if candidate_ends else len(template)
    placeholder = _BRACKET_FIELD_RE.search(template, label_match.end(), section_end)

    if placeholder:
        opening = "[[" if placeholder.group(1) is not None else "["
        closing = "]]" if placeholder.group(1) is not None else "]"
        replacement = f"{opening}{escaped_reason}{closing}"
        return template[:placeholder.start()] + replacement + template[placeholder.end():]

    value_start = label_match.end()
    closing_strong = re.match(r"(?is)\s*</strong\s*>", template[value_start:section_end])
    if closing_strong:
        value_start += closing_strong.end()

    return template[:value_start] + f" [[{escaped_reason}]]" + template[section_end:]


def merge_legacy_content(
    technique: Any = None,
    findings: Any = None,
    impressions: Any = None,
    narrative: Any = None,
) -> str:
    """Combine historical sections without losing their semantic labels."""
    sections = (
        ("Técnica de examen", technique),
        ("Narrativa", narrative),
        ("Hallazgos", findings),
        ("Impresiones", impressions),
    )
    chunks: list[str] = []
    for title, raw in sections:
        if not has_value(raw):
            continue
        value = _value(raw).strip()
        chunks.append(f"<p><strong>{title}:</strong></p>{value}")
    return "<p></p>".join(chunks)


def canonical_fields_from_row(
    study_reason: Any,
    content: Any,
    conclusion: Any,
    *,
    legacy_technique: Any = None,
    legacy_findings: Any = None,
    legacy_impressions: Any = None,
    legacy_conclusion: Any = None,
    reason_fallback: Any = None,
) -> dict[str, str]:
    """Resolve one DB row, using legacy values only for an unmigrated row."""
    canonical_present = any(value is not None for value in (study_reason, content, conclusion))
    if canonical_present:
        return {
            "study_reason": _value(study_reason),
            "content": _value(content),
            "conclusion": _value(conclusion),
        }

    return {
        "study_reason": _value(reason_fallback),
        "content": merge_legacy_content(
            legacy_technique,
            legacy_findings,
            legacy_impressions,
        ),
        "conclusion": _value(legacy_conclusion),
    }


def legacy_aliases(fields: Mapping[str, Any]) -> dict[str, str]:
    """Expose deprecated response names without exposing legacy DB contents."""
    content = _value(fields.get("content"))
    conclusion = _value(fields.get("conclusion"))
    return {
        "findings": content,
        "techniques": "",
        "impressions": "",
        "conclusions": conclusion,
    }


def normalize_report_payload(
    data: Mapping[str, Any],
    *,
    reason_fallback: Any = None,
) -> dict[str, Any]:
    """Normalize new, legacy or mixed request bodies.

    Canonical keys win independently.  A legacy body is merged into one
    ``content`` value; omitted legacy keys are treated as empty sections.
    """
    payload: dict[str, Any] = {}
    if "study_reason" in data:
        payload["study_reason"] = _value(data.get("study_reason"))
    elif "reason" in data:
        payload["study_reason"] = _value(data.get("reason"))
    elif reason_fallback is not None:
        payload["study_reason"] = _value(reason_fallback)

    if "content" in data:
        payload["content"] = _value(data.get("content"))
    elif any(key in data for key in ("technique", "techniques", "narrative", "findings", "impression", "impressions")):
        payload["content"] = merge_legacy_content(
            data.get("technique", data.get("techniques")),
            data.get("narrative"),
            data.get("findings"),
            data.get("impression", data.get("impressions")),
        )

    if "conclusion" in data:
        payload["conclusion"] = _value(data.get("conclusion"))
    elif "conclusions" in data:
        payload["conclusion"] = _value(data.get("conclusions"))

    return payload


def fields_are_complete(fields: Mapping[str, Any]) -> bool:
    """Signing/import validation shared by modern and legacy report routes."""
    return all(has_value(fields.get(key)) for key in ("study_reason", "content", "conclusion"))
