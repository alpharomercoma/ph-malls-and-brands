"""Build the compact JSON the site loads.

Size is the whole design constraint: 322 malls, 11,058 tenant identities and 41,000+
brand-to-mall edges have to reach a phone quickly. Three choices keep it small:

1. Columnar arrays of arrays, not arrays of objects, so field names are stored
   once instead of 40,664 times.
2. Integer indices into shared dictionaries for every repeated string (chain,
   region, category, property type).
3. Edges as one flat integer array read in pairs, which is the smallest useful
   representation of the brand-to-mall relation.

The result is a few hundred KB before compression and is served with a
content-hashed filename so it can be cached immutably.
"""

from __future__ import annotations

import hashlib
import json

import pandas as pd

from mallscape_core import storage

SCHEMA_VERSION = 2

CHAIN_CAVEATS = {
    "waltermart": "incomplete: source caps each category at 10 tenants",
    "ayala": "inflated: source contains duplicate merchant listings",
}


def build(run_date: str) -> tuple[str, dict]:
    """Return (content_hash, bundle). Pure function of the snapshot."""
    malls = storage.read(run_date, storage.SCRAPE, "malls")
    stores = storage.read(run_date, storage.CLEAN, "stores_clean")
    if malls is None or stores is None:
        raise SystemExit(f"stages 1 and 2 must both have run for {run_date}")
    storage.validate_snapshot_frames(malls, stores)

    # --- shared dictionaries, sorted so the bundle is deterministic ---
    chains = sorted(malls["chain"].unique())
    regions = sorted(set(malls["region"].dropna().unique()))
    ptypes = sorted(malls["property_type"].fillna("mall").unique())
    cats = sorted(set(stores["category_std"].dropna().unique()))
    chain_ix = {v: i for i, v in enumerate(chains)}
    region_ix = {v: i for i, v in enumerate(regions)}
    ptype_ix = {v: i for i, v in enumerate(ptypes)}
    cat_ix = {v: i for i, v in enumerate(cats)}

    listings = stores.groupby(["chain", "mall_id"]).size()
    malls = malls.sort_values("mall_id").reset_index(drop=True)
    mall_ix = {(r.chain, r.mall_id): i for i, r in enumerate(malls.itertuples())}

    mall_rows = [
        [
            str(r.mall_name),
            chain_ix[r.chain],
            region_ix.get(r.region, -1),
            ptype_ix.get(r.property_type if pd.notna(r.property_type) else "mall", 0),
            int(listings.get((r.chain, r.mall_id), 0)),
        ]
        for r in malls.itertuples()
    ]

    property_flags = []
    for r in malls.itertuples():
        flags = []
        if r.chain in CHAIN_CAVEATS:
            flags.append(CHAIN_CAVEATS[r.chain])
        if pd.isna(r.region):
            flags.append("region unavailable")
        mall_stores = stores[(stores["chain"] == r.chain) & (stores["mall_id"] == r.mall_id)]
        if not mall_stores.empty and (mall_stores["category_std"] == "unknown").all():
            flags.append("categories unavailable")
        property_flags.append(flags)

    # --- brands: one row per brand_key, with its most common display name ---
    named = stores[stores["brand_key"] != ""]
    display = (
        named.groupby("brand_key")["store_name"]
        .agg(lambda s: s.value_counts().index[0])
        .rename("name")
    )
    primary_cat = (
        named[named["category_std"] != "unknown"]
        .groupby("brand_key")["category_std"]
        .agg(lambda s: s.value_counts().index[0])
    )
    all_cats = (
        named[named["category_std"] != "unknown"]
        .groupby("brand_key")["category_std"]
        .agg(lambda s: sorted(set(s)))
    )
    edges_df = (
        named[["brand_key", "chain", "mall_id"]]
        .drop_duplicates()
        .sort_values(["brand_key", "chain", "mall_id"])
    )
    per_brand = edges_df.groupby("brand_key").apply(
        lambda frame: list(zip(frame["chain"], frame["mall_id"], strict=True)),
        include_groups=False,
    )

    brand_keys = sorted(per_brand.index)
    brand_ix = {k: i for i, k in enumerate(brand_keys)}
    brand_rows, edges = [], []
    aliases: dict[int, str] = {}
    for key in brand_keys:
        mall_ids = per_brand[key]
        chain_mask = 0
        for chain, _mid in mall_ids:
            chain_mask |= 1 << chain_ix[chain]
        # Searching "bpi" must find the branch entity even though its display
        # name is "Bank of the Philippine Islands". Carry the key as an alias
        # whenever it is not already findable inside the display name, which
        # keeps the payload small: most keys are just the lowercased name.
        display_name = str(display[key])
        if key not in display_name.lower():
            aliases[len(brand_rows)] = key
        brand_rows.append([
            str(display[key]),
            cat_ix.get(primary_cat.get(key, ""), -1),
            len(mall_ids),
            chain_mask,
        ])
        bi = brand_ix[key]
        for chain, mid in mall_ids:
            edges.append(bi)
            edges.append(mall_ix[(chain, mid)])

    bundle = {
        "schema": SCHEMA_VERSION,
        "date": run_date,
        "dict": {
            "chains": chains,
            "regions": regions,
            "propertyTypes": ptypes,
            "categories": cats,
        },
        "totals": {
            "properties": len(malls),
            "malls": int((malls["property_type"] == "mall").sum()),
            "listings": len(stores),
            "brands": len(brand_keys),
        },
        # [name, chainIdx, regionIdx, propertyTypeIdx, listings]
        "malls": mall_rows,
        # [name, categoryIdx, mallCount, chainBitmask]
        "brands": brand_rows,
        # sparse brandIdx -> alias, for names that do not contain their own key
        "aliases": {str(k): v for k, v in sorted(aliases.items())},
        # Full category membership; the row's category index remains the
        # primary display category for compact rendering.
        "brandCategories": [
            [cat_ix[c] for c in all_cats.get(key, [])]
            for key in brand_keys
        ],
        "quality": {
            "chainCaveats": CHAIN_CAVEATS,
            "propertyFlags": property_flags,
        },
        # flat pairs: brandIdx, mallIdx, brandIdx, mallIdx, ...
        "edges": edges,
    }
    payload = json.dumps(bundle, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:12]
    return digest, bundle


def dumps(bundle: dict) -> str:
    return json.dumps(bundle, separators=(",", ":"), ensure_ascii=False)
