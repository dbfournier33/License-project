"""Turn collected tenant data into spend totals, per-SKU rollups, and waste findings.

Pure functions only: no network, so this can be tested against fixtures.
"""

import re
from datetime import datetime, timezone

from .billing import invoice_prices
from .skus import BASE_SUITES, DESKTOP_SUITES

INACTIVE_BUCKETS = (90, 60, 30)
NEW_USER_GRACE_DAYS = 30
RENEWAL_WINDOW_DAYS = 90
FREE_SKU_SEATS = 10000


def _parse_dt(value):
    if not value:
        return None
    try:
        if len(value) == 10:  # report dates: YYYY-MM-DD
            return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Graph can send 7-digit fractions; Python < 3.11 only parses up to 6.
        value = re.sub(r"(\.\d{6})\d+", r"\1", value.replace("Z", "+00:00"))
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _col(row, name):
    """Report column lookup that tolerates Microsoft's inconsistent casing."""
    for key, value in row.items():
        if key and key.strip().lower() == name:
            return value
    return None


def _report_last_activity(rows):
    """UPN -> latest 'Last Activity Date' across all workloads in the active-users report."""
    last = {}
    for row in rows or []:
        upn = (_col(row, "user principal name") or "").lower()
        dates = [
            _parse_dt(v) for k, v in row.items() if k and k.lower().endswith("last activity date")
        ]
        dates = [d for d in dates if d]
        if upn and dates:
            last[upn] = max(dates)
    return last


def _reports_concealed(reports):
    for rows in reports.values():
        for row in rows or []:
            upn = _col(row, "user principal name")
            if upn:
                return "@" not in upn
    return False


