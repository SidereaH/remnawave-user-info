import re

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def detect_query(text: str) -> tuple[str, str]:
    t = text.strip()
    if _EMAIL_RE.match(t):
        return "email", t
    if t.startswith("@"):
        return "username", t[1:].strip()
    if t.isdigit():
        return "telegram_id", t
    return "username", t
