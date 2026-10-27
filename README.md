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

## 2. Run the probe

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in TENANT_ID, CLIENT_ID, CERT_PATH
cp prices.example.json prices.json # optional: enter what you actually pay
python probe.py
```

Output goes to `output/<timestamp>/`:
- `raw.json`: everything pulled from Graph (contains user names; keep private)
- `report.json`: the analysis (input for the dashboard later)
- `report.md`: human-readable summary

After changing prices, re-run the analysis without calling Graph again:
```bash
python probe.py --from output/<timestamp>
```

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
