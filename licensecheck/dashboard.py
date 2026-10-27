"""Render an analysis as a single self-contained HTML dashboard (no server, no CDN)."""

import json

from .render import FINDING_TITLES


def to_html(result):
    payload = json.dumps(
        {"result": result, "titles": FINDING_TITLES}
    ).replace("</", "<\\/")  # keep user data from closing the script tag
    title = f"License dashboard — {result.get('tenant') or 'tenant'}"
    return TEMPLATE.replace("__TITLE__", _escape(title)).replace("__DATA__", payload)


def _escape(text):
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root {
  --bg: #f6f7f9; --panel: #ffffff; --text: #1b1f24; --muted: #5f6b7a; --line: #e3e7ec;
  --accent: #2459d1; --bad: #c2362b; --warn: #b26a00; --good: #1f7a4d; --chip: #eef2f7;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #111418; --panel: #1a1f25; --text: #e6e9ed; --muted: #97a3b2; --line: #2a313a;
    --accent: #7aa2ff; --bad: #ff7b6e; --warn: #f0b04d; --good: #5fcf98; --chip: #242b34;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 1200px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 22px; margin: 0 0 2px; }
h2 { font-size: 16px; margin: 28px 0 10px; }
.sub { color: var(--muted); margin-bottom: 20px; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.tile { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
.tile .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
.tile .value { font-size: 24px; font-weight: 650; margin-top: 4px; font-variant-numeric: tabular-nums; }
.tile.bad .value { color: var(--bad); } .tile.warn .value { color: var(--warn); }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { font-size: 12px; color: var(--muted); font-weight: 600; cursor: pointer; user-select: none; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tr.vendor td { background: var(--chip); font-weight: 650; }
tr.sku { cursor: pointer; } tr.sku:hover td { background: var(--chip); }
tr.detail td { white-space: normal; padding: 4px 12px 14px 32px; color: var(--muted); }
tr.detail div { margin: 3px 0; } tr.detail b { color: var(--text); font-weight: 600; }
tr.free td { color: var(--muted); } tr.free td.flag, tr.free td.flagw { color: var(--muted); font-weight: 400; }
td.wrap { white-space: normal; min-width: 200px; }
.code { font-size: 11px; margin-left: 14px; }
.more { margin: 10px 12px; }
.flag { color: var(--bad); font-weight: 600; } .flagw { color: var(--warn); font-weight: 600; }
.bar { height: 6px; background: var(--chip); border-radius: 3px; width: 90px; display: inline-block; vertical-align: middle; margin-left: 6px; }
.bar i { display: block; height: 100%; background: var(--accent); border-radius: 3px; }
.gaps { background: var(--panel); border: 1px solid var(--warn); border-left-width: 4px; border-radius: 8px; padding: 10px 14px; margin-top: 16px; }
.gaps li { margin: 4px 0; }
.controls { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; margin-bottom: 10px; }
input[type=search] { flex: 1; min-width: 200px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--line);
  background: var(--panel); color: var(--text); font: inherit; }
button { padding: 8px 12px; border-radius: 8px; border: 1px solid var(--line); background: var(--panel);
  color: var(--text); font: inherit; cursor: pointer; }
button.on { border-color: var(--accent); color: var(--accent); }
.empty { color: var(--muted); padding: 14px; }
.muted { color: var(--muted); }
</style>
</head>
<body>
<main>
  <h1 id="title"></h1>
  <div class="sub" id="subtitle"></div>
  <div class="tiles" id="tiles"></div>
  <div id="gaps"></div>

  <h2>Spend by vendor and product <span class="muted" style="font-weight:400">— click a product for details</span></h2>
  <div class="panel"><table id="skus"></table></div>

  <h2>Renewals and trials (next 90 days)</h2>
  <div class="panel" id="renewals"></div>

  <h2>Findings</h2>
  <div class="controls">
    <input type="search" id="q" placeholder="Filter by name, email, or license">
    <span id="filters"></span>
    <button id="csv">Export CSV</button>
  </div>
  <div class="panel"><table id="findings"></table><div id="more"></div></div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const { result: R, titles: TITLES } = JSON.parse(document.getElementById("data").textContent);
const cur = R.currency || "USD";
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money = v => v == null ? "—" : new Intl.NumberFormat(undefined, {style: "currency", currency: cur}).format(v);
const num = v => new Intl.NumberFormat().format(v ?? 0);

document.getElementById("title").textContent = "License dashboard — " + (R.tenant || "tenant");
document.getElementById("subtitle").textContent = "Generated " + new Date(R.generatedAt).toLocaleString();

// Tiles
const T = R.totals;
const util = T.seatsPurchased ? Math.round(100 * T.seatsAssigned / T.seatsPurchased) : 0;
document.getElementById("tiles").innerHTML = [
  ["Monthly spend", money(T.monthlySpend), ""],
  ["Annual spend", money(T.annualSpend), ""],
  ["Confirmed waste / mo", money(T.confirmedWasteMonthly), T.confirmedWasteMonthly ? "bad" : ""],
  ["At risk / mo", money(T.atRiskMonthly), T.atRiskMonthly ? "warn" : ""],
  ["Paid seats in use", `${num(T.seatsAssigned)} / ${num(T.seatsPurchased)} (${util}%)`, ""],
].map(([l, v, c]) => `<div class="tile ${c}"><div class="label">${l}</div><div class="value">${v}</div></div>`).join("");

if (R.dataGaps.length) {
  document.getElementById("gaps").innerHTML = `<div class="gaps"><strong>Data gaps</strong><ul>${
    R.dataGaps.map(g => `<li>${esc(g)}</li>`).join("")}</ul></div>`;
}

// SKU table: Vendor -> Product, sortable, expandable
const usersFor = sku => Object.entries(R.findings).flatMap(([k, rows]) =>
  rows.filter(f => f.skus.includes(sku)).map(f => ({...f, check: TITLES[k]})));
let skuSort = {key: "monthlyCost", dir: -1};
const skuCols = [
  ["name", "Product", false], ["purchased", "Bought", true], ["assigned", "Assigned", true],
  ["unassigned", "Unassigned", true], ["unitPrice", "Price / seat", true], ["monthlyCost", "Monthly", true],
  ["onDisabledAccounts", "Disabled", true], ["inactive90Plus", "Inactive 90+", true], ["webOnly", "Web-only", true],
];
const open = new Set();
function drawSkus() {
  const isFree = r => r.unitPrice === 0;
  const rows = [...R.skus].sort((a, b) => {
    if (isFree(a) !== isFree(b)) return isFree(a) ? 1 : -1;  // free SKUs always last
    const x = a[skuSort.key] ?? -1, y = b[skuSort.key] ?? -1;
    return (x > y ? 1 : x < y ? -1 : 0) * skuSort.dir;
  });
  const vendors = [...new Set(rows.map(r => r.vendor))];
  let html = "<tr>" + skuCols.map(([k, l, n]) =>
    `<th data-k="${k}" class="${n ? "num" : ""}">${l}${skuSort.key === k ? (skuSort.dir > 0 ? " ▲" : " ▼") : ""}</th>`).join("") + "</tr>";
  for (const v of vendors) {
    const vr = rows.filter(r => r.vendor === v);
    const vcost = vr.reduce((s, r) => s + (r.monthlyCost || 0), 0);
    html += `<tr class="vendor"><td>${esc(v)}</td><td colspan="4"></td><td class="num">${money(vcost)}</td><td colspan="3"></td></tr>`;
    for (const r of vr) {
      const pct = r.purchased ? Math.min(100, Math.round(100 * r.assigned / r.purchased)) : 0;
      const free = isFree(r);
      html += `<tr class="sku ${free ? "free" : ""}" data-sku="${esc(r.sku)}">
        <td class="wrap">${open.has(r.sku) ? "▾" : "▸"} ${esc(r.name)}<br><span class="muted code">${esc(r.sku)}</span></td>
        <td class="num">${free ? "free" : num(r.purchased)}</td>
        <td class="num">${num(r.assigned)}${free ? "" : `<span class="bar"><i style="width:${pct}%"></i></span>`}</td>
        <td class="num ${r.unassigned && !free ? "flagw" : ""}">${free ? "—" : num(r.unassigned)}</td>
        <td class="num">${money(r.unitPrice)}</td>
        <td class="num">${money(r.monthlyCost)}</td>
        <td class="num ${r.onDisabledAccounts ? "flag" : ""}">${num(r.onDisabledAccounts)}</td>
        <td class="num ${r.inactive90Plus ? "flagw" : ""}">${num(r.inactive90Plus)}</td>
        <td class="num">${num(r.webOnly)}</td></tr>`;
      if (open.has(r.sku)) {
        const us = usersFor(r.sku);
        const groups = {};
        us.forEach(u => (groups[u.check] = groups[u.check] || []).push(u.displayName));
        const extra = r.unassignedMonthlyCost ? `<div>Unassigned seats cost <b>${money(r.unassignedMonthlyCost)}/mo</b>.</div>` : "";
        const lines = Object.entries(groups).map(([check, names]) =>
          `<div><b>${esc(check)} (${names.length}):</b> ${esc(names.slice(0, 8).join(", "))}${
            names.length > 8 ? ` <span class="muted">+${names.length - 8} more — see Findings</span>` : ""}</div>`).join("");
        html += `<tr class="detail"><td colspan="9">${extra}${lines ||
          "<div>No user-level findings for this product.</div>"}</td></tr>`;
      }
    }
  }
  const t = document.getElementById("skus");
  t.innerHTML = html;
  t.querySelectorAll("th").forEach(th => th.onclick = () => {
    skuSort = {key: th.dataset.k, dir: skuSort.key === th.dataset.k ? -skuSort.dir : -1};
    drawSkus();
  });
  t.querySelectorAll("tr.sku").forEach(tr => tr.onclick = () => {
    const s = tr.dataset.sku; open.has(s) ? open.delete(s) : open.add(s); drawSkus();
  });
}
drawSkus();

// Renewals
document.getElementById("renewals").innerHTML = R.renewals.length ?
  "<table><tr><th>Product</th><th>Date</th><th class='num'>Days</th><th class='num'>Seats</th><th>Trial</th><th>Status</th></tr>" +
  R.renewals.map(r => `<tr><td>${esc(r.name)}</td><td>${esc(r.date)}</td>
    <td class="num ${r.daysAway <= 30 ? "flag" : ""}">${r.daysAway}</td><td class="num">${num(r.totalLicenses)}</td>
    <td>${r.isTrial ? "yes" : ""}</td><td>${esc(r.status)}</td></tr>`).join("") + "</table>" :
  `<div class="empty">Nothing renews or expires in the next 90 days.</div>`;

// Findings
const PAGE = 25;
const allFindings =Object.entries(R.findings).flatMap(([k, rows]) => rows.map(f => ({...f, key: k})));
const active = new Set(Object.keys(R.findings).filter(k => R.findings[k].length));
const detail = f => Object.entries(f).filter(([k, v]) =>
  !["displayName", "userPrincipalName", "skus", "monthlyCost", "key"].includes(k) && v != null && v !== "" && !(Array.isArray(v) && !v.length))
  .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`).join(" · ");
function visible() {
  const q = document.getElementById("q").value.toLowerCase();
  return allFindings.filter(f => active.has(f.key) &&
    (!q || [f.displayName, f.userPrincipalName, ...f.skus].join(" ").toLowerCase().includes(q)));
}
function drawFindings() {
  document.getElementById("filters").innerHTML = Object.entries(R.findings).filter(([, r]) => r.length)
    .map(([k, r]) => `<button data-k="${k}" class="${active.has(k) ? "on" : ""}">${esc(TITLES[k])} (${r.length})</button>`).join(" ");
  document.querySelectorAll("#filters button").forEach(b => b.onclick = () => {
    active.has(b.dataset.k) ? active.delete(b.dataset.k) : active.add(b.dataset.k); drawFindings();
  });
  const rows = visible();
  document.getElementById("findings").innerHTML = rows.length ?
    "<tr><th>Finding</th><th>User</th><th>Licenses</th><th class='num'>Monthly</th><th>Detail</th></tr>" +
    rows.slice(0, limit).map(f => `<tr><td class="wrap">${esc(TITLES[f.key])}</td><td>${esc(f.displayName)}<br><span class="muted">${esc(f.userPrincipalName)}</span></td>
      <td class="wrap">${esc(f.skus.join(", "))}</td><td class="num">${money(f.monthlyCost)}</td><td class="muted wrap">${esc(detail(f))}</td></tr>`).join("") :
    `<tr><td class="empty">No findings match.</td></tr>`;
  const more = document.getElementById("more");
  more.innerHTML = rows.length > limit ?
    `<button class="more">Show all ${rows.length} (showing ${limit})</button>` : "";
  if (rows.length > limit) more.firstChild.onclick = () => { limit = Infinity; drawFindings(); };
}
let limit = PAGE;
document.getElementById("q").oninput = () => { limit = PAGE; drawFindings(); };
drawFindings();

document.getElementById("csv").onclick = () => {
  const q = v => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lines = [["finding", "name", "email", "licenses", "monthly_cost", "detail"].join(",")]
    .concat(visible().map(f => [TITLES[f.key], f.displayName, f.userPrincipalName, f.skus.join(" "), f.monthlyCost, detail(f)].map(q).join(",")));
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n")], {type: "text/csv"}));
  a.download = "license-findings.csv"; a.click();
};
</script>
</body>
</html>
"""
