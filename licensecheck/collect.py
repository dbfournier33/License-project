"""Pull every license-relevant dataset from a tenant. Missing permissions become warnings."""

from .graph import GraphError

USER_FIELDS = [
    "id", "displayName", "userPrincipalName", "mail", "accountEnabled", "userType",
    "department", "jobTitle", "createdDateTime", "assignedLicenses",
    "licenseAssignmentStates",
]

REPORTS = {
    "activeUsers": "/reports/getOffice365ActiveUserDetail(period='D30')",
    "appUsage": "/reports/getM365AppUserDetail(period='D30')",
    "mailboxUsage": "/reports/getMailboxUsageDetail(period='D30')",
}


def _try(warnings, label, fn):
    try:
        return fn()
    except GraphError as e:
        warnings.append(f"{label}: {e}")
        return None


def collect(client):
    warnings = []
    data = {"warnings": warnings}

    data["organization"] = _try(warnings, "organization", lambda: client.get_all("/organization"))
    data["subscribedSkus"] = _try(warnings, "subscribedSkus", lambda: client.get_all("/subscribedSkus"))
    data["subscriptions"] = _try(
        warnings, "subscriptions", lambda: client.get_all("/directory/subscriptions")
    )

    # signInActivity needs AuditLog.Read.All and Entra ID P1; fall back without it.
    try:
        data["users"] = client.get_all(
            "/users", {"$select": ",".join(USER_FIELDS + ["signInActivity"])}
        )
        data["signInAvailable"] = True
    except GraphError as e:
        warnings.append(
            "signInActivity unavailable (needs AuditLog.Read.All and Entra ID P1): "
            f"{e.code or e.status}"
        )
        data["users"] = _try(
            warnings, "users", lambda: client.get_all("/users", {"$select": ",".join(USER_FIELDS)})
        )
        data["signInAvailable"] = False

    # Filtering on assignedLicenses server-side needs advanced query headers; filter here.
    groups = _try(
        warnings,
        "licensedGroups",
        lambda: client.get_all("/groups", {"$select": "id,displayName,assignedLicenses"}),
    )
    data["licensedGroups"] = [g for g in groups or [] if g.get("assignedLicenses")]

    data["reports"] = {}
    for name, path in REPORTS.items():
        data["reports"][name] = _try(warnings, f"report {name}", lambda p=path: client.get_report_csv(p))

    return data
