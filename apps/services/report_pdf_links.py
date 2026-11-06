"""Short-lived signed URLs so browsers can open a report PDF with its real file name."""
from urllib.parse import quote
from flask import current_app
from itsdangerous import BadData, URLSafeTimedSerializer

MAX_AGE_SECONDS = 900


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'], salt='report-pdf-link')


def issue_link(exam_id, filename):
    """Call only after authorizing the current user for this exam. Returned path is relative to the API root."""
    return f"/report-files/{_serializer().dumps(str(exam_id))}/{quote(filename, safe='')}"


def resolve_link(token):
    try:
        return _serializer().loads(token, max_age=MAX_AGE_SECONDS)
    except BadData:
        return None
