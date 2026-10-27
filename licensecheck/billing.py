"""Pull billing data (Microsoft Customer Agreement) from Azure Resource Manager, read-only.

Needs the app to hold a billing role (e.g. Billing account reader) on the billing account;
Graph consent does not cover billing. Missing access becomes a warning, never a failure.
"""

from datetime import datetime, timedelta, timezone

from .graph import GraphError

API = "2024-04-01"
INVOICE_LOOKBACK_DAYS = 365


def collect_billing(arm, now=None):
    now = now or datetime.now(timezone.utc)
    out = {"warnings": [], "accounts": []}
    try:
        accounts = arm.get_all("/providers/Microsoft.Billing/billingAccounts", {"api-version": API})
    except GraphError as e:
        out["warnings"].append(
            f"Billing not accessible ({e.code or e.status}). Give the app the 'Billing account "
            "reader' role on the billing account to use invoice prices."
        )
        return out
    if not accounts:
        out["warnings"].append(
            "No billing accounts visible to the app. Give it the 'Billing account reader' role "
            "to use invoice prices (see README)."
        )

    for acct in accounts:
        props = acct.get("properties") or {}
        entry = {
            "id": acct.get("id"),
            "name": props.get("displayName") or acct.get("name"),
            "agreementType": props.get("agreementType"),
            "billingSubscriptions": [],
            "invoices": [],
        }
        out["accounts"].append(entry)
        if props.get("agreementType") != "MicrosoftCustomerAgreement":
            out["warnings"].append(
                f"Billing account '{entry['name']}' is {entry['agreementType']}; "
                "only Microsoft Customer Agreement billing is supported so far."
            )
            continue
        try:
            entry["billingSubscriptions"] = arm.get_all(
                f"{acct['id']}/billingSubscriptions", {"api-version": API}
            )
        except GraphError as e:
            out["warnings"].append(f"billingSubscriptions for '{entry['name']}': {e}")
        try:
            entry["invoices"] = arm.get_all(
                f"{acct['id']}/invoices",
                {
                    "api-version": API,
                    "periodStartDate": (now - timedelta(days=INVOICE_LOOKBACK_DAYS)).date().isoformat(),
                    "periodEndDate": now.date().isoformat(),
                },
            )
        except GraphError as e:
            out["warnings"].append(f"invoices for '{entry['name']}': {e}")
    return out


def invoice_prices(billing, graph_subscriptions):
    """skuPartNumber -> {"price", "currency", "detail"} from billing subscriptions.

    Billing subscriptions are joined to Graph's /directory/subscriptions on the commerce
    subscription id, which is what links a tenant's licenses to the billing account.
    Monthly unit price = last month's charges / quantity.
    """
    by_commerce_id = {
        (s.get("commerceSubscriptionId") or "").lower(): s.get("skuPartNumber")
        for s in graph_subscriptions or []
        if s.get("commerceSubscriptionId")
    }
    prices, unmatched = {}, []
    for acct in (billing or {}).get("accounts", []):
        for bs in acct.get("billingSubscriptions", []):
            props = bs.get("properties") or {}
            keys = {(bs.get("name") or "").lower(), (props.get("subscriptionId") or "").lower()}
            part = next((by_commerce_id[k] for k in keys if k in by_commerce_id), None)
            charges = (props.get("lastMonthCharges") or {}).get("value")
            qty = props.get("quantity")
            label = props.get("displayName") or props.get("skuDescription") or bs.get("name")
            if not part:
                unmatched.append(label)
                continue
            if not charges or not qty:
                continue  # trials and brand-new subscriptions have no charges yet
            unit = round(charges / qty, 2)
            # Several billing subscriptions can carry one SKU; keep the seat-weighted price.
            prev = prices.get(part)
            if prev:
                total_qty = prev["quantity"] + qty
                unit = round((prev["price"] * prev["quantity"] + charges) / total_qty, 2)
                qty = total_qty
            prices[part] = {
                "price": unit,
                "quantity": qty,
                "currency": (props.get("lastMonthCharges") or {}).get("currency"),
                "detail": label,
            }
    return prices, unmatched
