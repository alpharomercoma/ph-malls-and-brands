"""Stage 4 — build a self-contained static site from the cleaned snapshot.

One HTML file, no build step, no CDN: everything is inlined so the page works
from the filesystem, from a bucket, or from GitHub Pages without a toolchain.
The generator is deterministic for the same snapshot — sorted rows, no clock —
so the published site is diffable like any other artifact of this pipeline.

Reads stage 2's ``stores_clean`` when present and falls back to stage 1's raw
``stores`` otherwise, so the site never silently reports pre-normalization data
without saying so.
"""

from __future__ import annotations

import html
import json

import pandas as pd

from mallscape_core import storage

CSS = """
:root{--bg:#fbfaf8;--fg:#1a1a1a;--mut:#6b6b6b;--line:#e5e2dd;--accent:#8a5a2b;--card:#fff}
@media(prefers-color-scheme:dark){:root{--bg:#141312;--fg:#eceae7;--mut:#9a958e;--line:#2c2a27;--accent:#d9a066;--card:#1c1a18}}
:root[data-theme=dark]{--bg:#141312;--fg:#eceae7;--mut:#9a958e;--line:#2c2a27;--accent:#d9a066;--card:#1c1a18}
:root[data-theme=light]{--bg:#fbfaf8;--fg:#1a1a1a;--mut:#6b6b6b;--line:#e5e2dd;--accent:#8a5a2b;--card:#fff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:16px/1.6 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:48px 24px 80px}
h1{font-size:2rem;margin:0 0 .2em;letter-spacing:-.02em}
h2{font-size:1.15rem;margin:2.5em 0 .8em;padding-bottom:.4em;border-bottom:1px solid var(--line)}
.sub{color:var(--mut);margin:0 0 2em}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:0 0 8px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.stat b{display:block;font-size:1.7rem;letter-spacing:-.02em}
.stat span{color:var(--mut);font-size:.8rem;text-transform:uppercase;letter-spacing:.06em}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--mut);font-weight:600;font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:hover{background:color-mix(in srgb,var(--accent) 7%,transparent)}
.bar{height:6px;border-radius:3px;background:var(--accent);opacity:.75;min-width:2px}
.note{color:var(--mut);font-size:.85rem;margin:.8em 0 0}
footer{margin-top:4em;padding-top:1.5em;border-top:1px solid var(--line);color:var(--mut);font-size:.85rem}
code{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:1px 5px;font-size:.85em}
"""


def _rows(df: pd.DataFrame, cols: list[tuple[str, str, bool]]) -> str:
    """cols = [(header, dataframe column, numeric?)]"""
    head = "".join(f'<th class="{"n" if n else ""}">{html.escape(h)}</th>' for h, _, n in cols)
    body = []
    for r in df.itertuples():
        cells = []
        for _, col, numeric in cols:
            v = getattr(r, col)
            text = f"{v:,}" if numeric and isinstance(v, (int, float)) else html.escape(str(v))
            cells.append(f'<td class="{"n" if numeric else ""}">{text}</td>')
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<div class=scroll><table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>"


def build(run_date: str) -> str:
    malls = storage.read_table(run_date, "malls")
    clean = storage.read_table(run_date, "stores_clean")
    stores = clean if clean is not None else storage.read_table(run_date, "stores")
    if malls is None or stores is None:
        raise SystemExit(f"no usable snapshot for {run_date}")
    normalized = clean is not None

    listings = stores.groupby("mall_id").size().rename("listings")
    m = malls.merge(listings, on="mall_id", how="left")
    m["listings"] = m["listings"].fillna(0).astype(int)

    chains = (
        m.groupby("chain")
        .agg(properties=("mall_id", "size"),
             malls=("property_type", lambda s: int((s == "mall").sum())),
             listings=("listings", "sum"))
        .reset_index()
        .sort_values(["listings", "chain"], ascending=[False, True])
    )
    top = m.sort_values(["listings", "mall_id"], ascending=[False, True]).head(20)

    parts: list[str] = []
    add = parts.append
    add(f"<h1>Philippine mall directories</h1>")
    add(
        f'<p class=sub>{len(m):,} properties · {len(stores):,} store listings · '
        f'{m["chain"].nunique()} operators · snapshot {html.escape(run_date)}</p>'
    )

    add('<div class=stats>')
    for label, value in [
        ("properties", f"{len(m):,}"),
        ("listings", f"{len(stores):,}"),
        ("operators", f"{m['chain'].nunique()}"),
        ("malls only", f"{int((m['property_type'] == 'mall').sum()):,}"),
    ]:
        add(f"<div class=stat><b>{value}</b><span>{label}</span></div>")
    add("</div>")

    add("<h2>Operators</h2>")
    add(_rows(chains, [("chain", "chain", False), ("properties", "properties", True),
                       ("malls", "malls", True), ("listings", "listings", True)]))
    add('<p class=note><b>malls</b> excludes non-mall retail (condo podiums, amusement '
        'parks, office annexes). Use it for operator-vs-operator comparison.</p>')

    add("<h2>Largest properties</h2>")
    add(_rows(top, [("property", "mall_name", False), ("chain", "chain", False),
                    ("region", "region", False), ("listings", "listings", True)]))

    if normalized and "category_std" in stores.columns:
        cats = (
            stores[stores["category_std"] != "unknown"]
            .groupby("category_std").size().rename("listings").reset_index()
            .sort_values(["listings", "category_std"], ascending=[False, True])
        )
        add("<h2>Listings by category</h2>")
        add(_rows(cats, [("category", "category_std", False), ("listings", "listings", True)]))
        add('<p class=note>Harmonized from 101 distinct operator-specific category '
            'strings. Rows the operators left unlabelled are excluded.</p>')

    if normalized and "brand_key" in stores.columns:
        reach = (
            stores.drop_duplicates(subset=["brand_key", "chain", "mall_id"])
            .groupby("brand_key").agg(malls=("mall_id", "nunique"), chains=("chain", "nunique"))
            .reset_index().sort_values(["malls", "brand_key"], ascending=[False, True]).head(25)
        )
        display = (
            stores.groupby("brand_key")["store_name"]
            .agg(lambda s: s.value_counts().index[0]).rename("brand")
        )
        reach = reach.merge(display, on="brand_key")
        add("<h2>Most widespread brands</h2>")
        add(_rows(reach, [("brand", "brand", False), ("malls", "malls", True),
                          ("operators", "chains", True)]))

    source = "stage 2 (<code>stores_clean</code>)" if normalized else "stage 1 (<code>stores</code>, not normalized)"
    add(
        f"<footer>Built deterministically from {source} of snapshot "
        f"{html.escape(run_date)} by <code>mallscape website</code>. "
        f"Regenerating without a data change reproduces this page byte for byte."
        f"</footer>"
    )

    return (
        "<title>Philippine mall directories</title>"
        f"<style>{CSS}</style>"
        f"<div class=wrap>{''.join(parts)}</div>"
    )


def write(run_date: str) -> str:
    out_dir = storage.DATA_DIR.parent / "4_website" / "site"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(build(run_date))
    return str(path)
