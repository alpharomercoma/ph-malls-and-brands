"""Stage 2 entry point: standardize stage 1 output into this stage's artifacts."""

from __future__ import annotations

from mallscape_clean import clean
from mallscape_core import storage


def run(run_date: str) -> dict[str, float]:
    stores = storage.read(run_date, storage.SCRAPE, "stores")
    if stores is None:
        raise SystemExit(f"stage 1 output missing for {run_date}; run `scrape` first")

    cleaned = clean.build(stores)
    storage.write(run_date, storage.CLEAN, "stores_clean", cleaned)
    storage.write(run_date, storage.CLEAN, "category_mapping", clean.category_mapping(stores))

    flagged = int((cleaned["dq_flags"] != "").sum())
    stats = {
        "listings": len(cleaned),
        "brands": int(cleaned["brand_key"].nunique()),
        "category_mapped": float((cleaned["category_std"] != "unknown").mean()),
        "floor_resolved": float(cleaned["floor_level"].notna().mean()),
        "flagged": flagged,
    }
    print(f"[clean] {stats['listings']:,} listings -> {storage.stage_dir(run_date, storage.CLEAN)}")
    print(f"  brands: {stats['brands']:,} distinct")
    print(f"  categories mapped: {stats['category_mapped']:.1%}")
    print(f"  floors with a numeric level: {stats['floor_resolved']:.1%}")
    print(f"  rows carrying a dq flag: {flagged:,} ({flagged / len(cleaned):.1%})")
    return stats
