# Architecture

## The shape of the problem

Twelve mall operators, twelve different ways of publishing a tenant directory:
a JSON API here, a headless CMS there, a Laravel page that embeds its entire
state in one HTML attribute, an Elementor widget that hides its data inside a
JSON-escaped string. None of them share a schema, and several actively fight
being read.

The design answer is a thin, uniform core with all the weirdness pushed into
per-chain scrapers:

```
                  ┌──────────────┐
   each chain ───▶│ MallChain-   │───▶ Mall + Store  ───▶ snapshot ───▶ analysis
   its own way    │   Scraper    │     (one schema)       (parquet)     + report
                  └──────────────┘
                         ▲
                   Fetcher (rate limit, retries, cache)
```

A scraper's only obligation is to turn one operator's mess into `Mall` and
`Store` rows. Everything downstream — validation, normalization, brand
matching, reporting — is chain-agnostic and written once.

## Layout

The repository is organized as an explicit four-stage pipeline. Directory names
carry the stage number for readability; the package inside each carries a valid
Python identifier, because module names cannot begin with a digit.

```
common/mallscape_core/      models, snapshot storage        (imported by all)
1_scrape/mallscape_scrape/  fetcher, 12 scrapers, registries, run validation
2_clean/mallscape_clean/    name/category/floor/phone normalization
3_report/mallscape_report/  brand analysis, deterministic breakdown
4_website/mallscape_website/ self-contained static site
cli/mallscape/              typer app wiring the stages together
```

**Stage N may import stages below it and `mallscape_core`, never the reverse.**
That single rule keeps the pipeline direction and the dependency direction the
same, so a stage can be run, tested, or replaced on its own.

Stage 2 is additive by contract: it reads stage 1's output and writes a new
file beside it. Nothing downstream of a scrape ever rewrites a scrape.

## Modules

| module | responsibility |
|---|---|
| `fetch.py` | One HTTP client: rate limiting, exponential backoff, per-chain headers, and an on-disk response cache keyed by URL+params |
| `models.py` | `Mall` and `Store` — the only vocabulary the rest of the system speaks |
| `scrapers/base.py` | `MallChainScraper` ABC: `discover_malls()` + `scrape_mall()`, plus per-mall failure isolation |
| `scrapers/*.py` | One module per operator. All the site-specific ugliness lives here |
| `coverage.py` | Reads `registry/<chain>_coverage.json` and reports known gaps every run |
| `normalize.py` | `brand_key()` — collapses raw store names so brands match across chains |
| `validate.py` | Per-run report: counts, diff vs previous snapshot, anomaly detection |
| `analyze.py` | Builds the brand-presence tables |
| `report.py` | Deterministic Markdown breakdown of a snapshot |
| `storage.py` | Dated snapshots, `latest`, and the usability guards |

## Two invariants worth protecting

**1. A snapshot is either complete or not published.**

A crashed or single-chain run once left a zero-row snapshot on disk, and
`analyze` — which picks the newest snapshot — selected it and crashed. Three
guards now exist: `scrape` carries forward chains it isn't scraping,
`latest_usable_run()` skips degenerate snapshots, and `update_latest()`
refuses to publish one. Carried-forward rows keep their original `scraped_at`,
so a stale chain is never presented as fresh.

**2. Silence must never mean success.**

Every scraper that cannot derive its mall list live must verify its hardcoded
roster against the site on each run and warn on drift (`filinvest`, `starmall`,
`araneta`, and `fishermall` for floor lists). Every known-empty mall is
recorded in a coverage registry so it stays explained rather than
re-investigated. Truncation is reported, not swallowed — WalterMart emits a
warning for every category that hits the server's 10-item cap.

This invariant is the one that keeps being violated. See `docs/PITFALLS.md`.

## Adding a chain

1. Find the real data source before writing any parser. Load the directory page
   in a browser and watch the network tab — half these sites turn out to have a
   clean JSON API behind a JavaScript front end. Check for a stale or parked
   domain first; three of the operators investigated had one.
2. Subclass `MallChainScraper`. Set `extra_headers` if the endpoint needs them.
3. Derive the mall roster **live** if the site permits it. If you must hardcode,
   add a `_check_roster()` that diffs against the live nav and warns.
4. Add a fixture from the raw cache and a parser test asserting an exact count
   against the source markup — not a lower bound.
5. Register it in `SCRAPERS` in `cli.py` and add it to `SOURCES` in `report.py`.

Everything else — validation, normalization, analysis, reporting — picks the
new chain up automatically.

## Verification workflow

```bash
uv run pytest                                   # parser + integrity regressions
uv run mallscape scrape --chain <c> --date <d>  # re-parses from cache if present
uv run mallscape report --date <d>              # deterministic breakdown
```

Because the cache makes re-parsing free, the fastest way to check a parser
change is to re-run the scrape for that chain against an existing snapshot date
and diff the resulting counts.
