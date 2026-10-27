"""Executive report: a letter-size, print-ready HTML document (and PDF via a headless browser).

Rendered server-side with no JavaScript so the PDF matches the screen exactly.
"""

from datetime import datetime
from html import escape


def _money(value, currency, cents=False):
    if value is None:
        return "—"
    symbol = "$" if currency == "USD" else f"{currency} "
    return f"{symbol}{value:,.2f}" if cents else f"{symbol}{round(value):,}"


def _short_date(iso):
    if not iso:
        return ""
    d = datetime.fromisoformat(iso)
    return f"{d:%b} {d.day}, {d.year}"


def _bar(pct):
    return f'<span class="bar"><i style="width:{max(0, min(100, pct))}%"></i></span>'


def to_report_html(summary, result, prepared_by=None):
    s, cur = summary, summary["currency"]
    m = lambda v: _money(v, cur)  # noqa: E731
    e = lambda v: escape(str(v))  # noqa: E731
    when = datetime.fromisoformat(s["generatedAt"])
    savings = s["wasteConfirmedAnnual"] + s["wasteAtRiskAnnual"]

    actions = "".join(
        f"""<tr><td class="n">{i}</td><td><b>{e(a['title'])}</b><div class="why">{e(a['why'])}</div></td>
        <td class="num">{m(a['savingsAnnual']) if a['savingsAnnual'] is not None else 'Review'}</td>
        <td class="when">{e(a['when'])}</td></tr>"""
        for i, a in enumerate(s["actions"], 1)
    ) or '<tr><td colspan="4" class="why">No waste found. Licenses match how they are used.</td></tr>'

    deadlines = "".join(
        f"""<li><b>{e(d['date'])}</b> <span class="days {'urgent' if d['daysAway'] <= 30 else ''}">
        in {d['daysAway']} days</span><br>{e(d['what'])}</li>"""
        for d in s["deadlines"]
    )
    deadline_box = (
        f'<div class="callout"><h3>Decisions due soon</h3><ul>{deadlines}</ul></div>' if deadlines else ""
    )

    top = max((c["annual"] for c in s["categories"]), default=0) or 1
    categories = "".join(
        f"""<tr><td>{e(c['name'])}</td><td>{_bar(100 * c['annual'] / top)}</td>
        <td class="num">{m(c['annual'])}</td><td class="num muted">{c['pct']}%</td></tr>"""
        for c in s["categories"]
    )
    departments = "".join(
        f"""<tr><td>{e(d['name'])}</td><td class="num">{d['people'] or ''}</td>
        <td class="num">{m(d['annual'])}</td></tr>"""
        for d in s["departments"]
    )
    products = "".join(
        f"""<tr><td>{e(p['name'])}</td><td class="num">{p['assigned']} / {p['purchased']}</td>
        <td class="num">{m((p['monthlyCost'] or 0) * 12)}</td>
        <td class="when">{e(_short_date(p['renewalDate']))}</td></tr>"""
        for p in result["skus"]
        if (p["unitPrice"] or 0) > 0
    )
    notes = "".join(f"<li>{e(n)}</li>" for n in s["notes"])
    per_emp = (
        f'<div class="kpi"><div class="label">Per licensed employee</div>'
        f'<div class="value">{m(s["perEmployee"])}</div><div class="sub">per year, '
        f'{s["employees"]} people</div></div>' if s["perEmployee"] else ""
    )
    byline = f" · Prepared by {e(prepared_by)}" if prepared_by else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Microsoft 365 License Review — {e(s['tenant'] or '')}</title>
<style>
@page {{ size: Letter; margin: 0.6in; }}
:root {{ --ink: #17202b; --muted: #5d6b7b; --line: #dfe4ea; --accent: #1f4fbf; --bad: #b4342a;
  --warn: #9a5b00; --soft: #f3f6fa; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #e9edf2; color: var(--ink);
  font: 10.5pt/1.45 "Segoe UI", system-ui, -apple-system, Roboto, sans-serif; }}
.page {{ background: #fff; width: 8.5in; min-height: 11in; margin: 24px auto; padding: 0.6in;
  box-shadow: 0 1px 6px rgba(0,0,0,.12); }}
@media print {{ body {{ background: #fff; }} .page {{ margin: 0; padding: 0; width: auto;
  min-height: 0; box-shadow: none; page-break-after: always; }} .page:last-child {{ page-break-after: auto; }} }}
