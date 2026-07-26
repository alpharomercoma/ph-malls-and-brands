"""Run-folder management: dated raw/processed snapshots + `latest` copy."""

from __future__ import annotations

import datetime as dt
import shutil
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def today() -> str:
    return dt.date.today().isoformat()


def raw_dir(run_date: str, chain: str) -> Path:
    d = DATA_DIR / "raw" / run_date / chain
    d.mkdir(parents=True, exist_ok=True)
    return d


def processed_dir(run_date: str) -> Path:
    d = DATA_DIR / "processed" / run_date
    d.mkdir(parents=True, exist_ok=True)
    return d


def previous_run(run_date: str) -> str | None:
    root = DATA_DIR / "processed"
    if not root.exists():
        return None
    runs = sorted(p.name for p in root.iterdir() if p.is_dir() and p.name < run_date)
    return runs[-1] if runs else None


def write_table(df: pd.DataFrame, out_dir: Path, name: str) -> None:
    df.to_parquet(out_dir / f"{name}.parquet", index=False)
    df.to_csv(out_dir / f"{name}.csv", index=False)


def read_table(run_date: str, name: str) -> pd.DataFrame | None:
    path = processed_dir(run_date) / f"{name}.parquet"
    return pd.read_parquet(path) if path.exists() else None


def is_usable(run_date: str) -> bool:
    """A snapshot is usable only if it actually holds mall and store rows.

    A crashed or single-chain run can leave a zero-row snapshot behind; those
    must never be picked as `latest` or silently analyzed.
    """
    malls = read_table(run_date, "malls")
    stores = read_table(run_date, "stores")
    return (
        malls is not None
        and stores is not None
        and not malls.empty
        and not stores.empty
        and "chain" in malls.columns
        and "store_name_raw" in stores.columns
    )


def latest_usable_run() -> str | None:
    root = DATA_DIR / "processed"
    if not root.exists():
        return None
    for run in sorted((p.name for p in root.iterdir() if p.is_dir()), reverse=True):
        if is_usable(run):
            return run
    return None


def update_latest(run_date: str) -> None:
    if not is_usable(run_date):
        raise ValueError(
            f"refusing to publish {run_date} as `latest`: snapshot is empty or "
            f"missing required columns"
        )
    src = processed_dir(run_date)
    dest = DATA_DIR / "latest"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
