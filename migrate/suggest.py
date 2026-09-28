"""Draft a column mapping for a new legacy export.

Two modes:
  - heuristic (default, offline): header synonyms + value shape sniffing
  - --ai: Claude reads the headers and a few sample values per column

Either way the output is a *draft* with a confidence and a reason for every
suggestion. A consultant reviews it and the customer confirms it; nothing
here writes a config that is used without a human reading it first.

Privacy: in --ai mode only headers and up to 5 sample values per column are
sent, and --mask replaces letters/digits in samples with a/9 so the model
sees the format but not the customer's data.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional

from . import source as source_io
from .profile import shape

# What the target platform expects, per entity. Descriptions are what a
# consultant would read in the vendor's import documentation.
TARGET_SCHEMA: Dict[str, Dict[str, str]] = {
    "accounts": {
        "external_id": "Legacy system's unique ID for the customer account",
        "name": "Company or household name",
        "siret": "French company registration number (14 digits)",
        "address": "Street address",
        "postcode": "5-digit French postcode",
        "city": "City",
        "phone": "Main phone number",
        "email": "Main email address",
        "created_on": "Date the customer was created in the legacy system",
        "owner": "Sales rep who owns the account",
    },
    "contacts": {
        "external_id": "Legacy system's unique ID for the contact",
        "account_external_id": "Legacy ID of the account this contact belongs to",
        "first_name": "First name",
        "last_name": "Last name",
        "job_title": "Role or job title",
        "mobile": "Mobile phone number",
        "email": "Email address",
    },
    "contracts": {
        "external_id": "Legacy contract reference",
        "account_external_id": "Legacy ID of the account holding the contract",
        "type": "Contract type / service level",
        "annual_value": "Annual contract value excluding VAT, in euros",
        "start_date": "Contract start date",
        "end_date": "Contract end / renewal date",
        "status": "Contract status (active, suspended, terminated…)",
    },
}

SYNONYMS: Dict[str, List[str]] = {
    "name": ["raison sociale", "nom client", "societe", "company", "client"],
    "siret": ["siret", "siren", "n siret"],
    "address": ["adresse", "rue", "address"],
    "postcode": ["cp", "code postal", "postal", "zip"],
    "city": ["ville", "commune", "city"],
    "phone": ["tel", "telephone", "phone", "fixe"],
    "mobile": ["portable", "mobile", "gsm", "tel portable"],
    "email": ["email", "e mail", "mail", "courriel"],
    "created_on": ["date creation", "cree le", "created"],
    "owner": ["commercial", "responsable", "owner", "vendeur"],
    "first_name": ["prenom", "first name"],
    "last_name": ["nom", "last name", "surname"],
    "job_title": ["fonction", "poste", "titre", "role"],
    "type": ["type", "formule", "offre"],
    "annual_value": ["montant", "montant annuel", "prix", "ca", "valeur"],
    "start_date": ["date debut", "debut", "start"],
    "end_date": ["date fin", "fin", "echeance", "end"],
    "status": ["statut", "etat", "status"],
    "external_id": ["n client", "id", "ref", "reference", "code client", "n contact", "ref contrat"],
    "account_external_id": ["n client", "client id", "code client"],
}


@dataclass
class Suggestion:
    target: str
    source: Optional[str]
    confidence: str  # high | medium | low | none
    reason: str
    transforms: List[str]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _default_transforms(target: str) -> List[str]:
    return {
        "siret": ["siret"], "postcode": ["postcode_fr"], "phone": ["phone_fr"], "mobile": ["phone_fr"],
        "email": ["email"], "created_on": ["date_fr"], "start_date": ["date_fr"], "end_date": ["date_fr"],
        "annual_value": ["amount_fr"],
    }.get(target, ["strip"])


def heuristic(entity: str, headers: List[str], samples: Dict[str, List[str]]) -> List[Suggestion]:
    out = []
    used = set()
    for target in TARGET_SCHEMA[entity]:
        best, conf, why = None, "none", "no header or value pattern matched"
        for h in headers:
            if h in used:
                continue
            nh = _norm(h)
            for syn in SYNONYMS.get(target, []):
                if nh == syn:
                    best, conf, why = h, "high", f"header '{h}' is a known name for {target}"
                    break
                if syn in nh and conf not in ("high",):
                    best, conf, why = h, "medium", f"header '{h}' contains '{syn}'"
            if conf == "high":
                break
        if conf in ("none", "medium") and target in ("email", "phone", "mobile", "postcode"):
            for h in headers:
                if h in used:
                    continue
                vals = [v for v in samples.get(h, []) if v.strip()]
                if not vals:
                    continue
                if target == "email" and all("@" in v for v in vals):
                    best, conf, why = h, "medium", "sample values look like email addresses"
                elif target == "postcode" and all(re.fullmatch(r"\d{4,5}", v.strip()) for v in vals):
                    best, conf, why = h, "medium", "sample values are 4–5 digit codes (4 = lost leading zero?)"
        if best:
            used.add(best)
        out.append(Suggestion(target, best, conf, why, _default_transforms(target)))
    return out


_AI_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "source": {"type": ["string", "null"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low", "none"]},
                    "reason": {"type": "string"},
                    "transforms": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["target", "source", "confidence", "reason", "transforms"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["mappings"],
    "additionalProperties": False,
}

_TRANSFORMS_HELP = (
    "strip, upper, siret, email, phone_fr (any French phone format → E.164), postcode_fr (restores "
    "leading zero), date_fr (day-first dates), amount_fr (French number format, comma decimals, "
    "dot or space thousands)"
)


def ai(entity: str, headers: List[str], samples: Dict[str, List[str]]) -> List[Suggestion]:
    import anthropic  # optional dependency, only needed for --ai

    columns = "\n".join(f"- {h!r}: samples {samples.get(h, [])}" for h in headers)
    targets = "\n".join(f"- {k}: {v}" for k, v in TARGET_SCHEMA[entity].items())
    prompt = (
        f"You are helping an implementation consultant map a legacy CSV export onto a new platform's "
        f"'{entity}' import.\n\nLegacy columns, with sample values:\n{columns}\n\n"
        f"Target fields:\n{targets}\n\n"
        f"For every target field, pick the best legacy column or null if none fits. Each legacy column "
        f"can be used at most once. Choose transforms from: {_TRANSFORMS_HELP}. "
        f"In 'reason', point out anything in the samples the consultant should raise with the customer "
        f"(mixed formats, ambiguous values, lost leading zeros). Say 'low' when you are guessing."
    )

    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model="claude-opus-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"format": {"type": "json_schema", "schema": _AI_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude declined the request; use the heuristic mode instead")
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    valid_targets = set(TARGET_SCHEMA[entity])
    return [
        Suggestion(m["target"], m["source"] if m["source"] in headers else None,
                   m["confidence"], m["reason"], m["transforms"])
        for m in data["mappings"] if m["target"] in valid_targets
    ]


def collect_samples(src: source_io.SourceFile, k: int = 5, mask: bool = False) -> Dict[str, List[str]]:
    samples = {}
    for h in src.headers:
        vals = []
        for r in src.rows:
            v = (r.get(h) or "").strip()
            if v and v not in vals:
                vals.append(shape(v) if mask else v)
            if len(vals) == k:
                break
        samples[h] = vals
    return samples


def to_yaml(entity: str, source_path: str, suggestions: List[Suggestion]) -> str:
    lines = [
        f"# DRAFT mapping for {entity}: review every line before using it.",
        f"# Generated from {source_path}",
        f"{entity}:",
        f"  source: {source_path}",
    ]
    key = next((s for s in suggestions if s.target == "external_id"), None)
    lines.append(f"  key: \"{key.source if key and key.source else 'TODO'}\"")
    lines.append("  fields:")
    for s in suggestions:
        if s.target == "external_id":
            continue
        lines.append(f"    # [{s.confidence}] {s.reason}")
        src = f"\"{s.source}\"" if s.source else "TODO  # no match found, ask the customer"
        lines.append(f"    {s.target}: {{source: {src}, transforms: {json.dumps(s.transforms)}}}")
    return "\n".join(lines) + "\n"
