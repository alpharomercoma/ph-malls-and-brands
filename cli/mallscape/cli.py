"""Philippine Mall Explorer command line.

Thin orchestration only. Every command resolves a snapshot date, delegates to
the stage that owns the work, and prints the result. No stage logic lives here,
so each stage can also be driven directly from Python or a test.
"""

from __future__ import annotations

import typer

from mallscape_clean import pipeline as clean_stage
from mallscape_core import storage
from mallscape_report import pipeline as report_stage
from mallscape_scrape import pipeline as scrape_stage
from mallscape_scrape.registry_of_scrapers import SCRAPERS
from mallscape_website import pipeline as website_stage

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)


def _resolve(date: str | None) -> str:
    run_date = date or storage.latest_usable_run()
    if run_date is None:
        raise SystemExit("no usable snapshot found; run `mallscape scrape` first")
    return run_date


@app.command()
def scrape(
    chain: str = typer.Option("all", help=f"one of {', '.join(SCRAPERS)}, or 'all'"),
    date: str = typer.Option(None, help="snapshot date (YYYY-MM-DD), default today"),
    rate: float = typer.Option(3.0, help="max requests per second"),
):
    """Stage 1. Fetch directories and write malls plus stores."""
    if chain != "all" and chain not in SCRAPERS:
        raise SystemExit(f"unknown chain {chain!r}; expected one of {', '.join(SCRAPERS)}")
    chains = list(SCRAPERS) if chain == "all" else [chain]
    run_date = date or storage.today()
    scrape_stage.run(chains, run_date, rate)
    storage.publish_latest(run_date)


@app.command()
def clean(date: str = typer.Option(None, help="snapshot date, default newest usable")):
    """Stage 2. Standardize listings without modifying stage 1 output."""
    run_date = _resolve(date)
    clean_stage.run(run_date)
    storage.publish_latest(run_date)


@app.command()
def report(date: str = typer.Option(None, help="snapshot date, default newest usable")):
    """Stage 3. Build brand analysis tables and the breakdown document."""
    run_date = _resolve(date)
    report_stage.run(run_date)
    storage.publish_latest(run_date)


@app.command()
def website(
    date: str = typer.Option(None, help="snapshot date, default newest usable"),
    serve: bool = typer.Option(False, "--serve", help="serve the site after building"),
    port: int = typer.Option(3000, help="port used by --serve"),
):
    """Stage 4. Build the static site, optionally serving it."""
    run_date = _resolve(date)
    website_stage.run(run_date)
    storage.publish_latest(run_date)
    if serve:
        website_stage.serve(port)


@app.command()
def build(date: str = typer.Option(None, help="snapshot date, default newest usable")):
    """Run stages 2 through 4 over an existing scrape."""
    run_date = _resolve(date)
    clean_stage.run(run_date)
    report_stage.run(run_date, quiet=True)
    website_stage.run(run_date)
    storage.publish_latest(run_date)
    print(f"\n[build] stages 2-4 complete for {run_date}")


if __name__ == "__main__":
    app()
