"""Build viz-ready analysis tables from the latest snapshot.

Outputs (written next to the snapshot tables):
- brand_presence: one row per (brand_key, chain, mall_id) — long-format matrix
- brand_summary:  per brand — malls per chain, total, cross-chain flag
- unique_brands:  brands present in exactly one mall
- mall_summary:   per mall — store count, distinct brands, top categories
"""

from __future__ import annotations

import pandas as pd

from mallscape_core import storage
from mallscape_clean.normalize import brand_key


def build_tables(run_date: str) -> dict[str, pd.DataFrame]:
    malls = storage.read_table(run_date, "malls")
    stores = storage.read_table(run_date, "stores")
    if malls is None or stores is None:
        raise SystemExit(f"no snapshot for {run_date} — run `mallscape scrape` first")

    stores = stores.copy()
    stores["brand_key"] = stores["store_name_raw"].map(brand_key)
    stores = stores[stores["brand_key"] != ""]

    presence = (
        stores[["brand_key", "chain", "mall_id"]]
        .drop_duplicates()
        .merge(malls[["chain", "mall_id", "mall_name", "region"]], on=["chain", "mall_id"])
        .sort_values(["brand_key", "chain", "mall_id"])
    )

    per_chain = (
        presence.groupby(["brand_key", "chain"])["mall_id"].nunique().unstack(fill_value=0)
    )
    for chain in sorted(malls["chain"].unique()):
        if chain not in per_chain.columns:
            per_chain[chain] = 0
    display_names = (
        stores.groupby("brand_key")["store_name_raw"]
        .agg(lambda s: s.value_counts().index[0])
        .rename("display_name")
    )
    brand_summary = per_chain.rename(
        columns={c: f"n_malls_{c}" for c in per_chain.columns}
    ).reset_index()
    chain_cols = [c for c in brand_summary.columns if c.startswith("n_malls_")]
    brand_summary["n_malls_total"] = brand_summary[chain_cols].sum(axis=1)
    brand_summary["n_chains"] = (brand_summary[chain_cols] > 0).sum(axis=1)
    brand_summary["in_all_chains"] = brand_summary["n_chains"] == len(chain_cols)
    brand_summary["in_multiple_chains"] = brand_summary["n_chains"] > 1
    brand_summary = (
        brand_summary.merge(display_names, on="brand_key")
        .sort_values("n_malls_total", ascending=False)
        .reset_index(drop=True)
    )

    unique = brand_summary[brand_summary["n_malls_total"] == 1].merge(
        presence[["brand_key", "chain", "mall_id", "mall_name", "region"]],
        on="brand_key",
    )[["brand_key", "display_name", "chain", "mall_id", "mall_name", "region"]]

    mall_summary = (
        stores.groupby(["chain", "mall_id"])
        .agg(
            n_stores=("store_name_raw", "size"),
            n_brands=("brand_key", "nunique"),
            top_categories=(
                "category",
                lambda s: ", ".join(f"{k} ({v})" for k, v in s.value_counts().head(3).items()),
            ),
        )
        .reset_index()
        .merge(malls[["chain", "mall_id", "mall_name", "region"]], on=["chain", "mall_id"])
    )
    single_mall_brands = unique.groupby(["chain", "mall_id"]).size().rename("n_unique_brands")
    mall_summary = mall_summary.merge(
        single_mall_brands, on=["chain", "mall_id"], how="left"
    ).fillna({"n_unique_brands": 0})
    mall_summary["n_unique_brands"] = mall_summary["n_unique_brands"].astype(int)
    mall_summary = mall_summary.sort_values("n_stores", ascending=False).reset_index(drop=True)

    tables = {
        "brand_presence": presence,
        "brand_summary": brand_summary,
        "unique_brands": unique,
        "mall_summary": mall_summary,
    }
    out = storage.processed_dir(run_date)
    for name, df in tables.items():
        storage.write_table(df, out, name)
    storage.update_latest(run_date)
    return tables


def print_headlines(tables: dict[str, pd.DataFrame]) -> None:
    bs = tables["brand_summary"]
    chain_cols = [c for c in bs.columns if c.startswith("n_malls_") and c != "n_malls_total"]

    print("\n=== Top 15 most visible brands (by number of malls, all chains) ===")
    print(bs.head(15)[["display_name", *chain_cols, "n_malls_total"]].to_string(index=False))

    print(f"\nBrands in ALL {len(chain_cols)} chains:  {bs['in_all_chains'].sum()}")
    print(f"Brands in 2+ chains:      {bs['in_multiple_chains'].sum()}")
    for col in chain_cols:
        others = [c for c in chain_cols if c != col]
        exclusive = bs[(bs[col] > 0) & (bs[others].sum(axis=1) == 0)]
        print(f"Brands only in {col.replace('n_malls_', ''):10s} {len(exclusive)}")

    uniq = tables["unique_brands"]
    print(f"\nBrands unique to a single mall: {len(uniq)}")
    top_uniq = (
        uniq.groupby("mall_name").size().sort_values(ascending=False).head(10)
    )
    print("Malls with most exclusive brands:")
    print(top_uniq.to_string())
