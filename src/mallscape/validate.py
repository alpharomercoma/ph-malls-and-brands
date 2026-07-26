"""Per-run validation report: catches site redesigns and partial scrapes by
comparing the fresh snapshot against the previous one."""

from __future__ import annotations

import pandas as pd

from . import storage

DROP_ALERT = 0.20  # alert when a mall loses more than 20% of its stores


def build_report(
    run_date: str,
    malls: pd.DataFrame,
    stores: pd.DataFrame,
    warnings: list[str],
) -> str:
    lines = [f"# mallscape run report — {run_date}", ""]

    for chain, chain_malls in malls.groupby("chain"):
        chain_stores = stores[stores["chain"] == chain]
        lines.append(
            f"- **{chain}**: {len(chain_malls)} malls, {len(chain_stores)} store rows"
        )
    empty = set(malls["mall_id"]) - set(stores["mall_id"])
    if empty:
        lines.append(f"- ⚠ malls with 0 stores: {sorted(empty)}")

    prev_date = storage.previous_run(run_date)
    if prev_date:
        lines.append(f"\n## Diff vs {prev_date}")
        prev_stores = storage.read_table(prev_date, "stores")
        prev_malls = storage.read_table(prev_date, "malls")
        if prev_malls is not None:
            gone = set(prev_malls["mall_id"]) - set(malls["mall_id"])
            new = set(malls["mall_id"]) - set(prev_malls["mall_id"])
            if gone:
                lines.append(f"- ⚠ malls disappeared: {sorted(gone)}")
            if new:
                lines.append(f"- malls added: {sorted(new)}")
        if prev_stores is not None:
            cur = stores.groupby("mall_id").size()
            prev = prev_stores.groupby("mall_id").size()
            both = cur.index.intersection(prev.index)
            delta = (cur[both] - prev[both]) / prev[both]
            drops = delta[delta < -DROP_ALERT]
            if not drops.empty:
                lines.append(f"- ⚠ store-count drops >{DROP_ALERT:.0%} (possible redesign):")
                for mall_id, pct in drops.items():
                    lines.append(f"  - {mall_id}: {prev[mall_id]} → {cur[mall_id]} ({pct:+.0%})")
            else:
                lines.append("- no anomalous store-count drops")
    else:
        lines.append("\n_First run — no previous snapshot to diff against._")

    if warnings:
        lines.append("\n## Scraper warnings")
        lines.extend(f"- {w}" for w in warnings)

    report = "\n".join(lines) + "\n"
    (storage.processed_dir(run_date) / "report.md").write_text(report)
    return report
