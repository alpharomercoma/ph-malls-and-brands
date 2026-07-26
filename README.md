# mallscape

Recurring scraper + brand-presence analysis for Philippine mall directories.
Currently covers **SM Supermalls** (126 malls) and **Robinsons Malls** (53 malls).

## Quick start

```bash
uv sync
uv run mallscape scrape            # full scrape (~15-20 min, mostly SM's paginated API)
uv run mallscape analyze           # build brand-presence tables + print headlines
uv run pytest                      # parser regression tests (offline, fixture-based)
```

Re-run monthly (or weekly): each run writes a dated snapshot and diffs itself
against the previous one, so history accumulates automatically.

## Data layout

```
data/
├── raw/<date>/<chain>/     # every fetched response body (cache; re-parse without re-fetch)
├── processed/<date>/
│   ├── malls.parquet/.csv      # chain, mall_id, mall_name, region, address, ...
│   ├── stores.parquet/.csv     # chain, mall_id, store_name_raw, category, floor, phone, ...
│   ├── brand_presence.*        # (brand_key, chain, mall, region) long-format matrix
│   ├── brand_summary.*         # per brand: #SM malls, #Robinsons malls, cross-chain flag
│   ├── unique_brands.*         # brands present in exactly one mall
│   ├── mall_summary.*          # per mall: store count, brand count, top categories
│   └── report.md               # validation report (counts, diffs vs previous run, warnings)
└── latest/                 # copy of the newest processed snapshot (stable path for viz)
```

`brand_key` (in `normalize.py`) unifies raw names across chains — casefold,
strip phones/branch suffixes/parentheticals, plus a small alias table
(McDo→McDonald's, BDO Unibank→BDO, …). Extend `ALIASES` as dupes surface.

## How each chain is scraped

### SM Supermalls (`scrapers/sm.py`)
Uses the site's own JSON endpoints (no browser):
- `GET /list-of-malls?region=<r>&keyword=&page=<n>` — mall list, 12/page.
  Region buckets: metro-manila, north-luzon, south-luzon, visayas, mindanao,
  smdc, others (together they cover all 126 malls).
- `GET /tenants?category=all&subCategory=all&mallCode=<CODE>&keyword=all&floor=all&building=all&order=order_name&asc=asc&page=<n>` — tenants, 12/page,
  with category/floor/building per tenant.

**Gotcha:** filter params must literally be the string `all` — empty strings
return `[]`.

### Robinsons Malls (`scrapers/robinsons.py`)
No API; two complementary HTML sources:
- **Drupal** `robinsonsmalls.com/mall-info/<slug>` (primary): directory embedded
  as `li.store-name` items grouped under `div.field--name-field-level-N`
  (floor labels in `h4.field--label`, names as `Name | phone`).
- **VMD** `vmd.robinsonsmalls.com` (Google Sites, custom domain): canonical
  region-grouped mall list at `/list-of-malls`; per-mall pages carry category
  sections (SHOP/DINE/…) with `📍 <floor>` markers. Used as fallback for malls
  without a Drupal page (e.g. The Plaza Bagong Silang) — and it's where new
  malls appear first.

Mall discovery reconciles `registry/robinsons_malls.json` (verified
name→slug mapping) against three live sources: the VMD mall list, the
`chat_widget.chatbots` roster embedded in Drupal pages, and slug-pattern
probing for new malls. Anything unrecognized lands as a ⚠ warning in
`report.md` — when that happens, verify the slug and add it to the registry.

**Gotcha:** robinsonsmalls.com requires TLS 1.3; macOS system Python 3.9
fails the handshake. Always run through `uv run` (Python 3.12).

## Maintenance playbook

1. **Run** `uv run mallscape scrape && uv run mallscape analyze`.
2. **Read** `data/processed/<date>/report.md`:
   - *store-count drop >20%* on a mall → site may have redesigned; compare the
     cached page in `data/raw/<date>/` against the parser's expectations.
   - *NEW mall on VMD not in registry* → verify its Drupal slug, add to
     `src/mallscape/registry/robinsons_malls.json`.
   - *malls with 0 stores* → open the raw cached page and check the markup.
3. Parser changes? Re-run `uv run pytest`; re-parse without re-fetching by
   re-running scrape the same day (raw cache hits).

## Adding another chain (Ayala, Megaworld, …)

1. Subclass `MallChainScraper` (`scrapers/base.py`): implement
   `discover_malls()` and `scrape_mall()` returning the shared `Mall`/`Store`
   models.
2. Register it in `SCRAPERS` in `cli.py`.
3. Add fixture pages + tests. Everything downstream (validation, brand
   matching, analysis tables) picks the new chain up automatically.

## Etiquette

Rate-limited (default 3 req/s, `--rate` to change) with exponential backoff,
identifying user-agent, and aggressive response caching so parser development
never re-hits the sites. Keep it that way.

**Observed (2026-07):** SM's WAF issues a temporary domain-wide 403 ban after
roughly 1,500–2,000 requests in one session at 3 req/s. The ban lifts on its
own (minutes–hours). The fetcher retries 403s with long backoff and the
per-mall isolation keeps the run alive; on a re-run the raw cache resumes
where the ban hit. For SM prefer `--rate 1.5` and expect a full first scrape
to need a resume pass.
