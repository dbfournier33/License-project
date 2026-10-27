"""Deterministic fake tenant in the same shape collect() returns — for demos and visual testing."""

import random
from datetime import datetime, timedelta, timezone

FIRST = ["Alex", "Jordan", "Sam", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Drew", "Avery",
         "Quinn", "Reese", "Parker", "Rowan", "Skyler", "Dana", "Emerson", "Hayden", "Kendall", "Logan"]
LAST = ["Nguyen", "Garcia", "Smith", "Patel", "Kim", "Brown", "Lopez", "Walker", "Young", "Hall",
        "Rivera", "Clark", "Lewis", "Allen", "King", "Wright", "Scott", "Green", "Baker", "Adams"]
DEPTS = ["Engineering", "Sales", "Finance", "Operations", "Marketing", "HR", "Field Services"]

# (skuPartNumber, purchased)
SKUS = [
    ("SPE_E3", 120), ("SPE_E5", 15), ("O365_BUSINESS_PREMIUM", 10), ("SPE_F1", 25),
    ("POWER_BI_PRO", 30), ("VISIOCLIENT", 8), ("PROJECTPROFESSIONAL", 6),
    ("Microsoft_365_Copilot", 20), ("FLOW_FREE", 10000),
]


def demo_data(now=None, seed=7, people=150):
    rng = random.Random(seed)
    now = now or datetime.now(timezone.utc)
    iso = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    ids = {part: f"00000000-0000-0000-0000-{i:012d}" for i, (part, _) in enumerate(SKUS)}

    users, assigned, app_rows, mailbox_rows = [], {p: 0 for p, _ in SKUS}, [], []

    def give(lic, part):
        lic.append({"skuId": ids[part]})
        assigned[part] += 1

    for i in range(people):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        upn = f"{first}.{last}{i}@contoso-demo.com".lower()
        dept = rng.choice(DEPTS)
        enabled = rng.random() > 0.06
        lic = []
        if dept == "Field Services":
            give(lic, "SPE_F1")
        elif i < 14:
            give(lic, "SPE_E5")
        else:
            give(lic, "SPE_E3")
        if i % 17 == 3:
            give(lic, "O365_BUSINESS_PREMIUM")  # overlap
        if dept in ("Finance", "Operations") and rng.random() < 0.6:
            give(lic, "POWER_BI_PRO")
        if dept == "Engineering" and rng.random() < 0.15:
            give(lic, rng.choice(["VISIOCLIENT", "PROJECTPROFESSIONAL"]))
        if rng.random() < 0.12 and assigned["Microsoft_365_Copilot"] < 18:
            give(lic, "Microsoft_365_Copilot")
        if rng.random() < 0.3:
            give(lic, "FLOW_FREE")

        r = rng.random()
        last_seen = None if r < 0.03 else now - timedelta(days=rng.choice(
            [1, 2, 3, 5, 8] if r > 0.15 else [35, 70, 120, 200]))
        users.append({
            "id": f"u{i}", "displayName": f"{first} {last}", "userPrincipalName": upn,
            "accountEnabled": enabled, "userType": "Member", "department": dept,
            "createdDateTime": iso(now - timedelta(days=rng.randint(40, 1500))),
            "assignedLicenses": lic, "licenseAssignmentStates": [],
            "signInActivity": {"lastSignInDateTime": iso(last_seen) if last_seen else None},
        })
        desktop = dept not in ("Field Services",) and rng.random() > 0.2
        app_rows.append({"User Principal Name": upn, "Windows": "Yes" if desktop else "No",
                         "Mac": "No", "Web": "Yes", "Mobile": "Yes"})

    # A licensed shared mailbox, a licensed guest, and a group-licensing error.
    for upn, name, extra in [
        ("accounting@contoso-demo.com", "Accounting (shared)", {"accountEnabled": False}),
        ("vendor_ext#EXT#@contoso-demo.com", "Vendor Contractor", {"userType": "Guest"}),
    ]:
        lic = []
        give(lic, "SPE_E3")
        users.append({"id": upn, "displayName": name, "userPrincipalName": upn,
                      "accountEnabled": True, "userType": "Member",
                      "createdDateTime": iso(now - timedelta(days=400)),
                      "assignedLicenses": lic, "licenseAssignmentStates": [],
                      "signInActivity": {"lastSignInDateTime": iso(now - timedelta(days=2))}, **extra})
    mailbox_rows.append({"User Principal Name": "accounting@contoso-demo.com", "Recipient Type": "Shared"})
    users.append({"id": "err", "displayName": "Pat Error", "userPrincipalName": "pat.error@contoso-demo.com",
                  "accountEnabled": True, "userType": "Member", "createdDateTime": iso(now - timedelta(days=90)),
                  "assignedLicenses": [], "licenseAssignmentStates": [
                      {"skuId": ids["POWER_BI_PRO"], "state": "Error", "error": "CountViolation",
                       "assignedByGroup": "BI Users"}]})

    return {
        "warnings": [],
        "organization": [{"displayName": "Contoso Demo Co."}],
        "subscribedSkus": [
            {"skuId": ids[p], "skuPartNumber": p, "consumedUnits": assigned[p],
             "prepaidUnits": {"enabled": max(n, assigned[p]), "suspended": 0, "warning": 0}}
            for p, n in SKUS
        ],
        "subscriptions": [
            {"skuPartNumber": "SPE_E3", "status": "Enabled", "isTrial": False, "totalLicenses": 120,
             "nextLifecycleDateTime": iso(now + timedelta(days=41))},
            {"skuPartNumber": "Microsoft_365_Copilot", "status": "Enabled", "isTrial": True,
             "totalLicenses": 20, "nextLifecycleDateTime": iso(now + timedelta(days=12))},
            {"skuPartNumber": "SPE_E5", "status": "Enabled", "isTrial": False, "totalLicenses": 15,
             "nextLifecycleDateTime": iso(now + timedelta(days=210))},
        ],
        "signInAvailable": True,
        "users": users,
        "licensedGroups": [],
        "reports": {"activeUsers": [], "appUsage": app_rows, "mailboxUsage": mailbox_rows},
    }
