# 06 · Customer update (email to Nadia, 25/09/2026)

*Written for the ops lead: no technical background needed, and it asks for exactly one thing.*

---

**Subject:** Migration: ready for 05/10, one decision needed from you by Friday

Hi Nadia,

Short version: **the migration is ready for go-live on Monday 5 October.** We need one thing from your team by Friday 2 October, and I owe you an explanation of something we caught this week.

**Where we are**

We ran the full migration three times on a test copy. The third run passed every check we agreed on at kickoff:

- All 1,591 rows from your three exports are accounted for.
- 470 customers, 652 contacts and 391 active contracts are ready to move.
- The contract total matches your "CA contrats actifs" report **to the cent**: €701,366.21.

**What we caught this week**

On Tuesday's test run, everything looked fine: no errors, and every row accounted for. But the contract total came out **€90,295 lower** than your report.

The cause: your old system writes some amounts like `2.400`, meaning two thousand four hundred euros. Our first version read that as two euros forty. 23 contracts were affected, all business customers paying €1,000 or more a year. Thank you for checking five of them against the paper contracts. That confirmed the fix.

This never reached your new platform. It's the reason we asked for your control total at kickoff, and it's exactly what that total is for.

**What we need from you by Friday 2 October**

Please open **exceptions_contracts.csv**, **exceptions_contacts.csv** and **exceptions_accounts.csv** (they open directly in Excel) and look at the rows marked **REJECTED**. There are 31 in total:

| What | How many | What we need from you |
|---|---:|---|
| Contacts and contracts linked to customers that were deleted from the old system | 19 | Recreate the customer, or drop the row? |
| Customers with no name in the old system (and their contacts/contracts) | 3 + 6 | Who are they? |
| Contracts with an impossible start date (e.g. 31 February) | 3 | The correct date |

Together, these rejected contracts are worth **€25,528** a year, so they're worth the 30 minutes.

Everything marked **MIGRATED with warning** (mostly phone numbers and emails we couldn't read) will be in the new platform on Monday. Your team can fix those in the first week; no need to do it before go-live.

**Next steps**

- **Friday 2 Oct, 17:00:** freeze. Please ask the team to stop editing in the old system, and send me the final exports plus that day's "CA contrats actifs" figure.
- **Saturday 3 Oct:** final load and checks. I'll call you by 14:00 for the go/no-go.
- **Monday 5 Oct:** go-live. I'll be with the office at 09:00.

If anything on Saturday doesn't add up, we don't go live. Your team keeps working in the old system on Monday as usual and we reschedule. Nothing is lost either way.

Best,
Implementation Consultant
