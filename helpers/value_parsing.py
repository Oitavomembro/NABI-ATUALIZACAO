from datetime import datetime


def parse_flexible_number(value):
    if not value:
        return 0.0
    text = str(value).strip()
    if "." in text and "," in text:
        text = text.replace(".", "")
    return float(text.replace(",", "."))


def parse_system_date(value):
    text = str(value or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_date_br(value):
    text = str(value or "").strip()
    if not text:
        return "-"
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text
