"""Deterministic breakdown report for a scrape snapshot.

Given the same snapshot, this module always produces byte-identical Markdown:
no wall-clock timestamps, every collection sorted, fixed column widths. That
makes the report diffable across runs - a change in the output means a change
in the data, never a change in the weather.

Everything is derived from the snapshot tables plus the coverage registries,
so the report also states what was *excluded* and why, not just what was kept.
"""

from __future__ import annotations

import json
from importlib import resources

from mallscape_core import storage

# Where each chain's data comes from, for the provenance section. Kept here
# rather than in the scrapers so the report can describe a snapshot without
# importing (and therefore network-configuring) every scraper module.
SOURCES = {
    "sm": ("smsupermalls.com", "JSON API (list-of-malls + tenants)"),
    "robinsons": ("robinsonsmalls.com + vmd.robinsonsmalls.com", "Drupal HTML + Google Sites fallback"),
    "ayala": ("api.ayalamalls.com", "explore-v2 JSON API"),
    "megaworld": ("megaworld-lifestylemalls.com", "Contentstack headless CMS API"),
    "waltermart": ("malls.waltermart.com.ph", "server-rendered HTML"),
    "ortigas": ("ortigasmalls.com", "Laravel/Inertia data-page JSON"),
    "xentro": ("xentromalls.com", "server-rendered HTML"),
    "filinvest": ("filinvestlifemalls.com", "server-rendered HTML table"),
    "fishermall": ("fishermall.com.ph", "loadlevel.php HTML fragments"),
    "araneta": ("aranetacity.com", "server-rendered HTML"),
    "starmall": ("starmalls.com.ph", "Elementor JSON-escaped blob"),
}

# Chains whose published totals are known to be a lower bound.
CAVEATS = {
    "waltermart": (
        "**Counts are a FLOOR.** Every category page caps at 10 tenants and the "
        "mall page returns an identical set; no pagination or limit parameter "
        "lifts it. Malls with a capped category are truncated upstream."
    ),
    "ayala": (
        "Ayala's API returns duplicate `(mall, merchant)` pairs with distinct "
        "ids but no distinguishing fields, so listing counts run above the "
        "number of unique brands present."
    ),
    "xentro": (
        "Some source list items merge two tenants into one line; those names "
        "are preserved verbatim rather than split on a guess."
    ),
}


def _fmt_table(rows: list[list[str]], headers: list[str], align_right: set[int] = frozenset()) -> str:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    def line(cells: list[str]) -> str:
        out = []
        for i, cell in enumerate(cells):
            out.append(cell.rjust(widths[i]) if i in align_right else cell.ljust(widths[i]))
        return "| " + " | ".join(out) + " |"
    sep = "|" + "|".join(
        ("-" * (widths[i] + 2)) if i not in align_right else ("-" * (widths[i] + 1)) + ":"
        for i in range(len(headers))
    ) + "|"
    return "\n".join([line(headers), sep, *(line(r) for r in rows)])


def _load_coverage(chain: str) -> dict | None:
    try:
        raw = resources.files("mallscape_scrape.registry").joinpath(f"{chain}_coverage.json").read_text()
    except FileNotFoundError:
        return None
    return json.loads(raw)


def _unscraped() -> dict:
    raw = resources.files("mallscape_scrape.registry").joinpath("unscraped_chains.json").read_text()
    return json.loads(raw)


