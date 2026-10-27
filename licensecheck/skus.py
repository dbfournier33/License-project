"""SKU part number -> friendly name, plus the groupings the waste checks rely on."""

import csv
import os

import requests

SKU_CSV_URL = (
    "https://download.microsoft.com/download/e/3/e/e3e9faf2-f28b-490a-9ada-c6089a1fc5b0/"
    "Product%20names%20and%20service%20plan%20identifiers%20for%20licensing.csv"
)

# Fallback when Microsoft's CSV can't be downloaded.
FALLBACK_NAMES = {
    "O365_BUSINESS_ESSENTIALS": "Microsoft 365 Business Basic",
    "O365_BUSINESS_PREMIUM": "Microsoft 365 Business Standard",
    "SPB": "Microsoft 365 Business Premium",
    "O365_BUSINESS": "Microsoft 365 Apps for business",
    "OFFICESUBSCRIPTION": "Microsoft 365 Apps for enterprise",
    "STANDARDPACK": "Office 365 E1",
    "ENTERPRISEPACK": "Office 365 E3",
    "ENTERPRISEPREMIUM": "Office 365 E5",
    "SPE_E3": "Microsoft 365 E3",
    "SPE_E5": "Microsoft 365 E5",
    "SPE_F1": "Microsoft 365 F3",
    "DESKLESSPACK": "Office 365 F3",
    "EXCHANGESTANDARD": "Exchange Online (Plan 1)",
    "EXCHANGEENTERPRISE": "Exchange Online (Plan 2)",
    "POWER_BI_PRO": "Power BI Pro",
    "POWER_BI_STANDARD": "Microsoft Fabric (Free)",
    "FLOW_FREE": "Microsoft Power Automate Free",
    "TEAMS_EXPLORATORY": "Microsoft Teams Exploratory",
    "VISIOCLIENT": "Visio Plan 2",
    "PROJECTPROFESSIONAL": "Project Plan 3",
    "AAD_PREMIUM": "Microsoft Entra ID P1",
    "AAD_PREMIUM_P2": "Microsoft Entra ID P2",
    "Microsoft_365_Copilot": "Microsoft 365 Copilot",
    "MDE_SMB": "Microsoft Defender for Business",
    "BUSINESS_STANDARD_AND_COPILOT_FOR_BUSINESS": "Microsoft 365 Business Standard + Copilot Business",
}

# Base productivity suites: one user normally needs only one of these.
BASE_SUITES = {
    "O365_BUSINESS_ESSENTIALS", "O365_BUSINESS_PREMIUM", "SPB",
    "STANDARDPACK", "ENTERPRISEPACK", "ENTERPRISEPREMIUM",
    "SPE_E3", "SPE_E5", "SPE_F1", "DESKLESSPACK",
}

# Suites that include desktop Office apps; web-only users of these may be over-licensed.
DESKTOP_SUITES = {
    "O365_BUSINESS", "OFFICESUBSCRIPTION", "O365_BUSINESS_PREMIUM", "SPB",
    "ENTERPRISEPACK", "ENTERPRISEPREMIUM", "SPE_E3", "SPE_E5",
}


def load_names(cache_path):
    """Friendly names from Microsoft's CSV (cached), falling back to the built-in map."""
    names = dict(FALLBACK_NAMES)
    if not os.path.exists(cache_path):
        try:
            resp = requests.get(SKU_CSV_URL, timeout=30)
            resp.raise_for_status()
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "wb") as f:
                f.write(resp.content)
        except requests.RequestException:
            return names
    with open(cache_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("String_Id") and row.get("Product_Display_Name"):
                names[row["String_Id"]] = row["Product_Display_Name"]
    return names
