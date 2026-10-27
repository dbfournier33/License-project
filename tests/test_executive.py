from datetime import datetime, timezone

from licensecheck.analyze import analyze
from licensecheck.demo import demo_data
from licensecheck.executive import category, executive_summary
from licensecheck.report import to_report_html

NOW = datetime(2026, 10, 27, tzinfo=timezone.utc)
LIST = {
    "currency": "USD",
    "monthly_per_seat": {
        "SPE_E3": 36.0, "SPE_E5": 57.0, "O365_BUSINESS_PREMIUM": 12.5, "SPE_F1": 8.0,
        "POWER_BI_PRO": 14.0, "VISIOCLIENT": 15.0, "PROJECTPROFESSIONAL": 30.0,
        "Microsoft_365_Copilot": 30.0, "FLOW_FREE": 0, "O365_BUSINESS_ESSENTIALS": 6.0,
    },
}


def build():
    data = demo_data(now=NOW)
    result = analyze(data, LIST, {}, now=NOW)
    return data, result, executive_summary(result, data, LIST["monthly_per_seat"])


def test_totals_reconcile():
    _, result, s = build()
    assert s["annualSpend"] == round(result["totals"]["monthlySpend"] * 12, 2)
    assert abs(sum(c["annual"] for c in s["categories"]) - s["annualSpend"]) < 1
    assert abs(sum(d["annual"] for d in s["departments"]) - s["annualSpend"]) < 1
    assert s["employees"] > 0 and s["perEmployee"] == round(s["annualSpend"] / s["employees"], 2)


def test_actions_are_plain_sorted_and_deduplicated():
    _, result, s = build()
    savings = [a["savingsAnnual"] or 0 for a in s["actions"]]
    assert savings == sorted(savings, reverse=True)
    f = result["findings"]
    leavers = {r["userPrincipalName"] for k in ("disabledLicensed", "guestLicensed",
                                                 "sharedMailboxLicensed") for r in f[k]}
    leaver_action = next(a for a in s["actions"] if a["title"].startswith("Remove licenses"))
    assert leaver_action["count"] == len(leavers)  # shared mailbox is also disabled: counted once
    for a in s["actions"]:
        assert "SPE_" not in a["title"] and "SPE_" not in a["why"]  # no SKU codes for executives


def test_trial_and_renewal_deadlines():
    _, _, s = build()
    whats = [d["what"] for d in s["deadlines"]]
    assert any("trial ends" in w for w in whats)
    assert any("renews" in w for w in whats)


def test_categories():
    assert category("Microsoft_365_Copilot") == "AI (Copilot)"
    assert category("BUSINESS_STANDARD_AND_COPILOT_FOR_BUSINESS") == "AI (Copilot)"
    assert category("SPE_E3") == "Email & Office"
    assert category("MDE_SMB") == "Security"
    assert category("POWER_BI_PRO") == "Analytics (Power BI)"


def test_report_escapes_and_renders():
    data, result, s = build()
    s["tenant"] = '<script>alert(1)</script>'
    s["departments"][0]["name"] = "<img src=x>"
    html = to_report_html(s, result, prepared_by="Descry & Co")
    assert "<script>" not in html and "<img src=x>" not in html
    assert "Descry &amp; Co" in html and "What to do" in html
