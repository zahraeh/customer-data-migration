"""Field-level transforms applied to legacy values before they reach the target.

Every transform takes the raw string from the source file and returns the
cleaned value, or raises TransformError with a message written for the
customer (it ends up verbatim in the exceptions file they review).

Blank input returns None from every transform; whether a missing value is
acceptable is decided by the field's `required` flag, not here.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable, Dict, Optional

import phonenumbers


class TransformError(ValueError):
    pass


def _blank(value: Optional[str]) -> bool:
    return value is None or value.strip() == "" or value.strip().lower() in {"n/a", "na", "-", "null"}


# ── Text ─────────────────────────────────────────────────────────────────────

def strip(value):
    if _blank(value):
        return None
    return re.sub(r"\s+", " ", value).strip()


def upper(value):
    value = strip(value)
    return value.upper() if value else None


# ── Identifiers ──────────────────────────────────────────────────────────────

def siret(value):
    """French company identifier: 14 digits with a Luhn checksum."""
    if _blank(value):
        return None
    digits = re.sub(r"[\s.]", "", value)
    if not re.fullmatch(r"\d{14}", digits):
        raise TransformError(f"SIRET '{value}' must be 14 digits")
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    if total % 10 != 0:
        raise TransformError(f"SIRET '{value}' fails its checksum (likely a typo)")
    return digits


# ── Contact details ──────────────────────────────────────────────────────────

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$")


def email(value):
    if _blank(value):
        return None
    cleaned = value.strip().lower()
    if not _EMAIL.match(cleaned):
        raise TransformError(f"'{value}' is not a valid email address")
    return cleaned


def phone_basic(value):
    """Dry run 1 version: only accepts +33… or 0X XX XX XX XX with spaces."""
    if _blank(value):
        return None
    compact = value.replace(" ", "")
    if re.fullmatch(r"\+33\d{9}", compact):
        return compact
    if re.fullmatch(r"0\d{9}", compact):
        return "+33" + compact[1:]
    raise TransformError(f"Phone '{value}' is not in a recognised format")


def phone_fr(value):
    """Any French way of writing a number (dots, dashes, 0033, 33…) → E.164."""
    if _blank(value):
        return None
    candidate = value.strip()
    digits = re.sub(r"\D", "", candidate)
    if digits.startswith("33") and len(digits) == 11 and not candidate.startswith("+"):
        candidate = "+" + digits
    try:
        parsed = phonenumbers.parse(candidate, "FR")
    except phonenumbers.NumberParseException:
        raise TransformError(f"Phone '{value}' could not be parsed")
    if not phonenumbers.is_valid_number(parsed):
        raise TransformError(f"Phone '{value}' is not a valid French number")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


# ── Addresses ────────────────────────────────────────────────────────────────

def postcode_strict(value):
    """Dry run 1 version: exactly five digits, nothing else."""
    if _blank(value):
        return None
    cleaned = value.strip()
    if not re.fullmatch(r"\d{5}", cleaned):
        raise TransformError(f"Postcode '{value}' must be 5 digits")
    return cleaned


def postcode_fr(value):
    """Restores the leading zero Excel strips from departments 01–09."""
    if _blank(value):
        return None
    cleaned = value.strip()
    if re.fullmatch(r"\d{4}", cleaned):
        cleaned = "0" + cleaned
    if not re.fullmatch(r"\d{5}", cleaned):
        raise TransformError(f"Postcode '{value}' must be 5 digits")
    return cleaned


# ── Dates ────────────────────────────────────────────────────────────────────

_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")


def date_fr(value):
    """Day-first, always. 03/04/2021 is the 3rd of April, never March 4th."""
    if _blank(value):
        return None
    cleaned = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    raise TransformError(f"Date '{value}' is not a real calendar date (expected DD/MM/YYYY)")


# ── Money ────────────────────────────────────────────────────────────────────

def amount_naive(value):
    """Dry runs 1–2 version. Kept so the regression test can prove the bug.

    Treats every dot as a decimal point, so the legacy export's "2.400"
    (two thousand four hundred euros) silently becomes 2.40.
    """
    if _blank(value):
        return None
    cleaned = value.replace("€", "").replace(" ", "").replace(" ", "").replace(",", ".")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        raise TransformError(f"Amount '{value}' is not a number")


_THOUSANDS_DOT = re.compile(r"^\d{1,3}(\.\d{3})+$")


def amount_fr(value):
    """French number formatting: comma decimals, space or dot thousands."""
    if _blank(value):
        return None
    cleaned = value.replace("€", "").replace(" ", " ").strip().replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif _THOUSANDS_DOT.match(cleaned):
        cleaned = cleaned.replace(".", "")
    try:
        return round(float(cleaned), 2)
    except ValueError:
        raise TransformError(f"Amount '{value}' is not a number")


# ── Registry ─────────────────────────────────────────────────────────────────

REGISTRY: Dict[str, Callable[[Any], Any]] = {
    "strip": strip,
    "upper": upper,
    "siret": siret,
    "email": email,
    "phone_basic": phone_basic,
    "phone_fr": phone_fr,
    "postcode_strict": postcode_strict,
    "postcode_fr": postcode_fr,
    "date_fr": date_fr,
    "amount_naive": amount_naive,
    "amount_fr": amount_fr,
}


def value_map(mapping: Dict[str, str]) -> Callable[[Any], Any]:
    """Build a transform that translates legacy picklist values."""
    lookup = {k.strip().lower(): v for k, v in mapping.items()}

    def apply(value):
        if _blank(value):
            return None
        key = value.strip().lower()
        if key not in lookup:
            raise TransformError(f"'{value}' is not one of the agreed values: {', '.join(mapping)}")
        return lookup[key]

    return apply


def build(spec) -> Callable[[Any], Any]:
    """Turn a config entry (name or {map: {...}}) into a callable."""
    if isinstance(spec, str):
        if spec not in REGISTRY:
            raise KeyError(f"Unknown transform '{spec}'. Available: {', '.join(sorted(REGISTRY))}")
        return REGISTRY[spec]
    if isinstance(spec, dict) and "map" in spec:
        return value_map(spec["map"])
    raise KeyError(f"Unsupported transform spec: {spec!r}")


def chain(specs) -> Callable[[Any], Any]:
    funcs = [build(s) for s in specs]

    def apply(value):
        for f in funcs:
            value = f(value)
            if value is None:
                return None
        return value

    return apply
