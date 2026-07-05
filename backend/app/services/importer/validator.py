"""
Row-level validation for imported person records.

Returns a list of RowResult objects — one per source row.
Valid rows carry a cleaned dict; invalid rows carry an error list.
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from .columns import REQUIRED_COLUMNS, normalise_person_type

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[+\d\s\-().]{7,20}$")
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y"]


@dataclass
class RowResult:
    row_number: int
    raw: dict
    cleaned: Optional[dict] = None
    errors: list = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


def validate_rows(normalised_rows: list[dict]) -> list[RowResult]:
    """Validate a list of normalised-column dicts. Returns one RowResult per row."""
    results = []
    for i, row in enumerate(normalised_rows, start=2):  # row 2 = first data row (1 = header)
        results.append(_validate_row(i, row))
    return results


def _validate_row(row_number: int, row: dict) -> RowResult:
    errors = []
    cleaned = {}

    # ── Required fields ────────────────────────────────────────────────────────
    for col in REQUIRED_COLUMNS:
        val = row.get(col, "").strip() if isinstance(row.get(col), str) else ""
        if not val:
            errors.append(f"Missing required field: {col}")
        else:
            cleaned[col] = val

    if errors:
        return RowResult(row_number=row_number, raw=row, errors=errors)

    # ── person_type ────────────────────────────────────────────────────────────
    pt = normalise_person_type(cleaned.get("person_type", ""))
    if pt is None:
        errors.append(
            f"person_type '{cleaned.get('person_type')}' is not recognised. "
            "Use 'employee' or 'contractor'."
        )
    else:
        cleaned["person_type"] = pt

    # ── email ──────────────────────────────────────────────────────────────────
    email = cleaned.get("email", "")
    if email and not EMAIL_RE.match(email):
        errors.append(f"email '{email}' does not look valid.")
    else:
        cleaned["email"] = email.lower()

    # ── phone (optional) ──────────────────────────────────────────────────────
    phone = row.get("phone", "").strip() if row.get("phone") else ""
    if phone:
        if not PHONE_RE.match(phone):
            errors.append(f"phone '{phone}' contains unexpected characters.")
        else:
            cleaned["phone"] = phone

    # ── start_date (optional, defaults to today) ───────────────────────────────
    raw_date = row.get("start_date", "").strip() if row.get("start_date") else ""
    if raw_date:
        parsed = _parse_date(raw_date)
        if parsed is None:
            errors.append(f"start_date '{raw_date}' could not be parsed. Try YYYY-MM-DD.")
        else:
            cleaned["start_date"] = parsed
    else:
        cleaned["start_date"] = date.today()

    # ── Optional string fields ─────────────────────────────────────────────────
    for col in ("middle_name", "floor", "company_name", "nfc_uid"):
        val = row.get(col, "").strip() if row.get(col) else ""
        if val:
            cleaned[col] = val

    # ── contractor must have company_name ──────────────────────────────────────
    if cleaned.get("person_type") == "contractor" and not cleaned.get("company_name"):
        errors.append("Contractors must have a company_name.")

    if errors:
        return RowResult(row_number=row_number, raw=row, errors=errors)
    return RowResult(row_number=row_number, raw=row, cleaned=cleaned)


def _parse_date(raw: str) -> Optional[date]:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None