def build(run_date: str) -> str:
    malls = storage.read(run_date, storage.SCRAPE, "malls")
    # prefer stage 2 output; fall back to stage 1 so the report still builds
    # before cleaning has run
    stores = storage.read(run_date, storage.CLEAN, "stores_clean")
    if stores is None:
        stores = storage.read(run_date, storage.SCRAPE, "stores")
    if malls is None or stores is None:
        raise SystemExit(f"no snapshot for {run_date}")

    listings = stores.groupby(["chain", "mall_id"]).size().rename("listings")
    malls = malls.merge(listings, on=["chain", "mall_id"], how="left")
    malls["listings"] = malls["listings"].fillna(0).astype(int)

    out: list[str] = []
    add = out.append

    add(f"# Mall directory scrape - breakdown ({run_date})")
    add("")
    add(
        f"**{len(malls):,} properties · {len(stores):,} listings · "
        f"{malls['chain'].nunique()} chains**"
    )
    add("")
    add(
        "Generated deterministically from the snapshot in "
        f"`data/snapshots/{run_date}/`. Regenerate with "
        f"`mallscape report --date {run_date}`."
    )
    add("")

    # ---------- data quality ----------
    add("## Data quality")
    add("")
    unknown = int((stores.get("category_std", "unknown") == "unknown").sum()) if "category_std" in stores else None
    if unknown is not None:
        add(f"{unknown:,} of {len(stores):,} listings have no confidently mapped category.")
    review = storage.read(run_date, storage.CLEAN, "normalization_review")
    if review is not None:
        add(f"{len(review):,} normalized brand keys have multiple raw variants or require review.")
    add("Raw listings are retained; these signals describe uncertainty rather than removing rows.")
    add("")

    # ---------- per-chain summary ----------
    add("## Chains")
    add("")
    rows = []
    for chain in sorted(malls["chain"].unique()):
        cm = malls[malls["chain"] == chain]
        mall_only = int((cm["property_type"] == "mall").sum())
        fetched = sorted(cm["scraped_at"].unique())
        host, _method = SOURCES.get(chain, ("-", "-"))
        rows.append([
            chain,
            f"{len(cm):,}",
            f"{mall_only:,}",
            f"{int(cm['listings'].sum()):,}",
            ", ".join(fetched),
            host,
        ])
    rows.append([
        "**total**",
        f"**{len(malls):,}**",
        f"**{int((malls['property_type'] == 'mall').sum()):,}**",
        f"**{len(stores):,}**",
        "",
        "",
    ])
    add(_fmt_table(
        rows,
        ["chain", "properties", "malls", "listings", "fetched", "source"],
        align_right={1, 2, 3},
    ))
    add("")
    add(
        "`properties` counts everything the operator publishes a directory for; "
        "`malls` excludes non-mall retail (condo podiums, amusement parks, office "
        "annexes). **Use `malls` for chain-vs-chain comparison.**"
    )
    add("")

    # ---------- caveats ----------
    flagged = sorted(c for c in CAVEATS if c in set(malls["chain"]))
    if flagged:
        add("### Accuracy caveats")
        add("")
        for chain in flagged:
            add(f"- **{chain}** - {CAVEATS[chain]}")
        add("")

    # ---------- per-property ----------
    add("## Properties")
    add("")
    for chain in sorted(malls["chain"].unique()):
        cm = malls[malls["chain"] == chain].sort_values(
            ["listings", "mall_id"], ascending=[False, True]
        )
        add(f"### {chain} ({len(cm)} properties, {int(cm['listings'].sum()):,} listings)")
        add("")
        rows = [
            [
                str(r.mall_name),
                str(r.region or "-"),
                str(r.property_type),
                f"{int(r.listings):,}",
            ]
            for r in cm.itertuples()
        ]
        add(_fmt_table(rows, ["property", "region", "type", "listings"], align_right={3}))
        add("")

    # ---------- zero-store properties ----------
    empty = malls[malls["listings"] == 0].sort_values(["chain", "mall_id"])
    add("## Properties with zero listings")
    add("")
    if empty.empty:
        add("None.")
    else:
        add(
            f"{len(empty)} properties publish no tenant directory. Every one was "
            "checked against its source and is an upstream gap, not a parse failure."
        )
        add("")
        add(_fmt_table(
            [[r.chain, str(r.mall_name), str(r.mall_id)] for r in empty.itertuples()],
            ["chain", "property", "id"],
        ))
    add("")

    # ---------- excluded operators ----------
    add("## Excluded operators")
    add("")
    unscraped = _unscraped()
    add(
        "Operators investigated but not scraped. Each entry records the finding "
        "and what would have to change for a scraper to become viable."
    )
    add("")
    rows = []
    for entry in sorted(unscraped["chains"], key=lambda e: e["chain"]):
        known = entry.get("malls_known")
        rows.append([
            entry["name"],
            str(known) if known else "-",
            entry["status"],
        ])
    add(_fmt_table(rows, ["operator", "malls", "status"], align_right={1}))
    add("")
    for entry in sorted(unscraped["chains"], key=lambda e: e["chain"]):
        add(f"**{entry['name']}** - {entry['finding']}")
        add("")

    # ---------- known gaps within scraped chains ----------
    add("## Known gaps inside scraped chains")
    add("")
    any_gap = False
    for chain in sorted(malls["chain"].unique()):
        cov = _load_coverage(chain)
        if not cov:
            continue
        entries = cov.get("not_in_api", [])
        if not entries:
            continue
        any_gap = True
        add(f"### {chain}")
        add("")
        rows = [
            [
                e["name"],
                str(e.get("region") or "-"),
                str(e.get("opened") or "-"),
                str(e.get("property_type") or "-"),
            ]
            for e in sorted(entries, key=lambda e: e["name"])
        ]
        add(_fmt_table(rows, ["property", "region", "opened", "type"]))
        add("")
    if not any_gap:
        add("None recorded.")
        add("")

    # ---------- brand headline ----------
    brand_summary = storage.read(run_date, storage.REPORT, "brand_summary")
    if brand_summary is not None and not brand_summary.empty:
        add("## Brand reach")
        add("")
        add(f"{len(brand_summary):,} distinct brands after normalization.")
        add("")
        top = brand_summary.sort_values(
            ["n_malls_total", "brand_key"], ascending=[False, True]
        ).head(20)
        add(_fmt_table(
            [[str(r.display_name), f"{int(r.n_malls_total):,}", f"{int(r.n_chains)}"]
             for r in top.itertuples()],
            ["brand", "malls", "chains"],
            align_right={1, 2},
        ))
        add("")

    return "\n".join(out).rstrip() + "\n"