@media (max-width: 8.6in) {{ .page {{ width: auto; min-height: 0; margin: 0; padding: 20px 16px; }} }}
header {{ border-bottom: 3px solid var(--accent); padding-bottom: 8px; margin-bottom: 14px; }}
.eyebrow {{ color: var(--accent); font-weight: 700; letter-spacing: .08em; font-size: 8.5pt; text-transform: uppercase; }}
h1 {{ font-size: 20pt; margin: 2px 0; }} h2 {{ font-size: 12.5pt; margin: 18px 0 6px; }}
h3 {{ font-size: 10.5pt; margin: 0 0 6px; }}
.meta {{ color: var(--muted); font-size: 9pt; }}
.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; }}
.kpi {{ background: var(--soft); border-radius: 8px; padding: 10px 14px; }}
.kpi .label {{ color: var(--muted); font-size: 8.5pt; text-transform: uppercase; letter-spacing: .04em; }}
.kpi .value {{ font-size: 18pt; font-weight: 700; margin-top: 2px; }}
.kpi .sub {{ color: var(--muted); font-size: 9pt; }}
.kpi.bad .value {{ color: var(--bad); }}
.headline {{ font-size: 12pt; margin: 12px 0 2px; }}
.headline b {{ color: var(--bad); }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; font-size: 8.5pt; color: var(--muted); font-weight: 600; text-transform: uppercase;
  letter-spacing: .04em; border-bottom: 1.5px solid var(--ink); padding: 6px 8px; }}
td {{ border-bottom: 1px solid var(--line); padding: 6px 8px; vertical-align: top; }}
td.num, th.num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
td.n {{ color: var(--accent); font-weight: 700; width: 18px; }}
td.when {{ white-space: nowrap; color: var(--muted); }}
.why {{ color: var(--muted); font-size: 9pt; margin-top: 1px; line-height: 1.35; }}
.muted {{ color: var(--muted); }}
.callout {{ border: 1px solid var(--warn); border-left: 5px solid var(--warn); border-radius: 6px;
  padding: 8px 14px; margin-top: 12px; page-break-inside: avoid; }}
.callout ul {{ margin: 0; padding-left: 18px; }} .callout li {{ margin: 4px 0; }}
.days {{ color: var(--muted); }} .days.urgent {{ color: var(--bad); font-weight: 700; }}
.bar {{ display: inline-block; width: 100%; height: 9px; background: var(--soft); border-radius: 5px; }}
.bar i {{ display: block; height: 100%; background: var(--accent); border-radius: 5px; }}
.cols {{ display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 8fr); gap: 16px; }}
@media (max-width: 6in) {{ .cols {{ grid-template-columns: 1fr; }} td.when, td.num {{ white-space: normal; }}
  .kpi .value {{ font-size: 16pt; }} }}
tr {{ page-break-inside: avoid; }}
.prod td:first-child {{ white-space: nowrap; }}
.prod {{ font-size: 9pt; }} .prod td, .prod th {{ padding-left: 4px; padding-right: 4px; }}
.prod th {{ font-size: 7.5pt; }}
@media (max-width: 6in) {{ .prod td:first-child {{ white-space: normal; }} }}
ul.notes {{ padding-left: 18px; color: var(--muted); }} ul.notes li {{ margin: 4px 0; }}
@media print {{ .page {{ padding: 0; }} }}
</style></head>
<body>
<section class="page">
  <header>
    <div class="eyebrow">Microsoft 365 License Review</div>
    <h1>{e(s['tenant'] or 'Your organization')}</h1>
    <div class="meta">{when:%B} {when.day}, {when.year}{byline}</div>
  </header>

  <div class="kpis">
    <div class="kpi"><div class="label">Annual Microsoft 365 spend</div>
      <div class="value">{m(s['annualSpend'])}</div><div class="sub">{m(s['monthlySpend'])} per month</div></div>
    {per_emp}
    <div class="kpi bad"><div class="label">Paying for unused licenses</div>
      <div class="value">{m(savings)}</div><div class="sub">per year · {s['wastePct']}% of spend</div></div>
  </div>

  <p class="headline">{'We found <b>' + m(savings) + ' a year</b> in licenses that are not being used.' if savings else 'Your licenses match how they are used. No waste found.'}</p>

  {deadline_box}
  <h2>What to do</h2>
  <table>
    <tr><th></th><th>Action</th><th class="num">Saves / year</th><th>When</th></tr>
    {actions}
  </table>
</section>

<section class="page">
  <header><div class="eyebrow">Where the money goes</div><h1>Spend breakdown</h1></header>
  <h2>By category</h2>
  <table><tr><th>Category</th><th style="width:45%"></th><th class="num">Per year</th><th class="num">Share</th></tr>{categories}</table>
  <div class="cols">
    <div><h2>By department</h2>
      <table><tr><th>Department</th><th class="num">People</th><th class="num">Per year</th></tr>{departments}</table></div>
    <div><h2>By product</h2>
      <table class="prod"><tr><th>Product</th><th class="num">In use / paid</th><th class="num">Per year</th><th>Renews</th></tr>{products}</table></div>
  </div>
  <h2>About this review</h2>
  <ul class="notes">
    <li>Data was read directly from Microsoft 365 with read-only access. Nothing was changed.</li>
    {notes}
  </ul>
</section>
</body></html>
"""


def write_pdf(html_path, pdf_path):
    """Render the report to PDF with a headless browser. Returns False if Playwright is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("file://" + html_path)
        page.pdf(path=pdf_path, format="Letter", print_background=True,
                 margin={"top": "0.6in", "bottom": "0.6in", "left": "0.6in", "right": "0.6in"})
        browser.close()
    return True
