"""Turn an analysis into what an executive asks: spend, waste, actions, deadlines.

Plain language, annual dollars, no SKU codes. Pure functions over analyze() output plus
the raw users (for per-department cost).
"""

from datetime import date

from .analyze import FREE_SKU_SEATS

# Plain-language category for each product; first matching rule wins.
CATEGORY_RULES = [
    ("COPILOT", "AI (Copilot)"),
    ("POWER_BI", "Analytics (Power BI)"),
    ("VISIO", "Projects & diagrams"),
    ("PROJECT", "Projects & diagrams"),
    ("MCO", "Phones & meetings"),
    ("PHONE", "Phones & meetings"),
    ("TEAMS_PREMIUM", "Phones & meetings"),
    ("MDE", "Security"),
    ("DEFENDER", "Security"),
    ("ATP", "Security"),
    ("AAD_PREMIUM", "Security"),
    ("EMS", "Security"),
    ("INTUNE", "Security"),
]
OFFICE_PREFIXES = ("O365_", "SPE_", "SPB", "STANDARDPACK", "ENTERPRISE", "EXCHANGE",
                   "OFFICESUBSCRIPTION", "DESKLESSPACK", "BUSINESS_")

# Cheaper plan for people who only use Office on the web (only where it's a clean swap).
WEB_DOWNGRADE = {
    "O365_BUSINESS_PREMIUM": "O365_BUSINESS_ESSENTIALS",  # Business Standard -> Basic
    "ENTERPRISEPACK": "STANDARDPACK",                     # Office 365 E3 -> E1
}


def category(part):
    upper = part.upper()
    for needle, label in CATEGORY_RULES:
        if needle in upper:
            return label
    if upper.startswith(OFFICE_PREFIXES):
        return "Email & Office"
    return "Other"


def _shelf(unused, show=3):
    biggest = sorted(unused, key=lambda s: s["unassignedMonthlyCost"] or 0, reverse=True)
    items = ", ".join(f"{s['unassigned']} × {s['name']}" for s in biggest[:show])
    more = f", and {len(unused) - show} more products" if len(unused) > show else ""
    return f"Bought but sitting on the shelf: {items}{more}."


