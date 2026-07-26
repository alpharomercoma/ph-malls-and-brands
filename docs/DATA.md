# Data reference

The scraped data ships with the repository under `data/snapshots/<date>/`.
`data/raw/` (the HTTP cache) and `data/latest/` (a copy of the newest snapshot)
are not committed — the cache is large, regenerable, and rewritten in place on
re-runs, so it is scratch space rather than provenance.

## Snapshot contents

| file | rows | description |
|---|---|---|
| `malls.{parquet,csv}` | 328 | one row per property |
| `stores.{parquet,csv}` | 42,412 | one row per store listing |
| `brand_presence.*` | — | `(brand_key, chain, mall)` long-format matrix |
| `brand_summary.*` | — | per brand: malls per chain, total, chain count |
| `unique_brands.*` | — | brands present in exactly one mall |
| `mall_summary.*` | — | per mall: store count, brand count, top categories |
| `normalization_review.*` | — | raw-name variants requiring normalization review |
| `breakdown.md` | — | deterministic human-readable report (`mallscape report`) |
| `report.md` | — | validation report from the scrape run |

Parquet and CSV hold identical data. Parquet is what the code reads; CSV is
committed alongside it so the data is diffable and inspectable without pandas.

The four analysis tables are derived from `malls` + `stores` and can be
rebuilt at any time with `mallscape analyze --date <date>`.

## `malls` schema

| column | notes |
|---|---|
| `chain` | operator id (`sm`, `robinsons`, `ayala`, …) |
| `mall_id` | stable slug, unique within a chain |
| `mall_name` | display name as published |
| `region` | `metro-manila` \| `north-luzon` \| `south-luzon` \| `visayas` \| `mindanao`. Always geographic. Only three operators publish one, so the rest are inferred from name and address by `mallscape_core.geo`; resolved for 327 of 328 properties |
| `address` | street address where published |
| `mall_code` | operator-internal id (SM `mallCode`, Ayala numeric id, Contentstack uid) |
| `source_url` | the page or endpoint the data came from |
| `property_type` | `mall` \| `residential-retail` \| `amusement-park` \| `office-annex`. **Only SM is classified**; everything else defaults to `mall` |
| `scraped_at` | date this chain was actually fetched, not the snapshot date |

## `stores` schema

| column | notes |
|---|---|
| `chain`, `mall_id` | join keys to `malls` |
| `store_name_raw` | tenant name exactly as published |
| `category` | operator's own category, lowercased. Vocabularies differ per chain and are not harmonized |
| `floor` | floor/level label. Null for Ayala (their API exposes none) |
| `building` | wing/building. SM only |
| `phone` | where published |
| `source` | which parser produced the row (`sm-api`, `robinsons-drupal`, …) |

`store_name_raw` is deliberately verbatim. Cross-chain matching uses
`brand_key()` from `normalize.py`, applied at analysis time.

## Counting rules

- **Use `property_type == "mall"`** for chain-vs-chain comparison. The raw
  property count overstates SM by 25 non-mall properties.
- A row is one *listing*, not one brand. A brand with outlets on two floors is
  two listings in one mall, which is correct for store counts and deduplicated
  automatically for brand presence.
- Twelve properties have zero listings. All were checked against their source
  and are upstream gaps, not parse failures; they are listed in `breakdown.md`.

## Known accuracy limits

**WalterMart totals are a floor.** Every category page caps at 10 tenants and
no parameter lifts it, so any mall with a capped category is truncated at
source. The scrape warns per capped category.

**Ayala listing counts run high.** Their API returns duplicate
`(mall, merchant)` pairs with distinct ids but no distinguishing fields. Brand
presence is unaffected; raw listing counts are inflated by roughly 7%.

**Category vocabularies are not harmonized.** SM's `dining` and Ayala's `dine`
are not merged. Compare categories within a chain, not across.

## Regenerating

```bash
uv run mallscape scrape --chain all --date 2026-07-26   # re-parses from cache
uv run mallscape analyze --date 2026-07-26
uv run mallscape report  --date 2026-07-26
```

With the cache present this is offline and takes seconds. Without it, a full
scrape is roughly 3,000 requests; expect SM's WAF to issue a temporary 403 ban
around 1,500–2,000 requests at 3 req/s, which lifts on its own.
