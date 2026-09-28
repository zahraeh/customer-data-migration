# 03 · Dry-run log & decision log

A dry run executes the full pipeline (read, transform, validate, de-duplicate, reconcile) without writing to the target. Each run uses a versioned config, and its report is kept, so every change can be traced to the evidence that caused it.

| Run | Date | Config | Reject rate | Rows balanced | Euros unexplained | Decision |
|---|---|---|---:|:---:|---:|:---:|
| 1 | 21/09 | [v1](../config/v1.yaml) | **31.3%** | ✅ | €90,295.61 | ⛔ NO-GO |
| 2 | 23/09 | [v2](../config/v2.yaml) | 1.95% | ✅ | **€90,295.61** | ⛔ NO-GO |
| 3 | 25/09 | [v3](../config/v3.yaml) | 1.95% | ✅ | €0.00 | ✅ GO |

Full reports: [reports/v1](../reports/v1/dry_run_report.md) · [reports/v2](../reports/v2/dry_run_report.md) · [reports/v3](../reports/v3/dry_run_report.md)

---

## Dry run 1: strict mapping, 31% rejected

The first mapping followed the vendor's import template literally: postcodes must be 5 digits, and phone numbers must look like `06 12 34 56 78` or `+33…`.

**What happened**
- **145 accounts rejected** for 4-digit postcodes. All of them are in the Ain department (01xxx). Excel had stored the column as a number and dropped the leading zero.
- Those 145 rejections **cascaded**: 201 contacts and 130 contracts rejected because their account was.
- **181 phone numbers dropped** (loaded empty) because they were written `06.12.34.56.78`, `33612345678`, etc.

**What we did**
- Confirmed with Nadia that every 4-digit postcode in the export is an Ain postcode (the company has no customers in 02–09). → **D-05**: pad to 5 digits.
- Replaced the two hard-coded phone patterns with libphonenumber, which accepts any valid French format.

> Lesson: one bad column in a parent table multiplies. 145 bad postcodes became 476 rejected rows.

## Dry run 2: every row balances, the money doesn't

Reject rate down to 1.95%, under the 3% threshold. Every row accounted for. The phone drop-outs went from 181 to 32, and the 32 are genuinely invalid (truncated) numbers.

By row counts alone this run was ready. **The control-total check said otherwise: €90,295.61 of active contract value was unexplained.** Full write-up: [04 · Incident](04-incident-control-total-gap.md).

## Dry run 3: GO

Amounts parsed with French number rules (D-06). Control total reconciles to the cent:

| Legacy control total | Migrated | On hold (exceptions file) | Unexplained |
|---:|---:|---:|---:|
| €701,366.21 | €675,837.85 | €25,528.36 | **€0.00** |

The €25,528.36 on hold sits in 10 rejected contracts: 4 on accounts deleted from the legacy tool, 3 on the nameless accounts, and 3 with impossible start dates (`31/02/2023`). Each one is in [exceptions_contracts.csv](../reports/v3/exceptions_contracts.csv) with a reason and waits for Nadia's decision (D-07).

---

## Decision log

| ID | Date | Decision | Why | Agreed by |
|---|---|---|---|---|
| D-01 | 08/09 | Go-live requires: reject rate ≤ 3%, 100% of rows accounted for, control total matched to the cent, rollback rehearsed | "A few dozen rows to review, not hundreds" is what the office can absorb in a week | Nadia |
| D-02 | 10/09 | Auto-merge duplicates **only** on identical valid SIRET. Households with the same name + postcode are flagged, never merged | A wrong merge silently combines two real customers' contracts, and that's much harder to undo than a duplicate | Nadia |
| D-03 | 10/09 | Terminated contracts stay in the legacy archive (read-only for 12 months) | They'd trigger renewal emails in the new platform | Nadia, Laurent |
| D-04 | 10/09 | An invalid phone/email doesn't block a customer: load it empty and flag it | Losing a customer is worse than losing a phone number the office can re-enter | Nadia |
| D-05 | 22/09 | 4-digit postcodes are padded with a leading zero | All confirmed to be Ain (01xxx); Excel removed the zero | Nadia |
| D-06 | 24/09 | In amounts, a dot followed by exactly 3 digits is a thousands separator | Legacy tool prints whole-euro amounts ≥ 1,000 as `2.400`; confirmed against 5 contracts on paper | Nadia, legacy vendor |
| D-07 | 25/09 | Orphan contacts/contracts (account deleted in legacy): the office decides per row, recreate the account or drop the row | Only the office knows whether those customers are still active | Nadia (review due 02/10) |
