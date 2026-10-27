from datetime import datetime, timezone

from licensecheck.analyze import analyze
from licensecheck.billing import collect_billing
from licensecheck.graph import GraphError
from test_analyze import NAMES, NOW, fixture

LIST = {"currency": "USD", "monthly_per_seat": {"SPE_E3": 36.0, "O365_BUSINESS_PREMIUM": 12.5}}
ACCT = "/providers/Microsoft.Billing/billingAccounts/a1"


def billed(*subs):
    return {"warnings": [], "accounts": [{
        "id": ACCT, "name": "Contoso", "agreementType": "MicrosoftCustomerAgreement",
        "billingSubscriptions": list(subs), "invoices": [],
    }]}


def bsub(name, charges, qty, label="Microsoft 365 E3"):
    return {"name": name, "properties": {
        "displayName": label, "quantity": qty,
        "lastMonthCharges": {"currency": "USD", "value": charges},
    }}


def with_billing(billing):
    data = fixture()
    data["subscriptions"][0]["commerceSubscriptionId"] = "C-E3"
    data["subscriptions"][1]["commerceSubscriptionId"] = "C-BS"
    data["billing"] = billing
    return data


def skus(result):
    return {s["sku"]: s for s in result["skus"]}


def test_invoice_price_beats_list_price():
    r = analyze(with_billing(billed(bsub("c-e3", 330.0, 10))), LIST, NAMES, now=NOW)
    e3 = skus(r)["SPE_E3"]
    assert (e3["unitPrice"], e3["priceSource"], e3["monthlyCost"]) == (33.0, "invoice", 330.0)
    assert skus(r)["O365_BUSINESS_PREMIUM"]["priceSource"] == "list"


def test_override_beats_invoice():
    prices = dict(LIST, overrides={"SPE_E3": 30.0})
    r = analyze(with_billing(billed(bsub("c-e3", 330.0, 10))), prices, NAMES, now=NOW)
    assert (skus(r)["SPE_E3"]["unitPrice"], skus(r)["SPE_E3"]["priceSource"]) == (30.0, "override")


def test_trial_without_charges_falls_back_and_unmatched_is_reported():
    r = analyze(
        with_billing(billed(bsub("c-e3", 0, 10), bsub("other", 50.0, 5, "Mystery Product"))),
        LIST, NAMES, now=NOW,
    )
    assert skus(r)["SPE_E3"]["priceSource"] == "list"
    assert any("Mystery Product" in g for g in r["dataGaps"])


def test_split_subscriptions_use_seat_weighted_price():
    data = with_billing(billed(bsub("c-e3", 360.0, 10), bsub("c-e3-2", 60.0, 2)))
    data["subscriptions"].append(dict(data["subscriptions"][0], commerceSubscriptionId="C-E3-2"))
    r = analyze(data, LIST, NAMES, now=NOW)
    assert skus(r)["SPE_E3"]["unitPrice"] == 35.0  # (360 + 60) / 12


class FakeArm:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_all(self, path, params=None):
        self.calls.append(path)
        result = self.responses[path.split("/")[-1]]
        if isinstance(result, Exception):
            raise result
        return result


def test_collect_billing_without_role_warns():
    arm = FakeArm({"billingAccounts": GraphError(403, "AuthorizationFailed", "no", "/x")})
    out = collect_billing(arm)
    assert out["accounts"] == [] and "Billing account" in out["warnings"][0]


def test_collect_billing_reads_mca_and_skips_other_agreements():
    arm = FakeArm({
        "billingAccounts": [
            {"id": ACCT, "name": "a1", "properties": {
                "displayName": "Contoso", "agreementType": "MicrosoftCustomerAgreement"}},
            {"id": "/x/ea", "name": "ea", "properties": {"agreementType": "EnterpriseAgreement"}},
        ],
        "billingSubscriptions": [bsub("c-e3", 330.0, 10)],
        "invoices": [{"name": "INV-1"}],
    })
    out = collect_billing(arm, now=datetime(2026, 10, 27, tzinfo=timezone.utc))
    mca = out["accounts"][0]
    assert len(mca["billingSubscriptions"]) == 1 and mca["invoices"] == [{"name": "INV-1"}]
    assert out["accounts"][1]["billingSubscriptions"] == []
    assert any("EnterpriseAgreement" in w for w in out["warnings"])