def _fmt_date(iso):
    if not iso:
        return None
    d = date.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def executive_summary(result, data, list_prices=None):
    list_prices = list_prices or {}
    skus = result["skus"]
    unit = {s["sku"]: s["unitPrice"] or 0 for s in skus}
    name = {s["sku"]: s["name"] for s in skus}
    renewal = {s["sku"]: s.get("renewalDate") for s in skus}
    paid = [s for s in skus if (s["unitPrice"] or 0) > 0 and s["purchased"] < FREE_SKU_SEATS]
    f = result["findings"]

    annual = round(result["totals"]["monthlySpend"] * 12, 2)
    confirmed = round(result["totals"]["confirmedWasteMonthly"] * 12, 2)
    at_risk = round(result["totals"]["atRiskMonthly"] * 12, 2)

    # --- people and departments (from raw users) ---
    sku_part = {s["skuId"]: s["skuPartNumber"] for s in data.get("subscribedSkus") or []}
    depts, employees = {}, 0
    for u in data.get("users") or []:
        parts = [sku_part.get(l["skuId"]) for l in u.get("assignedLicenses") or []]
        cost = sum(unit.get(p, 0) for p in parts) * 12
        if not cost:
            continue
        if u.get("accountEnabled") is not False and u.get("userType") != "Guest":
            employees += 1
        d = depts.setdefault(u.get("department") or "No department set", {"annual": 0, "people": 0})
        d["annual"] += cost
        d["people"] += 1
    assigned_total = sum(d["annual"] for d in depts.values())
    if annual - assigned_total > 1:
        depts["Not assigned to anyone"] = {"annual": annual - assigned_total, "people": 0}
    departments = sorted(
        ({"name": k, "annual": round(v["annual"], 2), "people": v["people"]} for k, v in depts.items()),
        key=lambda d: d["annual"], reverse=True,
    )

    # --- where the money goes ---
    cats = {}
    for s in paid:
        c = category(s["sku"])
        cats[c] = cats.get(c, 0) + (s["monthlyCost"] or 0) * 12
    categories = [
        {"name": k, "annual": round(v, 2), "pct": round(100 * v / annual) if annual else 0}
        for k, v in sorted(cats.items(), key=lambda kv: kv[1], reverse=True)
    ]

    # --- actions ---
    actions = []

    def add(title, why, savings, when, deadline=None, count=0):
        if count:
            actions.append({"title": title, "why": why, "savingsAnnual": round(savings, 2)
                            if savings is not None else None, "when": when,
                            "deadline": deadline, "count": count})

    leavers = {}
    for key in ("disabledLicensed", "guestLicensed", "sharedMailboxLicensed"):
        for row in f[key]:
            leavers.setdefault(row["userPrincipalName"].lower(), row)
    add(
        f"Remove licenses from {len(leavers)} former employees, guests and shared mailboxes",
        "These accounts are switched off or don't need a license, but are still being paid for.",
        sum(r["monthlyCost"] for r in leavers.values()) * 12, "Now", count=len(leavers),
    )

    unused = [s for s in paid if s["unassigned"]]
    soonest = min((renewal[s["sku"]] for s in unused if renewal[s["sku"]]), default=None)
    add(
        f"Stop paying for {sum(s['unassigned'] for s in unused)} licenses that were never assigned",
        _shelf(unused),
        sum(s["unassignedMonthlyCost"] or 0 for s in unused) * 12,
        "At each product's renewal", deadline=soonest,
        count=len(unused),
    )

    stale = [r for r in f["inactive"] if r["bucket"] in ("90+", "never")
             and r["userPrincipalName"].lower() not in leavers]
    add(
        f"Check {len(stale)} people who haven't signed in for 90+ days",
        "Active accounts with no recent use. Confirm with their managers before removing.",
        sum(r["monthlyCost"] for r in stale) * 12, "Confirm with managers", count=len(stale),
    )

    dupes = f["overlappingSuites"]
    add(
        f"Remove duplicate plans from {len(dupes)} people",
        "These people hold two overlapping Office plans; one covers everything they need.",
        sum(r.get("redundantMonthlyCost", 0) for r in dupes) * 12, "Now", count=len(dupes),
    )

    web = f["webOnlyDesktopSuite"]
    web_savings, priced = 0, False
    for r in web:
        for part in r["skus"]:
            cheaper = WEB_DOWNGRADE.get(part)
            if cheaper and cheaper in list_prices:
                web_savings += (unit.get(part, 0) - list_prices[cheaper]) * 12
                priced = True
    add(
        f"Move {len(web)} people who only use web Office to a cheaper plan",
        "They never open the desktop Office apps their plan includes.",
        web_savings if priced else None, "At renewal", count=len(web),
    )

    actions.sort(key=lambda a: a["savingsAnnual"] or 0, reverse=True)

    # --- deadlines ---
    deadlines = []
    for r in result["renewals"]:
        if r["isTrial"]:
            what = f"{r['name']} trial ends: decide whether to keep paying for it"
        else:
            what = f"{r['name']} renews ({r['totalLicenses']} licenses): set the right number before then"
        deadlines.append({"what": what, "date": _fmt_date(r["date"]), "daysAway": r["daysAway"]})

    notes = []
    if any(s["priceSource"] == "list" for s in paid):
        notes.append("Some prices are Microsoft list prices, not your invoice. Actual costs may differ.")
    if not data.get("signInAvailable"):
        notes.append("Sign-in history isn't available on this tenant's plan; activity comes from usage reports.")
    notes.append(
        "On annual plans, Microsoft usually only lets you reduce licenses at renewal. "
        "Savings land at the next renewal unless the freed licenses are reused for new hires."
    )

    return {
        "tenant": result["tenant"],
        "generatedAt": result["generatedAt"],
        "currency": result["currency"],
        "annualSpend": annual,
        "monthlySpend": result["totals"]["monthlySpend"],
        "employees": employees,
        "perEmployee": round(annual / employees, 2) if employees else None,
        "wasteConfirmedAnnual": confirmed,
        "wasteAtRiskAnnual": at_risk,
        "wastePct": round(100 * (confirmed + at_risk) / annual) if annual else 0,
        "actions": actions,
        "categories": categories,
        "departments": departments,
        "deadlines": deadlines,
        "notes": notes,
    }
