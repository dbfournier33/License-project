"""Render an analysis as Markdown (also used for the console summary)."""

FINDING_TITLES = {
    "disabledLicensed": "Licenses on disabled accounts",
    "guestLicensed": "Licenses on guest accounts",
    "sharedMailboxLicensed": "Licensed shared mailboxes",
    "inactive": "Inactive licensed users (30+ days)",
    "overlappingSuites": "Users with overlapping suites",
    "webOnlyDesktopSuite": "Desktop-app suite, web-only usage (downgrade candidates)",
    "assignmentErrors": "License assignment errors",
}


def _money(value, currency):
    return "—" if value is None else f"{currency} {value:,.2f}"


def to_markdown(result, max_rows=25):
    cur = result["currency"]
    t = result["totals"]
    out = [
        f"# License report: {result['tenant'] or 'tenant'}",
        f"_Generated {result['generatedAt']}_",
        "",
        "## Totals",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Monthly spend (priced SKUs) | {_money(t['monthlySpend'], cur)} |",
        f"| Annual spend | {_money(t['annualSpend'], cur)} |",
        f"| Paid seats purchased / assigned | {t['seatsPurchased']} / {t['seatsAssigned']} |",
        f"| **Confirmed waste / month** (unassigned, disabled, guest, shared) | **{_money(t['confirmedWasteMonthly'], cur)}** |",
        f"| At risk / month (no activity 90+ days) | {_money(t['atRiskMonthly'], cur)} |",
        "",
        "## By product",
        "",
        "| Product | Bought | Assigned | Unassigned | Price | Monthly | Disabled | Inactive 90+ | Web-only |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in result["skus"]:
        source = f" ({r['priceSource']})" if r.get("priceSource") else ""
        out.append(
            f"| {r['name']} | {r['purchased']} | {r['assigned']} | {r['unassigned']} | "
            f"{_money(r['unitPrice'], cur)}{source} | {_money(r['monthlyCost'], cur)} | "
            f"{r['onDisabledAccounts']} | {r['inactive90Plus']} | {r['webOnly']} |"
        )

    if result["renewals"]:
        out += ["", "## Renewals and trials (next 90 days)", "",
                "| Product | Date | Days | Seats | Trial | Status |", "|---|---|---|---|---|---|"]
        for r in result["renewals"]:
            out.append(
                f"| {r['name']} | {r['date']} | {r['daysAway']} | {r['totalLicenses']} | "
                f"{'yes' if r['isTrial'] else ''} | {r['status']} |"
            )

    for key, title in FINDING_TITLES.items():
        rows = result["findings"][key]
        if not rows:
            continue
        out += ["", f"## {title} ({len(rows)})", "", "| User | Licenses | Monthly | Detail |",
                "|---|---|---|---|"]
        for f in rows[:max_rows]:
            detail = ", ".join(
                f"{k}={v}" for k, v in f.items()
                if k not in ("displayName", "userPrincipalName", "skus", "monthlyCost")
                and v not in (None, "", [])
            )
            out.append(
                f"| {f['displayName']} ({f['userPrincipalName']}) | {', '.join(f['skus'])} | "
                f"{_money(f['monthlyCost'], cur)} | {detail} |"
            )
        if len(rows) > max_rows:
            out.append(f"| … {len(rows) - max_rows} more in report.json | | | |")

    if result["dataGaps"]:
        out += ["", "## Data gaps", ""] + [f"- {g}" for g in result["dataGaps"]]
    return "\n".join(out) + "\n"
