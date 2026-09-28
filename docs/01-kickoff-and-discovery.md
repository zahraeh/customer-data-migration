# 01 · Kickoff & discovery

**Customer:** Maison Verte Services (fictional): heating & plumbing maintenance, 38 technicians, Bourg-en-Bresse / Lyon area
**Project:** move customer, contact and contract data from a 12-year-old desktop tool into the new field-service platform
**Kickoff:** 08/09/2026 · **Target go-live:** 05/10/2026 (Monday, low-season)
**All data in this repo is generated.** No real customer, person or company is involved.

## Why they are switching

The legacy tool can't schedule technicians or send contract renewals, so the office runs both from Excel. Renewals get missed, and contracts lapse without anyone calling the customer. The new platform automates renewals, but only if the contract data it receives is right. **That makes the migration the part of the project where the money is.**

## Who's involved

| Person | Role | What they need from the migration |
|---|---|---|
| Nadia R. | Ops lead, project owner | Go-live on 05/10 with no data loss she has to explain to the owner |
| Laurent R. | Owner / manager | Contract revenue in the new tool matches what he knows it is |
| Office team (3) | Daily users | Can find every customer by name or phone on day one |
| Legacy vendor | Export only | Provides the CSV exports, no API |
| Implementation consultant | This repo | Mapping, dry runs, load, reconciliation, cutover |

## What we learned in discovery

**Confirmed**
- Three exports are available from the legacy tool: clients, contacts, contracts. CSV only, no API.
- ~480 customers (≈40% businesses with a SIRET, the rest households), ~670 contacts, ~430 contracts.
- Terminated contracts should **not** move (Nadia: "we never look at them, and they'd trigger renewal emails").
- The owner checks contract revenue monthly from the legacy report **"CA contrats actifs"**. That report is the number everybody trusts.

**Surprising**
- Some customers were created twice over the years ("a new rep didn't find them and re-created them").
- The office sometimes opens exports in Excel and saves them back "to clean things up".
- Customers were deleted from the legacy tool in the past, but their contacts and contracts stayed.

**Open at kickoff (and how each was closed)**

| # | Question | Closed by |
|---|---|---|
| Q1 | How many rejected rows can the office realistically review before go-live? | Nadia: "a few dozen, not hundreds" → [D-01](03-dry-run-log.md#decision-log) |
| Q2 | Are duplicates the same customer, or two customers with the same name? | Same SIRET = same company; households need a human → D-02 |
| Q3 | Keep terminated contracts? | No, they stay in the legacy archive → D-03 |
| Q4 | Is a customer with a bad phone number still worth migrating? | Yes: load without the phone, flag it → D-04 |

## The one thing asked of the customer at kickoff

> **A control total from the legacy tool, exported the same day as the CSVs.**

Row counts tell you nothing got lost. They don't tell you what got loaded is *right*. The customer's own "CA contrats actifs" figure is independent of every transform we write, so it's the only check that can catch our own mistakes. Received 18/09: **€701,366.21** ([data/source/CONTROL_TOTALS.txt](../data/source/CONTROL_TOTALS.txt)).

This turned out to be the most important request of the project: see [04 · Incident](04-incident-control-total-gap.md).

## Success criteria (agreed, signed off by Nadia)

1. Every source row is accounted for: loaded, merged, out of scope, or in the exceptions file with a reason.
2. Reject rate ≤ 3%, and every rejected row reviewed by the office before go-live.
3. Contract value in the new platform + value on hold in the exceptions file = legacy control total, **to the cent**.
4. The load can be re-run safely and rolled back in minutes.
