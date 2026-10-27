from datetime import datetime, timezone

from licensecheck.analyze import analyze
from licensecheck.render import to_markdown

NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)
E3 = "sku-e3"
BS = "sku-bs"
FREE = "sku-free"

PRICES = {"currency": "USD", "monthly_per_seat": {"SPE_E3": 36.0, "O365_BUSINESS_PREMIUM": 12.5}}
NAMES = {"SPE_E3": "Microsoft 365 E3"}


def user(upn, skus, enabled=True, last_sign_in="2026-10-20T00:00:00Z", **extra):
    return {
        "displayName": upn.split("@")[0],
        "userPrincipalName": upn,
        "accountEnabled": enabled,
        "userType": "Member",
        "createdDateTime": "2024-01-01T00:00:00Z",
        "assignedLicenses": [{"skuId": s} for s in skus],
        "licenseAssignmentStates": [],
        "signInActivity": {"lastSignInDateTime": last_sign_in},
        **extra,
    }


def fixture():
    return {
        "organization": [{"displayName": "Contoso"}],
        "subscribedSkus": [
            {"skuId": E3, "skuPartNumber": "SPE_E3", "consumedUnits": 6,
             "prepaidUnits": {"enabled": 10, "suspended": 0, "warning": 0}},
            {"skuId": BS, "skuPartNumber": "O365_BUSINESS_PREMIUM", "consumedUnits": 1,
             "prepaidUnits": {"enabled": 1, "suspended": 0, "warning": 0}},
            {"skuId": FREE, "skuPartNumber": "FLOW_FREE", "consumedUnits": 3,
             "prepaidUnits": {"enabled": 10000, "suspended": 0, "warning": 0}},
        ],
        "subscriptions": [
            {"skuPartNumber": "SPE_E3", "status": "Enabled", "isTrial": False,
             "totalLicenses": 10, "nextLifecycleDateTime": "2026-12-01T00:00:00Z"},
            {"skuPartNumber": "O365_BUSINESS_PREMIUM", "status": "Enabled", "isTrial": False,
             "totalLicenses": 1, "nextLifecycleDateTime": "2027-09-01T00:00:00Z"},
        ],
        "signInAvailable": True,
        "users": [
            user("active@c.com", [E3]),
            user("leaver@c.com", [E3], enabled=False),
            user("stale@c.com", [E3], last_sign_in="2026-06-01T00:00:00Z"),
            user("never@c.com", [E3], last_sign_in=None),
            user("double@c.com", [E3, BS]),
            user("web@c.com", [E3]),
            user("newhire@c.com", [E3], last_sign_in=None, createdDateTime="2026-10-20T00:00:00Z"),
            user("guest@ext.com", [E3], userType="Guest"),
            user("nolicense@c.com", []),
            user("broken@c.com", [], licenseAssignmentStates=[
                {"skuId": E3, "state": "Error", "error": "CountViolation", "assignedByGroup": "g1"}
            ]),
        ],
        "reports": {
            "appUsage": [
                {"User Principal Name": "web@c.com", "Windows": "No", "Mac": "No", "Web": "Yes"},
                {"User Principal Name": "active@c.com", "Windows": "Yes", "Mac": "No", "Web": "Yes"},
            ],
            "mailboxUsage": [],
            "activeUsers": [],
        },
        "warnings": [],
    }


def upns(rows):
    return sorted(r["userPrincipalName"] for r in rows)


def test_findings():
    r = analyze(fixture(), PRICES, NAMES, now=NOW)
    f = r["findings"]
    assert upns(f["disabledLicensed"]) == ["leaver@c.com"]
    assert upns(f["guestLicensed"]) == ["guest@ext.com"]
    assert upns(f["overlappingSuites"]) == ["double@c.com"]
    assert f["overlappingSuites"][0]["redundant"] == ["O365_BUSINESS_PREMIUM"]
    assert upns(f["webOnlyDesktopSuite"]) == ["web@c.com"]
    assert upns(f["assignmentErrors"]) == ["broken@c.com"]
    inactive = {x["userPrincipalName"]: x["bucket"] for x in f["inactive"]}
    assert inactive == {"stale@c.com": "90+", "never@c.com": "never"}  # new hire excluded


def test_totals_and_skus():
    r = analyze(fixture(), PRICES, NAMES, now=NOW)
    t = r["totals"]
    assert t["monthlySpend"] == 10 * 36 + 12.5
    assert (t["seatsPurchased"], t["seatsAssigned"]) == (11, 7)  # free SKU excluded
    # 4 unassigned E3 + leaver E3 + guest E3
    assert t["confirmedWasteMonthly"] == 4 * 36 + 36 + 36
    # stale + never, neither already counted as waste
    assert t["atRiskMonthly"] == 72
    e3 = r["skus"][0]
    assert (e3["name"], e3["unassigned"], e3["onDisabledAccounts"], e3["inactive90Plus"]) == (
        "Microsoft 365 E3", 4, 1, 2
    )
    assert [x["sku"] for x in r["renewals"]] == ["SPE_E3"]
    assert any("FLOW_FREE" in g for g in r["dataGaps"])  # unpriced but assigned


def test_concealed_reports_flagged():
    data = fixture()
    data["reports"]["appUsage"] = [
        {"User Principal Name": "0F3A9C2B7D5E4F1A", "Windows": "No", "Mac": "No", "Web": "Yes"}
    ]
    r = analyze(data, PRICES, NAMES, now=NOW)
    assert any("anonymized" in g for g in r["dataGaps"])
    assert r["findings"]["webOnlyDesktopSuite"] == []


def test_no_activity_source_skips_inactivity():
    data = fixture()
    data["signInAvailable"] = False
    for u in data["users"]:
        u.pop("signInActivity")
    r = analyze(data, PRICES, NAMES, now=NOW)
    assert r["findings"]["inactive"] == []


def test_markdown_renders():
    md = to_markdown(analyze(fixture(), PRICES, NAMES, now=NOW))
    assert "Confirmed waste" in md and "Microsoft 365 E3" in md
