#!/usr/bin/env python3
"""Phase 1 probe: pull M365 license data read-only, save it, and summarize spend and waste.

Usage:
    python probe.py                     # pull from the tenant in .env, analyze, write output/
    python probe.py --from output/X     # re-analyze a saved raw.json (e.g. after editing prices)
    python probe.py --demo              # fake tenant, for demos (writes output/demo/)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from licensecheck.analyze import analyze
from licensecheck.dashboard import to_html
from licensecheck.render import to_markdown
from licensecheck.skus import load_names

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env(path):
    """Tiny .env reader so we don't need another dependency."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"'))


def load_prices():
    """List prices from prices.example.json, plus your overrides from prices.json."""
    with open(os.path.join(HERE, "prices.example.json")) as f:
        prices = json.load(f)
    override_path = os.path.join(HERE, "prices.json")
    if os.path.exists(override_path):
        with open(override_path) as f:
            prices["overrides"] = json.load(f).get("monthly_per_seat", {})
    return prices


def pull():
    from licensecheck.billing import collect_billing
    from licensecheck.collect import collect
    from licensecheck.graph import ARM, ARM_SCOPE, GraphClient

    load_env(os.path.join(HERE, ".env"))
    missing = [k for k in ("TENANT_ID", "CLIENT_ID") if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing {', '.join(missing)} — copy .env.example to .env and fill it in.")
    cert_path = os.environ.get("CERT_PATH")
    if cert_path:
        # Relative paths are relative to this project, not wherever you ran from.
        cert_path = os.path.join(HERE, os.path.expanduser(cert_path))
        if not os.path.exists(cert_path):
            sys.exit(
                f"Certificate not found: {cert_path}\n"
                "Set CERT_PATH in .env to the combined key+cert PEM, e.g. ./certs/license-probe.pem"
            )
    creds = dict(cert_path=cert_path, client_secret=os.environ.get("CLIENT_SECRET"))
    graph = GraphClient(os.environ["TENANT_ID"], os.environ["CLIENT_ID"], **creds)
    arm = GraphClient(
        os.environ["TENANT_ID"], os.environ["CLIENT_ID"], base=ARM, scope=ARM_SCOPE, **creds
    )
    print("Pulling from Microsoft Graph (read-only)...")
    data = collect(graph)
    print("Pulling billing (read-only)...")
    data["billing"] = collect_billing(arm)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from", dest="source", help="re-analyze a saved output directory")
    parser.add_argument("--demo", action="store_true", help="use a fake 150-person tenant")
    args = parser.parse_args()

    if args.demo:
        from licensecheck.demo import demo_data

        data = demo_data()
        out_dir = os.path.join(HERE, "output", "demo")
        os.makedirs(out_dir, exist_ok=True)
    elif args.source:
        out_dir = args.source
        with open(os.path.join(out_dir, "raw.json")) as f:
            data = json.load(f)
    else:
        data = pull()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = os.path.join(HERE, "output", stamp)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "raw.json"), "w") as f:
            json.dump(data, f, indent=2, default=str)

    prices = load_prices()
    names = load_names(os.path.join(HERE, "data", "sku_names.csv"))

    result = analyze(data, prices, names)
    markdown = to_markdown(result)
    with open(os.path.join(out_dir, "report.json"), "w") as f:
        json.dump(result, f, indent=2)
    with open(os.path.join(out_dir, "report.md"), "w") as f:
        f.write(markdown)
    with open(os.path.join(out_dir, "dashboard.html"), "w", encoding="utf-8") as f:
        f.write(to_html(result))

    print(markdown)
    print(f"Saved raw data and reports to {out_dir}")
    print(f"Open the dashboard: {os.path.join(out_dir, 'dashboard.html')}")


if __name__ == "__main__":
    main()
