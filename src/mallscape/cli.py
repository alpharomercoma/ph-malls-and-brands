"""mallscape CLI: `mallscape scrape` / `mallscape analyze`."""

from __future__ import annotations

import pandas as pd
import typer

from . import analyze as analyze_mod
from . import storage, validate
from .fetch import Fetcher
from .scrapers.ayala import AyalaScraper
from .scrapers.robinsons import RobinsonsScraper
from .scrapers.sm import SMScraper

app = typer.Typer(no_args_is_help=True, add_completion=False)

SCRAPERS = {"sm": SMScraper, "robinsons": RobinsonsScraper, "ayala": AyalaScraper}


@app.command()
def scrape(
    chain: str = typer.Option("all", help="sm | robinsons | all"),
    date: str = typer.Option(None, help="run date (YYYY-MM-DD), default today"),
    rate: float = typer.Option(3.0, help="max requests per second"),
):
    """Scrape mall directories and write a dated snapshot."""
    run_date = date or storage.today()
    chains = list(SCRAPERS) if chain == "all" else [chain]

    all_malls, all_stores, warnings = [], [], []
    # keep other chains' rows when scraping a single chain into an existing snapshot
    prev_malls = storage.read_table(run_date, "malls")
    prev_stores = storage.read_table(run_date, "stores")

    for name in chains:
        cls = SCRAPERS[name]
        fetcher = Fetcher(
            storage.raw_dir(run_date, name), rate=rate, headers=cls.extra_headers
        )
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
    if prev_malls is not None and chain != "all":
        malls_df = pd.concat([prev_malls[~prev_malls["chain"].isin(chains)], malls_df])
        stores_df = pd.concat([prev_stores[~prev_stores["chain"].isin(chains)], stores_df])
    malls_df["scraped_at"] = run_date
    stores_df["scraped_at"] = run_date

    out = storage.processed_dir(run_date)
    storage.write_table(malls_df, out, "malls")
    storage.write_table(stores_df, out, "stores")
    storage.update_latest(run_date)

    print("\n" + validate.build_report(run_date, malls_df, stores_df, warnings))


@app.command()
def analyze(date: str = typer.Option(None, help="snapshot date, default newest")):
    """Build brand-presence analysis tables from a snapshot."""
    run_date = date or storage.previous_run("9999-99-99")
    if run_date is None:
        raise SystemExit("no snapshots found — run `mallscape scrape` first")
    tables = analyze_mod.build_tables(run_date)
    analyze_mod.print_headlines(tables)
    print(f"\nTables written to data/processed/{run_date}/ (and data/latest/)")


if __name__ == "__main__":
    app()
