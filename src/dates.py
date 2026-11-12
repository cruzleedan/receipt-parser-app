"""WORK-0008: date normalisation, free of third-party imports so bench/ can use it."""
def normalise_date(value) -> "str | None":
    """
    WORK-0008: turn a date as printed into YYYY-MM-DD, or None.

    Year-first dates (2024-07-26, 2024/7/26) are kept. Otherwise the first number is the
    month, as on Philippine receipts (07/26/24, 07-26-2024), unless it cannot be a month
    (26/07/2024), in which case day and month swap. Two-digit years are 20YY.
    Written-out months (Jul 26, 2024 / 26 Jul 2024) are read too.
    """
    import re
    from datetime import date as _date

    if not isinstance(value, str) or not value.strip():
        return None
    s = value.strip()
    months = {m: i for i, m in enumerate(
        ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}

    def build(y, m, d):
        try:
            return _date(y, m, d).isoformat()
        except ValueError:
            return None

    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        return build(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), int(m[3])
        y += 2000 if len(m[3]) == 2 else 0
        return build(y, a, b) if a <= 12 else build(y, b, a)
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{2,4})", s)
    if m and m[1].lower() in months:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return build(y, months[m[1].lower()], int(m[2]))
    m = re.search(r"(\d{1,2})\s*([A-Za-z]{3})[a-z]*\.?,?\s*(\d{2,4})", s)
    if m and m[2].lower() in months:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        return build(y, months[m[2].lower()], int(m[1]))
    return None

