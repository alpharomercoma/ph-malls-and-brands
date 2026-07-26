"""mallscape CLI: `mallscape scrape` / `mallscape analyze`."""

from __future__ import annotations

import pandas as pd
import typer

from . import analyze as analyze_mod
from . import report as report_mod
from . import storage, validate
from .fetch import Fetcher
from .scrapers.araneta import AranetaScraper
from .scrapers.ayala import AyalaScraper
from .scrapers.filinvest import FilinvestScraper
from .scrapers.fishermall import FishermallScraper
from .scrapers.gmall import GmallScraper
from .scrapers.megaworld import MegaworldScraper
from .scrapers.ortigas import OrtigasScraper
from .scrapers.robinsons import RobinsonsScraper
from .scrapers.sm import SMScraper
from .scrapers.xentro import XentroScraper
from .scrapers.starmall import StarmallScraper
from .scrapers.waltermart import WaltermartScraper

app = typer.Typer(no_args_is_help=True, add_completion=False)

SCRAPERS = {
    "sm": SMScraper,
    "robinsons": RobinsonsScraper,
    "ayala": AyalaScraper,
    "megaworld": MegaworldScraper,
    "filinvest": FilinvestScraper,
    "starmall": StarmallScraper,
    "waltermart": WaltermartScraper,
    "araneta": AranetaScraper,
    "fishermall": FishermallScraper,
    "ortigas": OrtigasScraper,
    "xentro": XentroScraper,
    "gmall": GmallScraper,
}


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
    # Keep other chains' rows when scraping a single chain. Seed from this
    # date's snapshot if it exists, else carry forward the previous run —
    # otherwise the first single-chain scrape on a new day silently produces
    # a snapshot containing only that chain.
    prev_malls = storage.read_table(run_date, "malls")
    prev_stores = storage.read_table(run_date, "stores")
    if prev_malls is None and chain != "all":
        carry_from = storage.previous_run(run_date)
        if carry_from:
            prev_malls = storage.read_table(carry_from, "malls")
            prev_stores = storage.read_table(carry_from, "stores")
            if prev_malls is not None:
                kept = sorted(set(prev_malls["chain"]) - set(chains))
                print(f"[scrape] carrying forward {carry_from} rows for chains: {kept}")

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
    # Stamp only what was actually fetched this run. Carried-forward rows keep
    # their original scraped_at, so a stale chain is never presented as fresh.
    malls_df["scraped_at"] = run_date
    stores_df["scraped_at"] = run_date
    if prev_malls is not None and chain != "all":
        malls_df = pd.concat([prev_malls[~prev_malls["chain"].isin(chains)], malls_df])
        stores_df = pd.concat([prev_stores[~prev_stores["chain"].isin(chains)], stores_df])

    out = storage.processed_dir(run_date)
    storage.write_table(malls_df, out, "malls")
    storage.write_table(stores_df, out, "stores")
    storage.update_latest(run_date)

    print("\n" + validate.build_report(run_date, malls_df, stores_df, warnings))


@app.command()
def analyze(date: str = typer.Option(None, help="snapshot date, default newest")):
    """Build brand-presence analysis tables from a snapshot."""
    run_date = date or storage.latest_usable_run()
    if run_date is None:
        raise SystemExit("no usable snapshot found — run `mallscape scrape` first")
    tables = analyze_mod.build_tables(run_date)
    analyze_mod.print_headlines(tables)
    print(f"\nTables written to data/processed/{run_date}/ (and data/latest/)")


@app.command()
def report(date: str = typer.Option(None, help="snapshot date, default newest usable")):
    """Write a deterministic breakdown of a snapshot to breakdown.md."""
    run_date = date or storage.latest_usable_run()
    if run_date is None:
        raise SystemExit("no usable snapshot found — run `mallscape scrape` first")
    path = report_mod.write(run_date)
    print(f"wrote {path}")


if __name__ == "__main__":
    app()
