import csv
import textwrap
from pathlib import Path

import pytest

ACCOUNT_HEADERS = ["N° client", "Raison sociale", "SIRET", "CP", "Ville", "Tél"]
CONTACT_HEADERS = ["N° contact", "N° client", "Nom", "Tél portable"]
CONTRACT_HEADERS = ["Réf contrat", "N° client", "Montant annuel HT", "Date début", "Statut"]

# 73282932000074 is a checksum-valid SIRET.
ACCOUNTS = [
    ["CL001", "Boulangerie Martin", "73282932000074", "1000", "Bourg-en-Bresse", "04 74 22 33 44"],
    ["CL002", "BOULANGERIE MARTIN SARL", "73282932000074", "01000", "Bourg-en-Bresse", ""],  # dup by SIRET
    ["CL003", "", "", "69003", "Lyon", "06 12 34 56 78"],                                      # no name → rejected
    ["CL004", "Dupont Jean", "", "69100", "Villeurbanne", "0612345678"],
    ["CL005", "Dupont Jean", "", "69100", "Villeurbanne", "06.98.76.54.32"],                  # possible dup
]
CONTACTS = [
    ["CT001", "CL001", "MARTIN", "06 11 22 33 44"],
    ["CT002", "CL002", "MARTIN", "33611223345"],   # attached to the duplicate → re-linked
    ["CT003", "CL003", "X", ""],                   # parent rejected → cascade
    ["CT004", "CL999", "GHOST", ""],               # parent never existed
    ["CT004", "CL004", "DUPONT", ""],              # duplicate legacy ID
]
CONTRACTS = [
    ["CTR-1", "CL001", "2.400", "01/02/2024", "Actif"],       # €2,400, not €2.40
    ["CTR-2", "CL002", "1 250,50", "15/03/2024", "Actif"],    # on the duplicate → re-linked
    ["CTR-3", "CL004", "189,90 €", "31/02/2024", "Actif"],    # impossible date → rejected, value on hold
    ["CTR-4", "CL005", "300", "01/01/2020", "Résilié"],       # out of scope
]
CONTROL_TOTAL = 2400 + 1250.50 + 189.90

CONFIG = """
project: test
version: {version}
entities:
  accounts:
    source: data/clients.csv
    key: "N° client"
    fields:
      name:     {{source: "Raison sociale", transforms: [strip], required: true}}
      siret:    {{source: "SIRET", transforms: [siret]}}
      postcode: {{source: "CP", transforms: [postcode_fr], required: true}}
      city:     {{source: "Ville", transforms: [strip]}}
      phone:    {{source: "Tél", transforms: [phone_fr]}}
    dedupe: {{strong_key: siret, review_keys: [name, postcode]}}
  contacts:
    source: data/contacts.csv
    key: "N° contact"
    parent: {{entity: accounts, source: "N° client", field: account_external_id}}
    fields:
      last_name: {{source: "Nom", transforms: [strip], required: true}}
      mobile:    {{source: "Tél portable", transforms: [phone_fr]}}
  contracts:
    source: data/contrats.csv
    key: "Réf contrat"
    parent: {{entity: accounts, source: "N° client", field: account_external_id}}
    fields:
      annual_value: {{source: "Montant annuel HT", transforms: [{amount}], required: true}}
      start_date:   {{source: "Date début", transforms: [date_fr], required: true}}
      status:
        source: "Statut"
        required: true
        transforms: [{{map: {{"Actif": active, "Résilié": terminated}}}}]
    scope: {{field: status, exclude: [terminated], reason: out of scope}}
control_totals:
  - {{entity: contracts, sum_field: annual_value, expected: {total}, provided_by: test}}
go_live:
  max_reject_rate: {max_reject}
"""


def _write_csv(path: Path, headers, rows):
    with path.open("w", encoding="cp1252", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(headers)
        w.writerows(rows)


@pytest.fixture
def project(tmp_path):
    """A tiny legacy export + config laid out like the real repo."""
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    _write_csv(tmp_path / "data" / "clients.csv", ACCOUNT_HEADERS, ACCOUNTS)
    _write_csv(tmp_path / "data" / "contacts.csv", CONTACT_HEADERS, CONTACTS)
    _write_csv(tmp_path / "data" / "contrats.csv", CONTRACT_HEADERS, CONTRACTS)

    def make_config(amount="amount_fr", max_reject=0.9, version="test"):
        path = tmp_path / "config" / f"{version}-{amount}.yaml"
        path.write_text(textwrap.dedent(CONFIG.format(
            amount=amount, total=CONTROL_TOTAL, max_reject=max_reject, version=version,
        )), encoding="utf-8")
        return path

    return make_config
