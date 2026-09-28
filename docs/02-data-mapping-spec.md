# 02 · Data mapping specification

Final version (v3). The executable form of this document is [config/v3.yaml](../config/v3.yaml); the two must never disagree.

## Source files as received

Profile: [reports/source_profile.md](../reports/source_profile.md), generated with `python -m migrate profile data/source/*.csv`.

| File | Rows | Encoding | Delimiter | Notes |
|---|---:|---|---|---|
| clients.csv | 485 | Windows-1252 | `;` | 145 postcodes have 4 digits (Excel dropped the leading 0) |
| contacts.csv | 670 | Windows-1252 | `;` | 5+ phone formats in one column |
| contrats.csv | 436 | Windows-1252 | `;` | amounts mix `1 250,50`, `189,90 €`, `450` and `2.400` |

Reading these as UTF-8 with commas (the default in most tools) either crashes or silently turns `Réf contrat` into `RÃ©f contrat`. The reader detects both encoding and delimiter.

## Load order

`accounts` → `contacts` → `contracts`. Children are only accepted if their parent account was accepted (or merged into an account that was).

## Accounts

| Target field | Source column | Transform | Required | If invalid |
|---|---|---|:---:|---|
| external_id | N° client | trim | ✔ | reject |
| name | Raison sociale | trim, collapse spaces | ✔ | reject |
| siret | SIRET | 14 digits + Luhn checksum | | load empty, flag |
| address | Adresse | trim | | |
| postcode | CP | restore leading zero (`1000` → `01000`) | ✔ | reject |
| city | Ville | trim | ✔ | reject |
| phone | Tél | any French format → E.164 (`+33474…`) | | load empty, flag |
| email | Email | lowercase, format check | | load empty, flag |
| created_on | Date création | day-first date → ISO | | load empty, flag |
| owner | Commercial | trim | | |

**De-duplication (D-02)**
- Same valid SIRET → same legal entity → **merged automatically**. The most complete record survives, empty fields are filled from the duplicate, and the duplicate's contacts and contracts are re-linked to the survivor.
- Same name + postcode, no SIRET (households) → **flagged, not merged**. Two "Dupont Jean" in Villeurbanne can be father and son.

## Contacts

| Target field | Source column | Transform | Required | If invalid |
|---|---|---|:---:|---|
| external_id | N° contact | trim | ✔ | reject |
| account_external_id | N° client | resolved through merges | ✔ | reject if account not migrated |
| last_name | Nom | trim | ✔ | reject |
| first_name | Prénom | trim | | |
| job_title | Fonction | trim | | |
| mobile | Tél portable | any French format → E.164 | | load empty, flag |
| email | E-mail | lowercase, format check | | load empty, flag |

## Contracts

| Target field | Source column | Transform | Required | If invalid |
|---|---|---|:---:|---|
| external_id | Réf contrat | trim | ✔ | reject |
| account_external_id | N° client | resolved through merges | ✔ | reject if account not migrated |
| type | Formule | trim | ✔ | reject |
| annual_value | Montant annuel HT | French number rules, see below | ✔ | reject |
| start_date | Date début | day-first date → ISO | ✔ | reject |
| end_date | Date fin | day-first date → ISO | | load empty, flag |
| status | Statut | `Actif`→active, `Suspendu`→suspended, `Résilié`→terminated | ✔ | reject |

**Scope (D-03):** `terminated` contracts are valid but not migrated. They're counted as *skipped*, not rejected.

**Amounts (D-06):** comma = decimal separator; space or non-breaking space = thousands; a dot followed by exactly three digits and no comma (`2.400`) = thousands. `€` is ignored.

**Dates:** always day-first. `03/04/2021` is 3 April. Impossible dates (`31/02/2023`) are rejected, never "corrected".

## Validation outcome per row

Every source row gets exactly one status, which is what makes reconciliation possible:

| Status | Meaning | Where it shows up |
|---|---|---|
| accepted | loaded into the new platform | target, and in the exceptions file if it carries a warning |
| merged | duplicate folded into a survivor | exceptions file, "MERGED into CL…" |
| skipped | out of scope by agreement | exceptions file, "OUT OF SCOPE" |
| rejected | cannot be loaded | exceptions file, "REJECTED - needs your decision" |
