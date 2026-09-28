# Migration report — v1

**Project:** Maison Verte Services, legacy tool → new field-service platform  
**Mode:** Dry run (nothing written to the target)  
**Config:** `v1.yaml`

> Dry run 1. First mapping, built from the kickoff workshop and the vendor's
> import template. Strict validation everywhere, no format repair yet.

## Decision: ⛔ NO-GO

- reject rate 31.3% is above the agreed 3.0%
- contracts.annual_value: €90,295.61 unexplained vs. the legacy control total

## 1. Every row accounted for

| Entity | Source rows | Accepted | Merged | Skipped | Rejected | Balanced |
|---|---:|---:|---:|---:|---:|:---:|
| accounts | 485 | 330 | 9 | 0 | 146 | ✅ |
| contacts | 670 | 454 | 0 | 0 | 216 | ✅ |
| contracts | 436 | 271 | 0 | 29 | 136 | ✅ |

Reject rate: **31.30%** (go-live limit 3.0%)

## 2. Every euro accounted for

Control totals come from the customer's legacy system, not from our own transforms.

| Check | Legacy control total | Migrated | On hold (rejected rows) | Unexplained | Result |
|---|---:|---:|---:|---:|:---:|
| contracts.annual_value | €701,366.21 | €383,116.79 | €227,953.81 | **€90,295.61** | ❌ |

_Source of control total: Maison Verte ops lead, legacy 'CA contrats actifs' report, 18/09/2026 (data/source/CONTROL_TOTALS.txt)_

## 3. Why rows were rejected

**accounts**

| Reason | Rows |
|---|---:|
| postcode: Postcode … must be 5 digits | 145 |
| name is required but empty | 3 |

**contacts**

| Reason | Rows |
|---|---:|
| accounts # was rejected, so this row cannot be attached to it | 201 |
| accounts # does not exist in the accounts export | 15 |

**contracts**

| Reason | Rows |
|---|---:|
| accounts # was rejected, so this row cannot be attached to it | 130 |
| accounts # does not exist in the accounts export | 4 |
| start_date: Date … is not a real calendar date | 3 |

## 4. Loaded, but worth a look

| Entity | Warning | Rows |
|---|---|---:|
| accounts | phone: Phone … is not in a recognised format | 80 |
| accounts | possible duplicate of #; loaded separately, please confirm | 6 |
| accounts | email: … is not a valid email address | 3 |
| contacts | mobile: Phone … is not in a recognised format | 101 |
| contacts | re-linked from duplicate # to surviving record # | 19 |
| contacts | email: … is not a valid email address | 17 |
| contracts | re-linked from duplicate # to surviving record # | 9 |

---
Per-row detail for the customer: `exceptions_<entity>.csv` in this folder.
