import json
import re

from licensecheck.analyze import analyze
from licensecheck.dashboard import to_html
from licensecheck.demo import demo_data

PRICES = {"currency": "USD", "monthly_per_seat": {"SPE_E3": 36.0}}


def embedded(html):
    return json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S).group(1))


def test_hostile_names_cannot_break_out_of_script():
    data = demo_data(people=3)
    data["users"][0]["displayName"] = '</script><img src=x onerror=alert(1)>'
    data["organization"][0]["displayName"] = '<b>"Evil"</b>'
    html = to_html(analyze(data, PRICES, {}))
    assert html.count("</script>") == 2  # only our own two closing tags
    assert "<title>License dashboard — &lt;b&gt;&quot;Evil&quot;&lt;/b&gt;</title>" in html
    payload = embedded(html)
    assert payload["result"]["tenant"] == '<b>"Evil"</b>'


def test_web_only_counted_only_on_desktop_suites():
    r = analyze(demo_data(), {"currency": "USD", "monthly_per_seat": {}}, {})
    by_sku = {s["sku"]: s["webOnly"] for s in r["skus"]}
    assert by_sku["SPE_E3"] > 0
    assert by_sku["SPE_F1"] == by_sku["POWER_BI_PRO"] == by_sku["FLOW_FREE"] == 0


def test_demo_produces_every_finding_type():
    r = analyze(demo_data(), {"currency": "USD", "monthly_per_seat": {}}, {})
    for key, rows in r["findings"].items():
        assert rows, f"demo data should exercise {key}"
