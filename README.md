# Customer Data Migration Toolkit

**Every row accounted for. Every euro accounted for.**

📄 **Case study (5-minute read):** [zahra-work.com/data-migration.html](https://zahra-work.com/data-migration.html)
📁 **The six engagement documents:** [docs/](docs/), listed [below](#whats-in-here)

A portfolio project modelling the part of a SaaS implementation where most of the risk sits: moving a customer's data out of a legacy tool and into the new platform. It covers the whole engagement, from kickoff questions to the cutover runbook, plus the working Python toolkit that does the migration and proves it was done right.

> **Customer:** Maison Verte Services, a fictional 38-technician heating & plumbing company near Lyon, moving 12 years of customers, contacts and contracts out of a desktop tool.
> All data is generated ([data/generate_sample.py](data/generate_sample.py)); no real person or company appears anywhere.

## The story in three dry runs

| Run | What changed | Reject rate | Rows balanced | Euros unexplained | Decision |
|---|---|---:|:---:|---:|:---:|
| 1 | Strict mapping from the vendor template | 31.3% | ✅ | €90,295.61 | ⛔ |
| 2 | Repaired postcodes Excel had truncated, parsed every phone format | 1.95% | ✅ | **€90,295.61** | ⛔ |
| 3 | French number parsing: `2.400` = €2,400, not €2.40 | 1.95% | ✅ | €0.00 | ✅ |

**Dry run 2 is the point of this project.** Every row-level check passed. A customer-provided control total showed 12.9% of contract revenue had been silently misread, with no error anywhere. See the [incident write-up](docs/04-incident-control-total-gap.md).

## What's in here

**Engagement documents** (read in order)

1. [Kickoff & discovery](docs/01-kickoff-and-discovery.md): stakeholders, what was confirmed vs. open, and the one request that mattered most
2. [Data mapping spec](docs/02-data-mapping-spec.md): source → target, field by field, with the rules for duplicates and scope
3. [Dry-run log & decision log](docs/03-dry-run-log.md): what each run found, and every decision with who agreed to it
4. [Incident: €90k misread](docs/04-incident-control-total-gap.md): timeline, root cause, why only the control total caught it
5. [Cutover runbook](docs/05-cutover-runbook.md): freeze, load, go/no-go checks, rollback trigger, hypercare
6. [Customer update](docs/06-customer-update.md): the same story, written for a non-technical ops lead, with one clear ask

**Generated evidence**: [source profile](reports/source_profile.md) · reports for [dry run 1](reports/v1/dry_run_report.md), [2](reports/v2/dry_run_report.md), [3](reports/v3/dry_run_report.md) · [production-style load](reports/v3/load_report.md) · customer exceptions files (`reports/*/exceptions_*.csv`)

## The toolkit

```
profile  →  suggest-mapping  →  dry-run  →  load  →  reconcile  →  (rollback)
```

| Command | What it does |
|---|---|
| `profile` | Detects encoding and delimiter, and shows each column's fill rate and **value shapes** (`99999` vs `9999` = lost leading zeros) |
| `suggest-mapping` | Drafts a column mapping with a confidence and a reason for each line. Offline heuristics by default; `--ai` asks Claude, sending only headers and samples, or format-only samples with `--mask` |
| `dry-run` | Transforms, validates and de-duplicates every row, then reconciles and gives a GO / NO-GO with reasons |
| `load` | Refuses to run on a NO-GO. Batched, idempotent upserts keyed on legacy ID; retries 429s with exponential backoff; reconciles against the target afterwards |
| `rollback` | Removes everything a given run wrote |

**Design choices that matter in a real migration**

- **One outcome per row.** Every source row ends up *accepted*, *merged*, *skipped* or *rejected*, so `source = sum of outcomes` is checkable on every run.
- **Control totals come from the customer**, not from our code. It's the only check our own bugs can't fool.
- **Merge only on strong keys.** Same SIRET is merged automatically; same name + postcode is flagged for a human. A wrong merge is worse than a duplicate.
- **Repair what's certain, reject what isn't.** `1000` → `01000` is safe. `31/02/2023` is not "probably 28/02", so it goes back to the customer.
- **Bad optional data doesn't block a customer.** An unreadable phone number loads empty and is flagged; the customer still migrates.
- **Children follow merges.** Contacts and contracts on a duplicate account are re-linked to the survivor, not orphaned.
- **Exceptions files open in French Excel with a double-click** (UTF-8 BOM, `;`), because that's how the customer's team will open them.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python data/generate_sample.py                       # regenerate the fictional exports
python -m migrate profile data/source/*.csv
python -m migrate suggest-mapping data/source/contrats.csv --entity contracts

python -m migrate dry-run --config config/v2.yaml    # NO-GO: €90,295.61 unexplained
python -m migrate dry-run --config config/v3.yaml    # GO

python -m migrate load --config config/v3.yaml --db target.db --simulate-rate-limit 2
python -m migrate rollback --db target.db --run-id <run id printed by load>

python -m pytest                                     # 50 tests
```

`--ai` mapping suggestions need an Anthropic API key (`ANTHROPIC_API_KEY`) and use `claude-opus-5`. Everything else runs offline.

## Stack

Python 3.9+ · SQLite (stand-in for the target platform's bulk API) · libphonenumber · PyYAML · pytest · Anthropic SDK (optional)

## Layout

```
migrate/            the toolkit (transforms, pipeline, loader, reconcile, report, profile, suggest)
config/v1–v3.yaml   the mapping as it evolved across dry runs
data/source/        fictional legacy exports (Windows-1252, ';') + the customer's control total
docs/               engagement documents 01–06
reports/            generated profile, dry-run and load reports, customer exceptions files
tests/              unit tests + the three dry runs pinned as regression tests
```
