# License Project

License consumption dashboard. Phase 1 is a **read-only probe** for Microsoft 365: it pulls
licenses, assignments, sign-in and usage data from Microsoft Graph, prices them, and reports
spend and waste. See [SCOPE.md](SCOPE.md) for the product plan.

## 1. Register the app in Entra (one time, ~10 minutes)

1. **Create a certificate** (on your laptop):
   ```bash
   mkdir -p certs
   openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
     -keyout certs/key.pem -out certs/cert.pem -subj "/CN=license-probe"
   cat certs/key.pem certs/cert.pem > certs/license-probe.pem
   ```
2. **Entra admin center → App registrations → New registration.** Name it `license-probe`,
   single tenant, no redirect URI. Copy the **Application (client) ID** and **Directory (tenant) ID**.
3. **Certificates & secrets → Certificates → Upload** `certs/cert.pem`.
4. **API permissions → Add → Microsoft Graph → Application permissions**, all read-only:

   | Permission | Used for |
   |---|---|
   | `Organization.Read.All` | Purchased licenses (`subscribedSkus`), tenant name |
   | `LicenseAssignment.Read.All` | Subscriptions and renewal dates |
   | `User.Read.All` | Who holds which license, account status |
   | `Group.Read.All` | Group-based licensing |
   | `AuditLog.Read.All` | Last sign-in (needs Entra ID P1 in the tenant) |
   | `Reports.Read.All` | Usage reports (activity, desktop vs. web apps, mailbox type) |

5. Click **Grant admin consent**.
6. **Un-hide report names:** Microsoft 365 admin center → Settings → Org settings → Reports →
   uncheck *Display concealed user, group, and site names*. Without this, usage can't be
   matched to users (the probe will warn you).

## 1b. Optional: real prices from billing (Microsoft Customer Agreement)

Graph has no pricing. With read-only access to the billing account, the probe reads each
subscription's actual charges. Billing roles can't be given to an app in the portal UI, so
run this once in **Azure Cloud Shell** (portal.azure.com → `>_` → Bash), set `APP_ID` to your
Application (client) ID:

```bash
APP_ID=<application-client-id>
API=2019-10-01-preview
SP_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
TENANT=$(az account show --query tenantId -o tsv)
ACCT=$(az rest --method get --url "https://management.azure.com/providers/Microsoft.Billing/billingAccounts?api-version=2024-04-01" --query "value[0].name" -o tsv)
ROLE=$(az rest --method get --url "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/$ACCT/billingRoleDefinitions?api-version=$API" --query "value[?properties.roleName=='Billing account reader'].id | [0]" -o tsv)
echo "app=$SP_ID account=$ACCT role=$ROLE"
az rest --method put --url "https://management.azure.com/providers/Microsoft.Billing/billingAccounts/$ACCT/billingRoleAssignments/$(cat /proc/sys/kernel/random/uuid)?api-version=$API" --body "{\"properties\":{\"principalId\":\"$SP_ID\",\"principalTenantId\":\"$TENANT\",\"roleDefinitionId\":\"$ROLE\"}}"
```

Without it the probe still runs and uses list prices.

## Prices

Each product's price comes from the first of:
1. **override:** `prices.json` (yours, not committed): same format as `prices.example.json`,
   only the SKUs you want to set
2. **invoice:** last month's charges ÷ seats, from the billing account
3. **list:** `prices.example.json`

The dashboard shows which one was used.

## 2. Run the probe

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in TENANT_ID, CLIENT_ID, CERT_PATH
python probe.py
```

Output goes to `output/<timestamp>/`:
- `executive-report.html`: **the executive report**, two letter-size pages in plain language:
  annual spend, cost per employee, money going to unused licenses, ranked actions with
  savings and timing, upcoming decisions, and spend by category, department, and product.
  Add `--pdf` to also save it as PDF (needs `pip install playwright && playwright install chromium`;
  or open it in Chrome and Print → Save as PDF). Set `REPORT_PREPARED_BY` in `.env` to put
  your name on it.
- `dashboard.html`: **the IT dashboard** — open it in any browser. Self-contained (no server,
  no internet), so it can also be emailed to a client as the audit deliverable.
- `raw.json`: everything pulled from Graph (contains user names; keep private)
- `report.json`: the analysis (input for the dashboard later)
- `report.md`: human-readable summary

After changing prices, re-run the analysis without calling Graph again:
```bash
python probe.py --from output/<timestamp>
```

## Demo mode

`python probe.py --demo` builds the dashboard from a fake 150-person company
(`output/demo/dashboard.html`). Use it to show prospects what they'd get without touching
their tenant.

## What it reports

- **Totals:** monthly/annual spend, seats purchased vs. assigned, confirmed waste, spend at risk
- **By product:** bought, assigned, unassigned, price, monthly cost, holders on disabled accounts, inactive 90+, web-only users
- **Renewals and trials** in the next 90 days
- **Findings:** licensed disabled accounts, licensed guests, licensed shared mailboxes,
  inactive users (30/60/90+), overlapping suites, desktop suites used web-only,
  group-licensing errors
- **Data gaps:** missing permissions, anonymized reports, unpriced SKUs

**Confirmed waste** = unassigned seats + licenses on disabled, guest, and shared-mailbox
accounts (each user counted once). **At risk** = active accounts with no activity for 90+ days.

## Tests

```bash
pip install pytest && pytest
```
