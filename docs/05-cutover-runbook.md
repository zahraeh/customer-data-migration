# 05 · Cutover runbook

**Go-live:** Monday 05/10/2026 · **Freeze starts:** Friday 02/10, 17:00
**Roles:** IC = implementation consultant · NR = Nadia (ops lead, go/no-go owner) · LV = legacy vendor

## T-5 → T-1: before the weekend

| When | Step | Owner | Done when |
|---|---|---|---|
| 28/09 | Office reviews [exceptions files](../reports/v3/) from dry run 3 and fills in the decision for all rejected rows (D-07) | NR | Every "REJECTED" row has a decision |
| 29/09 | Rollback rehearsal on staging: load, roll back, confirm counts return to 0 | IC | `python -m migrate rollback` removes 100% of the run's rows |
| 01/10 | Office training on the new platform (search, contracts, renewals) | IC | 3/3 office staff trained |
| 02/10 17:00 | **Freeze**: no more edits in the legacy tool | NR | Email sent to the team |
| 02/10 17:30 | Final exports + same-day control total from the "CA contrats actifs" report | NR, LV | 3 CSVs + control total received |

## Saturday 03/10: load

| # | Step | Command / check | Go / no-go |
|---|---|---|---|
| 1 | Profile the final exports; compare shapes to dry run 3 | `python -m migrate profile data/source/*.csv` | Any **new** value shape in a structured column → stop and investigate |
| 2 | Update `control_totals.expected` in the config to the new figure | config/v3.yaml | Figure comes from NR, same day as exports |
| 3 | Final dry run | `python -m migrate dry-run --config config/v3.yaml` | Must be GO |
| 4 | Load to production | `python -m migrate load --config config/v3.yaml --db <prod>` | Record the run ID |
| 5 | Post-load reconciliation (automatic in step 4) | reports/v3/load_report.md | In target = accepted, 0 stale, 0 orphans, €0.00 unexplained |
| 6 | Spot check: 10 random accounts + the 5 highest-value contracts, side by side with the legacy tool | NR | 15/15 match |
| 7 | **Go / no-go call** | NR + IC | NR says go |

**Rollback trigger:** any failed check in steps 5–6 that can't be explained in 2 hours.
**Rollback:** `python -m migrate rollback --db <prod> --run-id <id>`. The legacy tool is still intact (read-only), so rolling back means the office works in the legacy tool on Monday as usual and we reschedule.

## Monday 05/10 onwards: hypercare (2 weeks)

| When | What |
|---|---|
| Daily 09:00, week 1 | 15-min check-in with the office: anything they couldn't find? |
| Daily | Office works through "MIGRATED with warning" rows (32 missing phone numbers, 25 invalid emails, 10 possible household duplicates) |
| 09/10 | First renewal batch runs in the new platform. IC reviews it with NR **before** it sends |
| 16/10 | Hypercare exit: open issues list empty or handed over to support |
| 05/10 + 12 months | Legacy tool archive switched off (D-03) |

## Kickoff checklist for the next migration

Lessons from this one, turned into questions to ask on day one:

- [ ] What encoding and delimiter do the exports use? Has anyone opened and re-saved them in Excel?
- [ ] **For every money or quantity field: which legacy report gives its total, and can we get it on export day?**
- [ ] Which identifier is truly unique (SIRET, email, phone)? Which duplicates are safe to merge automatically?
- [ ] What's out of scope, and would migrating it trigger anything (emails, invoices, renewals)?
- [ ] How many rejected rows can the customer's team review, and by when?
- [ ] Can the legacy tool stay read-only after go-live, so rollback means "keep working as usual"?
