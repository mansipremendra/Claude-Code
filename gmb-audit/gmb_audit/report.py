"""Write CSV, JSON and a self-contained HTML report."""

from __future__ import annotations

import csv
import json
from datetime import date
from html import escape
from pathlib import Path


def _flat(r: dict) -> dict:
    site = r.get("site") or {}
    return {
        "name": r["name"],
        "city": r["search_city"],
        "address": r["address"],
        "phone": r["phone"],
        "website": r["website"],
        "maps_url": r["maps_url"],
        "rating": r["rating"] if r["rating"] is not None else "",
        "reviews": r["review_count"],
        "photos": r["photo_count"],
        "days_since_last_review": r["days_since_last_review"] if r["days_since_last_review"] is not None else "",
        "analytics": "yes" if (site.get("ga4") or site.get("gtm")) else "no",
        "meta_pixel_or_ads_tag": "yes" if (site.get("meta_pixel") or site.get("google_ads_tag")) else "no",
        "socials": " ".join(site.get("socials", [])),
        "gap_score": r["gap_score"],
        "gap_count": len(r["gaps"]),
        "gaps": " | ".join(g.label for g in r["gaps"]),
        "pitch_notes": " | ".join(g.advice for g in r["gaps"]),
    }


def write_csv(results: list[dict], path: Path) -> None:
    rows = [_flat(r) for r in sorted(results, key=lambda r: r["gap_score"], reverse=True)]
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def write_json(results: list[dict], summary: dict, path: Path) -> None:
    payload = {
        "summary": summary,
        "businesses": [
            {**{k: v for k, v in r.items() if k not in ("gaps",)},
             "gaps": [g.__dict__ for g in r["gaps"]]}
            for r in results
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


CSS = """
:root{--bg:#fafaf7;--fg:#1b1b18;--mut:#6b6b63;--card:#fff;--line:#e4e2da;--acc:#0f6b5c;--bad:#b3261e;--warn:#9a6700}
@media (prefers-color-scheme:dark){:root{--bg:#141412;--fg:#ecebe5;--mut:#9a998f;--card:#1d1d1a;--line:#33332e;--acc:#4cc2ac;--bad:#ff8a80;--warn:#e3b341}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.1rem;margin:32px 0 12px}
.sub{color:var(--mut);margin:0 0 20px}.banner{background:var(--card);border:1px dashed var(--warn);padding:8px 12px;border-radius:8px;color:var(--warn);margin-bottom:16px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi b{display:block;font-size:1.5rem}.kpi span{color:var(--mut);font-size:.85rem}
.bar{display:grid;grid-template-columns:minmax(150px,320px) 1fr 48px;gap:10px;align-items:center;margin:6px 0;font-size:.9rem}
.bar i{display:block;height:10px;background:var(--acc);border-radius:5px}.bar em{color:var(--mut);font-style:normal;text-align:right}
.bar small{color:var(--mut)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}
th{cursor:pointer;user-select:none;font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);white-space:nowrap}
tr.biz{cursor:pointer}tr.biz:hover{background:rgba(127,127,127,.08)}
.score{font-weight:700}.hi{color:var(--bad)}.mid{color:var(--warn)}.lo{color:var(--acc)}
tr.detail td{background:rgba(127,127,127,.05)}tr.detail ul{margin:0;padding-left:18px}tr.detail li{margin:3px 0}
tr.detail small{color:var(--mut)}a{color:var(--acc)}.filters{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px}
select,input{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit}
@media(max-width:600px){.bar{grid-template-columns:1fr 1fr 40px}}
"""

JS = """
const rows=[...document.querySelectorAll('tr.biz')];
function apply(){const q=document.getElementById('q').value.toLowerCase(),c=document.getElementById('city').value;
rows.forEach(r=>{const show=(!c||r.dataset.city===c)&&(!q||r.dataset.name.includes(q));r.style.display=show?'':'none';r.nextElementSibling.style.display='none'})}
document.getElementById('q').oninput=apply;document.getElementById('city').onchange=apply;
rows.forEach(r=>r.onclick=()=>{const d=r.nextElementSibling;d.style.display=d.style.display==='none'?'table-row':'none'});
document.querySelectorAll('th[data-k]').forEach((th,i)=>th.onclick=()=>{const tb=document.querySelector('tbody'),asc=th.dataset.asc!=='1';th.dataset.asc=asc?'1':'0';
const pairs=rows.map(r=>[r,r.nextElementSibling]);pairs.sort((a,b)=>{const x=a[0].children[i].dataset.v,y=b[0].children[i].dataset.v;
const nx=parseFloat(x),ny=parseFloat(y);const cmp=(!isNaN(nx)&&!isNaN(ny))?nx-ny:x.localeCompare(y);return asc?cmp:-cmp});
pairs.forEach(p=>{tb.appendChild(p[0]);tb.appendChild(p[1])})});
"""


def _score_class(s: int) -> str:
    return "hi" if s >= 60 else "mid" if s >= 35 else "lo"


def write_html(results: list[dict], summary: dict, niche: str, cities: list[str], path: Path, demo: bool = False) -> None:
    ranked = sorted(results, key=lambda r: r["gap_score"], reverse=True)
    e = escape

    bars = "".join(
        f'<div class="bar"><span>{e(g["label"])} <small>({e(g["category"])})</small></span>'
        f'<i style="width:{g["percent"]}%"></i><em>{g["percent"]}%</em></div>'
        for g in summary["common_gaps"][:14]
    )

    rows = []
    for r in ranked:
        site = r.get("site") or {}
        web = (f'<a href="{e(r["website"])}" target="_blank" rel="noopener noreferrer">site</a>'
               if r["website"] else '<span class="hi">none</span>')
        maps = f' <a href="{e(r["maps_url"])}" target="_blank" rel="noopener noreferrer">maps</a>' if r["maps_url"] else ""
        gap_items = "".join(
            f"<li><b>{e(g.label)}</b> <small>[{e(g.category)}, {g.points} pts]</small><br><small>{e(g.advice)}</small></li>"
            for g in r["gaps"]
        ) or "<li>No gaps found.</li>"
        analytics = "yes" if (site.get("ga4") or site.get("gtm")) else "no"
        rating = f'{r["rating"]:.1f}' if r["rating"] is not None else "n/a"
        rows.append(
            f'<tr class="biz" data-city="{e(r["search_city"])}" data-name="{e(r["name"].lower())}">'
            f'<td data-v="{e(r["name"].lower())}">{e(r["name"])}<br><small>{e(r["address"])}</small></td>'
            f'<td data-v="{e(r["search_city"])}">{e(r["search_city"])}</td>'
            f'<td data-v="{r["rating"] or 0}">{rating}</td>'
            f'<td data-v="{r["review_count"]}">{r["review_count"]}</td>'
            f'<td data-v="{e(web)}">{web}{maps}</td>'
            f'<td data-v="{analytics}">{analytics}</td>'
            f'<td data-v="{r["gap_score"]}" class="score {_score_class(r["gap_score"])}">{r["gap_score"]}</td></tr>'
            f'<tr class="detail" style="display:none"><td colspan="7"><ul>{gap_items}</ul>'
            f'<small>Phone: {e(r["phone"] or "none listed")}</small></td></tr>'
        )

    city_opts = "".join(f'<option value="{e(c)}">{e(c)}</option>' for c in cities)
    banner = '<div class="banner">Sample data: this is a demo run, not real businesses.</div>' if demo else ""

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Marketing gap audit</title>
<style>{CSS}</style></head><body><main>
<h1>Marketing gap audit: {e(niche)}</h1>
<p class="sub">{e(", ".join(cities))} &middot; {date.today().isoformat()}</p>{banner}
<div class="kpis">
<div class="kpi"><b>{summary["businesses"]}</b><span>businesses audited</span></div>
<div class="kpi"><b>{summary["avg_gap_score"]}</b><span>average gap score (0-100)</span></div>
<div class="kpi"><b>{summary["median_reviews"]}</b><span>median Google reviews</span></div>
<div class="kpi"><b>{summary["median_rating"] if summary["median_rating"] is not None else "n/a"}</b><span>median rating</span></div>
</div>
<h2>Most common gaps in this niche</h2>{bars}
<h2>Businesses, biggest opportunity first</h2>
<p class="sub">Click a row for every gap and the suggested fix. Click a header to sort.</p>
<div class="filters"><input id="q" placeholder="Search name"><select id="city"><option value="">All cities</option>{city_opts}</select></div>
<div class="scroll"><table><thead><tr><th data-k>Business</th><th data-k>City</th><th data-k>Rating</th><th data-k>Reviews</th><th data-k>Website</th><th data-k>Analytics</th><th data-k>Gap score</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div>
<p class="sub" style="margin-top:20px">Gap score adds weighted points for each gap found (capped at 100). Higher means more room for a marketing agency to help. Photo counts are capped at 10 by the Google API.</p>
</main><script>{JS}</script></body></html>"""
    path.write_text(doc, encoding="utf-8")
