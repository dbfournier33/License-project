# License Project — Scope

_Last updated: 2026-10-27_

## The problem

Mid-sized organizations (50–1,000 people) don't know what they spend on software
licenses, who holds them, or whether anyone uses them. The vendor admin portals show
seat counts, but not cost, usage, or waste in one place — and nobody reconciles
licenses against who actually still works there.

## The product

A **license consumption dashboard**: pull license, usage, and cost data from each
vendor, tie it to real people, and show spend and waste in one view.

Hierarchy: **Vendor → Product → Tier → Cost → Details**

```
Microsoft
 ├─ Microsoft 365 E3   50 bought │ 47 assigned │ 3 unassigned │ $36/seat │ $1,800/mo │ renews 2027-03-14
 │    ├─ 5 assigned to disabled accounts        → $180/mo waste
 │    ├─ 6 no sign-in in 90 days                → $216/mo at risk
 │    └─ 9 use web apps only (E1/F3 candidates) → potential downgrade
 └─ ...
Adobe
 └─ ...
```

The pitch: **"Here's what you spend, who has it, who doesn't use it, and what you can
cut before the next renewal."**

## Who buys it

- **First:** MSPs (multi-tenant, one MSP covers many clients; reachable cold through
  r/msp and MSP communities). CSP-reseller MSPs can also supply real pricing via the
  Partner Center API.
- **Second:** mid-sized companies directly (IT manager or finance).
- **Vertical to explore:** architecture / engineering / construction firms — expensive
  desktop licenses (Autodesk, Adobe, Bluebeam), small IT teams, project-based staffing.

## Waste checks (Microsoft 365 first)

| Check | Source |
|---|---|
| Purchased but unassigned seats | `subscribedSkus` |
| Licenses on disabled accounts (leavers) | `users.accountEnabled` + `assignedLicenses` |
| No sign-in in 30/60/90 days | `users.signInActivity` (needs Entra ID P1) |
| No workload activity in the report period | `getOffice365ActiveUserDetail` |
| Overlapping suites on one user (e.g., E3 + Business Standard) | `assignedLicenses` |
| Desktop-app suite but web-only usage (downgrade candidate) | `getM365AppUserDetail` |
| Licensed shared mailboxes | `getMailboxUsageDetail` |
| Licensed guest accounts | `users.userType` |
| Group-licensing assignment errors | `licenseAssignmentStates` |
| Renewals in the next 90 days, trials | `directory/subscriptions` |

## Known constraints

1. **Graph has no pricing.** Prices come from a per-tenant price table (list-price
   defaults, customer overrides). Later: Partner Center API for CSP MSPs, invoices.
2. **Usage reports are anonymized by default.** Admin center → Settings → Org settings
   → Reports → turn off "Display concealed user, group, and site names". The probe
   detects this and warns.
3. **Sign-in data needs Entra ID P1** (Business Premium, E3, E5 include it).
4. **SKU part numbers are cryptic** (`ENTERPRISEPACK` = Office 365 E3). We map them
   with Microsoft's published product-names CSV.

## Phases

| Phase | Deliverable | Status |
|---|---|---|
| 1. Probe | Read-only script: pull every M365 endpoint, save raw JSON, print a waste summary | Built; awaiting first real-tenant run |
| 2. Engine | Normalize into SQLite; join users ↔ licenses ↔ usage ↔ prices | Next |
| 3. Dashboard | Web dashboard with the hierarchy, user drill-down, CSV export | **v1 built** (static HTML + demo mode) |
| 4. Connectors | Adobe, Zoom, Autodesk, same pattern | |
| 5. Add-ons | Helpdesk plugin (license availability in the ticket), renewal calendar, HR reconciliation (UKG/ADP/Workday or CSV) | |

## Principles

- **Read-only.** We never change a customer tenant. Reclaim/downgrade actions come later and always need human approval.
- **Certificate auth, least privilege.** No client secrets in production.
- **Store only what we need.** Names, license assignments, last activity — no mail, files, or content.
