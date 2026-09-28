import pytest

from migrate import transforms as t
from migrate.transforms import TransformError


@pytest.mark.parametrize("raw", [
    "06 12 34 56 78", "0612345678", "06.12.34.56.78", "+33 6 12 34 56 78", "33612345678", "06-12-34-56-78",
])
def test_phone_fr_normalises_every_french_format_to_e164(raw):
    assert t.phone_fr(raw) == "+33612345678"


def test_phone_fr_rejects_truncated_number():
    with pytest.raises(TransformError):
        t.phone_fr("06 12 34 56")


def test_phone_basic_misses_dotted_numbers():
    # Why dry run 1 lost phone numbers: only two patterns were accepted.
    with pytest.raises(TransformError):
        t.phone_basic("06.12.34.56.78")


def test_postcode_fr_restores_leading_zero_removed_by_excel():
    assert t.postcode_fr("1000") == "01000"
    assert t.postcode_fr("69003") == "69003"


def test_postcode_strict_rejects_four_digits():
    with pytest.raises(TransformError):
        t.postcode_strict("1000")


@pytest.mark.parametrize("raw,expected", [
    ("2.400", 2400.0),
    ("12.500", 12500.0),
    ("1 250,50", 1250.50),
    ("1 250,50", 1250.50),
    ("189,90 €", 189.90),
    ("1250.5", 1250.5),
    ("450", 450.0),
])
def test_amount_fr(raw, expected):
    assert t.amount_fr(raw) == expected


def test_amount_naive_silently_reads_thousands_dot_as_decimal():
    # The dry run 2 incident, pinned: no error, just the wrong number.
    assert t.amount_naive("2.400") == 2.40


def test_date_fr_is_day_first():
    assert t.date_fr("03/04/2021") == "2021-04-03"
    assert t.date_fr("03/04/21") == "2021-04-03"
    assert t.date_fr("2021-04-03") == "2021-04-03"


@pytest.mark.parametrize("raw", ["31/02/2023", "00/01/2022", "2021/04/03"])
def test_date_fr_rejects_impossible_or_unknown_dates(raw):
    with pytest.raises(TransformError):
        t.date_fr(raw)


def test_siret_checksum():
    assert t.siret("732 829 320 00074") == "73282932000074"
    with pytest.raises(TransformError, match="checksum"):
        t.siret("73282932000075")


@pytest.mark.parametrize("raw", ["jean@@gmail.com", "jean@gmail", "jean gmail.com"])
def test_email_rejects_malformed(raw):
    with pytest.raises(TransformError):
        t.email(raw)


def test_blank_placeholders_become_none():
    for raw in ["", "   ", "n/a", "N/A", "-"]:
        assert t.email(raw) is None


def test_value_map_rejects_unknown_picklist_values():
    status = t.value_map({"Actif": "active"})
    assert status(" actif ") == "active"
    with pytest.raises(TransformError, match="agreed values"):
        status("En pause")
