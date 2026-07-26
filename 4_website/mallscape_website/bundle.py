"""Build the compact JSON the site loads.

Size is the whole design constraint: 328 malls, 11,660 brands and 40,664
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

SCHEMA_VERSION = 1


def build(run_date: str) -> tuple[str, dict]:
    """Return (content_hash, bundle). Pure function of the snapshot."""
    malls = storage.read(run_date, storage.SCRAPE, "malls")
    stores = storage.read(run_date, storage.CLEAN, "stores_clean")
    if malls is None or stores is None:
        raise SystemExit(f"stages 1 and 2 must both have run for {run_date}")

    # --- shared dictionaries, sorted so the bundle is deterministic ---
    chains = sorted(malls["chain"].unique())
    regions = sorted(set(malls["region"].dropna().unique()))
    ptypes = sorted(malls["property_type"].fillna("mall").unique())
    cats = sorted(set(stores["category_std"].dropna().unique()))
    chain_ix = {v: i for i, v in enumerate(chains)}
    region_ix = {v: i for i, v in enumerate(regions)}
    ptype_ix = {v: i for i, v in enumerate(ptypes)}
    cat_ix = {v: i for i, v in enumerate(cats)}

    listings = stores.groupby("mall_id").size()
    malls = malls.sort_values("mall_id").reset_index(drop=True)
    mall_ix = {mid: i for i, mid in enumerate(malls["mall_id"])}

    mall_rows = [
        [
            str(r.mall_name),
            chain_ix[r.chain],
            region_ix.get(r.region, -1),
            ptype_ix.get(r.property_type if pd.notna(r.property_type) else "mall", 0),
            int(listings.get(r.mall_id, 0)),
        ]
        for r in malls.itertuples()
    ]

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
    edges_df = (
        named[["brand_key", "mall_id"]]
        .drop_duplicates()
        .sort_values(["brand_key", "mall_id"])
    )
    per_brand = edges_df.groupby("brand_key")["mall_id"].apply(list)

    brand_keys = sorted(per_brand.index)
    brand_ix = {k: i for i, k in enumerate(brand_keys)}
    brand_rows, edges = [], []
    for key in brand_keys:
        mall_ids = per_brand[key]
        chain_mask = 0
        for mid in mall_ids:
            chain_mask |= 1 << chain_ix[malls.at[mall_ix[mid], "chain"]]
        brand_rows.append([
            str(display[key]),
            cat_ix.get(primary_cat.get(key, ""), -1),
            len(mall_ids),
            chain_mask,
        ])
        bi = brand_ix[key]
        for mid in mall_ids:
            edges.append(bi)
            edges.append(mall_ix[mid])

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
        # flat pairs: brandIdx, mallIdx, brandIdx, mallIdx, ...
        "edges": edges,
    }
    payload = json.dumps(bundle, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:12]
    return digest, bundle


def dumps(bundle: dict) -> str:
    return json.dumps(bundle, separators=(",", ":"), ensure_ascii=False)
