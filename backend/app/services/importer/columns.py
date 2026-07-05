"""
Canonical column names for import files and their accepted aliases.

Users may label columns differently across CSV/XLSX/DOCX tables.
The normaliser maps every alias → canonical name so the rest of the
import pipeline only ever deals with one name per field.

Required fields (one row cannot be imported without these):
  first_name, last_name, person_type, job_title, department, email

Optional:
  middle_name, phone, floor, start_date, company_name, nfc_uid
"""

from typing import Optional

# canonical → list of accepted aliases (all lowercased, stripped)
COLUMN_ALIASES: dict[str, list[str]] = {
    "first_name":   ["first name", "firstname", "given name", "forename", "first"],
    "last_name":    ["last name", "lastname", "surname", "family name", "last"],
    "middle_name":  ["middle name", "middlename", "middle"],
    "email":        ["email", "email address", "e-mail", "work email"],
    "phone":        ["phone", "telephone", "mobile", "phone number", "tel"],
    "person_type":  ["type", "person type", "staff type", "employment type", "category"],
    "job_title":    ["job title", "title", "position", "role", "designation"],
    "department":   ["department", "dept", "team", "division", "group"],
    "floor":        ["floor", "level", "building floor"],
    "start_date":   ["start date", "start", "date started", "commencement date", "hire date"],
    "company_name": ["company", "company name", "employer", "organisation", "organization", "contractor company"],
    "nfc_uid":      ["nfc uid", "nfc", "card uid", "rfid uid", "card id", "rfid"],
}

# Build reverse map: alias → canonical
_ALIAS_MAP: dict[str, str] = {}
for _canonical, _aliases in COLUMN_ALIASES.items():
    _ALIAS_MAP[_canonical] = _canonical   # canonical maps to itself
    for _alias in _aliases:
        _ALIAS_MAP[_alias] = _canonical

REQUIRED_COLUMNS = {"first_name", "last_name", "person_type", "job_title", "department", "email"}


def normalise_header(raw: str) -> Optional[str]:
    """Map a raw column header string to a canonical name, or None if unknown."""
    return _ALIAS_MAP.get(raw.strip().lower())


def normalise_row(raw_row: dict) -> dict:
    """
    Convert a dict keyed by raw headers to one keyed by canonical names.
    Unknown columns are dropped. Duplicate canonical names: last value wins.
    """
    result = {}
    for key, value in raw_row.items():
        canonical = normalise_header(key)
        if canonical is not None:
            result[canonical] = value.strip() if isinstance(value, str) else value
    return result


PERSON_TYPE_MAP = {
    "employee":     "employee",
    "emp":          "employee",
    "staff":        "employee",
    "permanent":    "employee",
    "contractor":   "contractor",
    "contract":     "contractor",
    "ctr":          "contractor",
    "temp":         "contractor",
    "temporary":    "contractor",
    "freelance":    "contractor",
}


def normalise_person_type(raw: str) -> Optional[str]:
    return PERSON_TYPE_MAP.get(raw.strip().lower())