def analyze(data, prices, names, now=None):
    now = now or datetime.now(timezone.utc)
    currency = prices.get("currency", "USD")
    list_prices = prices.get("monthly_per_seat", {})
    overrides = prices.get("overrides", {})
    skus = data.get("subscribedSkus") or []
    users = data.get("users") or []
    reports = data.get("reports") or {}

    sku_part = {s["skuId"]: s["skuPartNumber"] for s in skus}

    billed, unmatched_billing = invoice_prices(data.get("billing"), data.get("subscriptions"))

    def price_info(part):
        """Your override, else what the invoice says, else list price."""
        if part in overrides:
            return overrides[part], "override"
        if part in billed:
            return billed[part]["price"], "invoice"
        if part in list_prices:
            return list_prices[part], "list"
        return None, None

    def price(part):
        return price_info(part)[0]

    def user_skus(user):
        return [sku_part.get(l["skuId"], l["skuId"]) for l in user.get("assignedLicenses") or []]

    def user_cost(parts):
        return round(sum(price(p) or 0 for p in parts), 2)

    def entry(user, parts, **extra):
        return {
            "displayName": user.get("displayName"),
            "userPrincipalName": user.get("userPrincipalName"),
            "skus": parts,
            "monthlyCost": user_cost(parts),
            **extra,
        }

    findings = {k: [] for k in (
        "disabledLicensed", "guestLicensed", "sharedMailboxLicensed", "inactive",
        "overlappingSuites", "webOnlyDesktopSuite", "assignmentErrors",
    )}

    # --- per-user checks ---
    report_last = _report_last_activity(reports.get("activeUsers"))
    shared_upns = {
        (_col(r, "user principal name") or "").lower()
        for r in reports.get("mailboxUsage") or []
        if (_col(r, "recipient type") or "").lower().startswith("shared")
    }
    web_only_upns = {
        (_col(r, "user principal name") or "").lower()
        for r in reports.get("appUsage") or []
        if _col(r, "windows") == "No" and _col(r, "mac") == "No" and _col(r, "web") == "Yes"
    }

    waste_users = {}  # upn -> cost; union so one user is never counted twice
    for user in users:
        parts = user_skus(user)
        upn = (user.get("userPrincipalName") or "").lower()

        for state in user.get("licenseAssignmentStates") or []:
            if state.get("state") == "Error":
                findings["assignmentErrors"].append(entry(
                    user, [sku_part.get(state.get("skuId"), state.get("skuId"))],
                    error=state.get("error"), viaGroup=state.get("assignedByGroup"),
                ))

        if not parts:
            continue

        if user.get("accountEnabled") is False:
            findings["disabledLicensed"].append(entry(user, parts))
            waste_users[upn] = user_cost(parts)
        if user.get("userType") == "Guest":
            findings["guestLicensed"].append(entry(user, parts))
            waste_users[upn] = user_cost(parts)
        if upn in shared_upns:
            findings["sharedMailboxLicensed"].append(entry(user, parts))
            waste_users[upn] = user_cost(parts)

        suites = [p for p in parts if p in BASE_SUITES]
        if len(suites) > 1:
            keep = max(suites, key=lambda p: price(p) or 0)
            extra = [p for p in suites if p != keep]
            findings["overlappingSuites"].append(entry(
                user, suites, redundant=extra, redundantMonthlyCost=user_cost(extra),
            ))

        if upn in web_only_upns and any(p in DESKTOP_SUITES for p in parts):
            findings["webOnlyDesktopSuite"].append(entry(user, parts))

        # Inactivity: only for enabled accounts past their first month.
        created = _parse_dt(user.get("createdDateTime"))
        if user.get("accountEnabled") is False or (
            created and (now - created).days < NEW_USER_GRACE_DAYS
        ):
            continue
        sign_in = user.get("signInActivity") or {}
        seen = [
            _parse_dt(sign_in.get(k)) for k in (
                "lastSignInDateTime", "lastNonInteractiveSignInDateTime",
                "lastSuccessfulSignInDateTime",
            )
        ] + [report_last.get(upn)]
        seen = [d for d in seen if d]
        last_seen = max(seen) if seen else None
        if not data.get("signInAvailable") and not report_last:
            continue  # no activity source at all; don't call everyone inactive
        days = (now - last_seen).days if last_seen else None
        bucket = next((b for b in INACTIVE_BUCKETS if days is None or days >= b), None)
        if bucket:
            findings["inactive"].append(entry(
                user, parts,
                lastSeen=last_seen.isoformat() if last_seen else None,
                daysInactive=days, bucket=f"{bucket}+" if days is not None else "never",
            ))

    # --- per-SKU rollup ---
    sku_rows = []
    for s in skus:
        part = s["skuPartNumber"]
        purchased = (s.get("prepaidUnits") or {}).get("enabled", 0)
        assigned = s.get("consumedUnits", 0)
        unit, source = price_info(part)
        unassigned = max(purchased - assigned, 0)
        holders = [f for f in findings["disabledLicensed"] if part in f["skus"]]
        sku_rows.append({
            "vendor": "Microsoft",
            "sku": part,
            "name": names.get(part, part),
            "purchased": purchased,
            "assigned": assigned,
            "unassigned": unassigned,
            "suspended": (s.get("prepaidUnits") or {}).get("suspended", 0),
            "warning": (s.get("prepaidUnits") or {}).get("warning", 0),
            "unitPrice": unit,
            "priceSource": source,
            "monthlyCost": round(purchased * unit, 2) if unit is not None else None,
            "unassignedMonthlyCost": round(unassigned * unit, 2) if unit is not None else None,
            "onDisabledAccounts": len(holders),
            "inactive90Plus": sum(
                1 for f in findings["inactive"]
                if part in f["skus"] and f["bucket"] in ("90+", "never")
            ),
            "webOnly": sum(1 for f in findings["webOnlyDesktopSuite"] if part in f["skus"])
            if part in DESKTOP_SUITES else 0,
        })
    sku_rows.sort(key=lambda r: r["monthlyCost"] or 0, reverse=True)

    # --- renewals ---
    renewals = []
    for sub in data.get("subscriptions") or []:
        when = _parse_dt(sub.get("nextLifecycleDateTime"))
        if not when:
            continue
        days = (when - now).days
        if days <= RENEWAL_WINDOW_DAYS or sub.get("isTrial"):
            renewals.append({
                "sku": sub.get("skuPartNumber"),
                "name": names.get(sub.get("skuPartNumber"), sub.get("skuPartNumber")),
                "status": sub.get("status"),
                "isTrial": sub.get("isTrial"),
                "totalLicenses": sub.get("totalLicenses"),
                "date": when.date().isoformat(),
                "daysAway": days,
            })
    renewals.sort(key=lambda r: r["daysAway"])

    # --- totals ---
    priced = [r for r in sku_rows if r["monthlyCost"] is not None]
    # Free/viral SKUs show up with 10,000+ "seats"; unpriced paid SKUs still count.
    paid = [r for r in sku_rows if r["unitPrice"] != 0 and r["purchased"] < FREE_SKU_SEATS]
    monthly = round(sum(r["monthlyCost"] for r in priced), 2)
    unassigned_waste = round(sum(r["unassignedMonthlyCost"] for r in priced), 2)
    at_risk = round(sum(
        f["monthlyCost"] for f in findings["inactive"]
        if f["bucket"] in ("90+", "never")
        and f["userPrincipalName"].lower() not in waste_users
    ), 2)

    gaps = list(data.get("warnings") or [])
    if _reports_concealed(reports):
        gaps.append(
            "Usage reports are anonymized, so usage can't be matched to users. Turn off "
            "'Display concealed user, group, and site names' in Admin center > Settings > "
            "Org settings > Reports."
        )
    gaps += (data.get("billing") or {}).get("warnings", [])
    if unmatched_billing:
        gaps.append(
            "Billing subscriptions not matched to a license: " + ", ".join(unmatched_billing)
        )
    unpriced = [r["sku"] for r in sku_rows if r["unitPrice"] is None and r["assigned"]]
    if unpriced:
        gaps.append(f"No price set for: {', '.join(unpriced)} (add to prices.json)")

    org = (data.get("organization") or [{}])[0]
    return {
        "tenant": org.get("displayName"),
        "generatedAt": now.isoformat(),
        "currency": currency,
        "totals": {
            "seatsPurchased": sum(r["purchased"] for r in paid),
            "seatsAssigned": sum(r["assigned"] for r in paid),
            "monthlySpend": monthly,
            "annualSpend": round(monthly * 12, 2),
            "confirmedWasteMonthly": round(unassigned_waste + sum(waste_users.values()), 2),
            "atRiskMonthly": at_risk,
        },
        "skus": sku_rows,
        "findings": findings,
        "renewals": renewals,
        "dataGaps": gaps,
    }
