"""Stage 3 entry point: brand analysis tables plus the deterministic breakdown."""

from __future__ import annotations

from mallscape_core import storage
from mallscape_report import analyze, report


def run(run_date: str, quiet: bool = False) -> dict:
    tables = analyze.build_tables(run_date)
    for name, df in tables.items():
        storage.write(run_date, storage.REPORT, name, df)
    storage.write_text(run_date, storage.REPORT, "breakdown.md", report.build(run_date))
    if not quiet:
        analyze.print_headlines(tables)
        print(f"\n[report] wrote {storage.stage_dir(run_date, storage.REPORT)}")
    return tables
