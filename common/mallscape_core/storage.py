"""Snapshot storage: stage-owned artifacts under one dated snapshot root.

Layout::

    data/
      cache/<date>/<chain>/     stage 1 HTTP cache (scratch, not committed)
      snapshots/<date>/
        1_scrape/               malls, stores, run_report.md
        2_clean/                stores_clean, category_mapping
        3_report/               brand_*, mall_summary, breakdown.md
        4_website/              bundle.json

Each stage writes only into its own directory and reads only from earlier
stages. Lineage is therefore visible on the filesystem: if a file looks wrong
you know which stage produced it without reading any code, and deleting one
stage's directory reruns exactly that stage.

The date is the unit of atomicity, so a snapshot always describes one point in
time across every stage.
"""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd

from mallscape_core import config

DATA_DIR = config.DATA_DIR

SCRAPE, CLEAN, REPORT, WEBSITE = "1_scrape", "2_clean", "3_report", "4_website"
STAGES = (SCRAPE, CLEAN, REPORT, WEBSITE)


def today() -> str:
    return dt.date.today().isoformat()


def cache_dir(run_date: str, chain: str) -> Path:
    d = DATA_DIR / "cache" / run_date / chain
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_dir(run_date: str, stage: str) -> Path:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}; expected one of {STAGES}")
    d = DATA_DIR / "snapshots" / run_date / stage
    d.mkdir(parents=True, exist_ok=True)
    return d


def write(run_date: str, stage: str, name: str, df: pd.DataFrame) -> None:
    """Parquet is what the code reads; CSV ships alongside so the data stays
    inspectable and diffable without a parquet reader."""
    out = stage_dir(run_date, stage)
    df.to_parquet(out / f"{name}.parquet", index=False)
    df.to_csv(out / f"{name}.csv", index=False)


def read(run_date: str, stage: str, name: str) -> pd.DataFrame | None:
    path = DATA_DIR / "snapshots" / run_date / stage / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None


def write_text(run_date: str, stage: str, name: str, text: str) -> Path:
    path = stage_dir(run_date, stage) / name
    path.write_text(text)
    return path


def runs() -> list[str]:
    root = DATA_DIR / "snapshots"
    if not root.exists():
        return []
    return sorted(p.name for p in root.iterdir() if p.is_dir() and p.name != "latest")


def previous_run(run_date: str) -> str | None:
    earlier = [r for r in runs() if r < run_date]
    return earlier[-1] if earlier else None


def is_usable(run_date: str) -> bool:
    """Usable means stage 1 actually produced mall and store rows. A crashed or
    empty run must never be selected as the newest snapshot."""
    malls = read(run_date, SCRAPE, "malls")
    stores = read(run_date, SCRAPE, "stores")
    return (
        malls is not None
        and stores is not None
        and not malls.empty
        and not stores.empty
        and "chain" in malls.columns
        and "store_name_raw" in stores.columns
    )


def latest_usable_run() -> str | None:
    for run in reversed(runs()):
        if is_usable(run):
            return run
    return None


def publish_latest(run_date: str) -> None:
    """Mirror a snapshot to snapshots/latest so downstream paths stay stable."""
    if not is_usable(run_date):
        raise ValueError(
            f"refusing to publish {run_date} as latest: stage 1 output is empty "
            f"or missing required columns"
        )
    dest = DATA_DIR / "snapshots" / "latest"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(DATA_DIR / "snapshots" / run_date, dest)
