# Migration report — v2

**Project:** Maison Verte Services, legacy tool → new field-service platform  
**Mode:** Dry run (nothing written to the target)  
**Config:** `v2.yaml`

> Dry run 2. Postcodes: restore the leading zero Excel removed (postcode_fr).
> Phones: parse every French format with libphonenumber (phone_fr) instead of
> two hard-coded patterns. Everything else unchanged from v1.

## Decision: ⛔ NO-GO

- contracts.annual_value: €90,295.61 unexplained vs. the legacy control total

## 1. Every row accounted for

| Entity | Source rows | Accepted | Merged | Skipped | Rejected | Balanced |
|---|---:|---:|---:|---:|---:|:---:|
| accounts | 485 | 470 | 12 | 0 | 3 | ✅ |
| contacts | 670 | 652 | 0 | 0 | 18 | ✅ |
| contracts | 436 | 391 | 0 | 35 | 10 | ✅ |

Reject rate: **1.95%** (go-live limit 3.0%)

## 2. Every euro accounted for

Control totals come from the customer's legacy system, not from our own transforms.

| Check | Legacy control total | Migrated | On hold (rejected rows) | Unexplained | Result |
|---|---:|---:|---:|---:|:---:|
| contracts.annual_value | €701,366.21 | €590,936.84 | €20,133.76 | **€90,295.61** | ❌ |

_Source of control total: Maison Verte ops lead, legacy 'CA contrats actifs' report, 18/09/2026 (data/source/CONTROL_TOTALS.txt)_

## 3. Why rows were rejected

**accounts**

| Reason | Rows |
|---|---:|
| name is required but empty | 3 |

**contacts**

| Reason | Rows |
|---|---:|
| accounts # does not exist in the accounts export | 15 |
| accounts # was rejected, so this row cannot be attached to it | 3 |

**contracts**

| Reason | Rows |
|---|---:|
| accounts # does not exist in the accounts export | 4 |
| start_date: Date … is not a real calendar date | 3 |
| accounts # was rejected, so this row cannot be attached to it | 3 |

## 4. Loaded, but worth a look

| Entity | Warning | Rows |
|---|---|---:|
| accounts | phone: Phone … is not a valid French number | 15 |
| accounts | possible duplicate of #; loaded separately, please confirm | 10 |
| accounts | email: … is not a valid email address | 5 |
| contacts | re-linked from duplicate # to surviving record # | 24 |
| contacts | email: … is not a valid email address | 20 |
| contacts | mobile: Phone … is not a valid French number | 17 |
| contracts | re-linked from duplicate # to surviving record # | 12 |

---
Per-row detail for the customer: `exceptions_<entity>.csv` in this folder.
