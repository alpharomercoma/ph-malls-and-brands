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


def update_latest(run_date: str) -> None:
    src = processed_dir(run_date)
    dest = DATA_DIR / "latest"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
