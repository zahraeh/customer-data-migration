# 04 · Incident: €90,295.61 of contract value misread during dry run 2

- **Status:** Resolved before go-live
- **Severity:** Critical. Would have under-stated active contract revenue by 12.9% in the new platform, with no error anywhere
- **Detected:** Dry run 2, 23/09/2026, by the control-total check
- **Affected:** 23 in-scope (active or suspended) contracts, all with a whole-euro value of €1,000 or more
- **Real customer impact:** none. Caught in a dry run; nothing had been written to the target

## Summary

Dry run 2 met every row-level criterion: 1.95% reject rate, every source row accounted for, no orphans. The reconciliation still returned **NO-GO**: contract value migrated plus value on hold came to €611,070.60 against a legacy control total of €701,366.21.

The legacy tool writes whole-euro amounts of €1,000 or more with a **dot as the thousands separator**: `2.400` means two thousand four hundred euros. The amount parser treated the dot as a decimal point and loaded **€2.40**. Nothing failed, because `2.40` is a perfectly valid number.

## Timeline (23/09/2026)

| Time | Event |
|---|---|
| 10:02 | Dry run 2 finished. Reject rate 1.95% (under 3%), all entities balanced. |
| 10:02 | Control-total check: **€90,295.61 unexplained** → NO-GO. |
| 10:10 | Ruled out scope: the gap isn't terminated contracts (excluded from both sides) and isn't rejected rows (their value is counted in "on hold"). So the problem is in rows that *were* accepted. |
| 10:25 | Compared migrated values against raw source strings. 23 accepted contracts had values under €10: `1.100` → 1.10, `6.750` → 6.75. |
| 10:31 | Checked the profile report from 18/09: shape `9.999` ×25 **existed, but wasn't displayed**. The profile showed only the 3 most common shapes per column, and this was the 5th. |
| 10:40 | Wrote the failing regression test (`test_amount_naive_silently_reads_thousands_dot_as_decimal`). |
| 11:15 | Implemented `amount_fr`; asked Nadia to confirm 5 of the 23 contracts against the signed paper contracts. |
| 24/09 09:30 | Nadia confirmed all 5 (e.g. CTR-2024-0292, Maintenance PAC: `2.600` in the export, €2,600/yr on paper). Decision D-06 logged. |
| 25/09 | Dry run 3: control total reconciled to €0.00. GO. |

## Root cause

Two conventions for the same field in one export:

| Legacy value | Meaning | `amount_naive` read | Correct |
|---|---|---:|---:|
| `1 250,50` | €1,250.50 | 1,250.50 | 1,250.50 |
| `189,90 €` | €189.90 | 189.90 | 189.90 |
| `2.400` | €2,400 | **2.40** | 2,400.00 |

The parser was written and tested against the formats we'd seen in the first 20 rows. No test covered a format we hadn't seen yet, and the profile that could have shown it cut it off.

## Why only the control total caught it

- **Row counts**: 23 rows were loaded. They were counted correctly; they just held the wrong values.
- **Validation**: `2.40` is a valid, positive number.
- **Our own totals**: we would have summed the same wrong values and matched ourselves.
- **The customer's control total** came from the legacy tool's own report, so it doesn't depend on any code we wrote. It was the one check we couldn't accidentally fool.

## Impact had it shipped

- 23 active contracts showing €1–€7 per year in the new platform. **€90,295.61 of annual revenue invisible** to the owner's reporting.
- Renewal emails quoting €2.40 instead of €2,400 to business customers.
- Discovered by the customer, not by us, probably at the first renewal cycle.

## Corrective actions

| # | Action | Status |
|---|---|---|
| 1 | `amount_fr` parser with explicit French rules + regression tests for every format seen | ✅ [migrate/transforms.py](../migrate/transforms.py) |
| 2 | Profile shows every value shape covering ≥ 2% of rows, not just the top 3 | ✅ [migrate/profile.py](../migrate/profile.py) |
| 3 | Control totals are a **hard** go-live criterion (NO-GO, not a warning) | ✅ already in place, and it worked |
| 4 | Kickoff checklist: ask for one control total per money or quantity field, exported the same day as the data | ✅ added to [05 · Runbook](05-cutover-runbook.md) |

## What we told the customer

See [06 · Customer update](06-customer-update.md).
