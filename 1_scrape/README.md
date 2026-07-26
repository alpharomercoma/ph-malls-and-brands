# Stage 1: scrape

**Reads** twelve operator websites. **Writes** `data/snapshots/<date>/1_scrape/`.

| file | contents |
|---|---|
| `malls.parquet` / `.csv` | one row per property |
| `stores.parquet` / `.csv` | one row per store listing, exactly as published |
| `run_report.md` | counts, diff against the previous snapshot, warnings |

Run it with `uv run mallscape scrape`, or one chain with `--chain sm`.

## What this stage promises

Store names are recorded **verbatim**. No case folding, no trimming beyond
whitespace, no guessing. Everything interpretive belongs to stage 2, so the
raw record stays auditable against the source page forever.

## How it is organized

`registry_of_scrapers.py` maps a chain id to its class, and is the only list of
chains in the repository. `pipeline.py` orchestrates a run and owns the
carry-forward rule. `fetch.py` is the single HTTP client: rate limited, retrying
with backoff, and caching every response to `data/cache/<date>/<chain>/` so
re-parsing costs nothing.

Each scraper in `scrapers/` subclasses `MallChainScraper` and implements
`discover_malls()` and `scrape_mall()`. Its module docstring records the
endpoints, the quirks, and any dead domain that should not be re-added. Read
that docstring before changing a parser.

## The rule that keeps this stage honest

**Silence must never mean success.** A scraper that cannot derive its mall list
live verifies its hardcoded roster against the site on every run and warns on
drift. A known-empty mall is recorded in `registry/<chain>_coverage.json` so it
stays explained instead of being re-investigated. Truncation is reported: the
WalterMart scraper warns for every category that hits that site's 10-item cap.

`registry/unscraped_chains.json` records operators that were investigated and
deliberately not scraped, with the evidence and what would have to change.

## Cost

A cold full run is roughly 3,000 requests and about 25 minutes at the default
3 requests per second. With the cache present it is seconds and touches no
network. Do not raise the rate: SM's WAF issues a temporary site-wide 403 at
sustained higher rates. See `docs/PITFALLS.md`.
