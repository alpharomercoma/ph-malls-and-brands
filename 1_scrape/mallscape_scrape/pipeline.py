"""Stage 1 entry point: scrape chains and write this stage's artifacts.

Owns everything about producing a snapshot's `1_scrape/` directory, including
the carry-forward rule that keeps a single-chain run from silently dropping
the other chains.
"""

from __future__ import annotations

import pandas as pd

from mallscape_core import storage
from mallscape_scrape import validate
from mallscape_scrape.fetch import Fetcher
from mallscape_scrape.registry_of_scrapers import SCRAPERS


def run(chains: list[str], run_date: str, rate: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_malls, all_stores, warnings = [], [], []

    # Seed from this date's snapshot if it exists, else carry the previous run
    # forward, so scraping one chain never drops the rest.
    prev_malls = storage.read(run_date, storage.SCRAPE, "malls")
    prev_stores = storage.read(run_date, storage.SCRAPE, "stores")
    partial = len(chains) < len(SCRAPERS)
    if prev_malls is None and partial:
        carry_from = storage.previous_run(run_date)
        if carry_from:
            prev_malls = storage.read(carry_from, storage.SCRAPE, "malls")
            prev_stores = storage.read(carry_from, storage.SCRAPE, "stores")
            if prev_malls is not None:
                kept = sorted(set(prev_malls["chain"]) - set(chains))
                print(f"[scrape] carrying forward {carry_from} for chains: {kept}")

    for name in chains:
        cls = SCRAPERS[name]
        fetcher = Fetcher(storage.cache_dir(run_date, name), rate=rate, headers=cls.extra_headers)
        scraper = cls(fetcher)
        try:
            malls, stores = scraper.scrape_all()
        finally:
            fetcher.close()
        print(
            f"[{name}] done: {len(malls)} malls, {len(stores)} stores "
            f"({fetcher.requests_made} requests, {fetcher.cache_hits} cache hits)"
        )
        all_malls.extend(m.to_row() for m in malls)
        all_stores.extend(s.to_row() for s in stores)
        warnings.extend(scraper.warnings)

    malls_df = pd.DataFrame(all_malls)
    stores_df = pd.DataFrame(all_stores)
    # Stamp only what was fetched now; carried rows keep their true date so a
    # stale chain is never presented as fresh.
    malls_df["scraped_at"] = run_date
    stores_df["scraped_at"] = run_date
    if prev_malls is not None and partial:
        malls_df = pd.concat([prev_malls[~prev_malls["chain"].isin(chains)], malls_df])
        stores_df = pd.concat([prev_stores[~prev_stores["chain"].isin(chains)], stores_df])

    storage.write(run_date, storage.SCRAPE, "malls", malls_df)
    storage.write(run_date, storage.SCRAPE, "stores", stores_df)
    report = validate.build_report(run_date, malls_df, stores_df, warnings)
    storage.write_text(run_date, storage.SCRAPE, "run_report.md", report)
    print("\n" + report)
    return malls_df, stores_df
