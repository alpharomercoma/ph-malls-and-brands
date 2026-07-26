"""Known-coverage registries: properties that exist but whose operator does
not publish a machine-readable store directory.

Every chain's official site is an incomplete view of its own portfolio. Rather
than silently omitting what the site omits, each chain ships a
``registry/<chain>_coverage.json`` describing the gap, and every run surfaces
it in the report. This also detects the good case: when a previously missing
mall finally appears upstream, the run says so, so it can be scraped.
"""

from __future__ import annotations

import datetime as dt
import json
from importlib import resources


def load(chain: str) -> dict | None:
    try:
        raw = resources.files("mallscape.registry").joinpath(f"{chain}_coverage.json").read_text()
    except FileNotFoundError:
        return None
    return json.loads(raw)


def report_gaps(scraper, scraped_names: set[str]) -> None:
    """Warn about known-missing malls, and about ones that have since appeared."""
    coverage = load(scraper.chain)
    if not coverage:
        return
    today = dt.date.today().isoformat()
    normalized = {n.lower() for n in scraped_names}
    missing, appeared = [], []

    for entry in coverage.get("not_in_api", []):
        name = entry["name"].lower()
        if any(name in n or n in name for n in normalized):
            appeared.append(entry["name"])
            continue
        opened = entry.get("opened")
        # count malls that are open; a null opening date means "operating,
        # date unrecorded" — only an explicitly future date is excluded
        is_open = opened is None or opened[:10] <= today
        if entry.get("property_type", "").endswith("mall") and is_open:
            when = f" (opened {opened})" if opened else ""
            missing.append(f"{entry['name']}{when}")

    if missing:
        scraper.warn(
            "operating malls with no published directory — absent from store "
            "data by necessity: " + "; ".join(missing)
        )
    for name in appeared:
        scraper.warn(
            f"{name} now appears upstream — remove it from "
            f"registry/{scraper.chain}_coverage.json so its stores get scraped"
        )
