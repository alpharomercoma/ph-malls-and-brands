# Stage 3: report

**Reads** `2_clean/stores_clean.parquet`, falling back to `1_scrape/stores.parquet`.
**Writes** `data/snapshots/<date>/3_report/`.

| file | contents |
|---|---|
| `brand_presence.*` | one row per brand, operator and property |
| `brand_summary.*` | per brand: properties per operator, total, operator count |
| `unique_brands.*` | brands present in exactly one property |
| `mall_summary.*` | per property: listings, distinct brands, top categories |
| `breakdown.md` | the human readable report |

Run it with `uv run mallscape report`.

## Determinism is the point

`breakdown.md` is byte identical for the same snapshot: no timestamps, every
collection sorted, fixed column widths. A diff in the report therefore always
means a diff in the data, never a difference in when it ran. A test enforces
this by building the same snapshot twice and comparing.

## What the report covers

Per-operator totals with source and fetch date, every property, properties with
zero listings, excluded operators with the finding for each, known gaps inside
scraped chains, and brand reach. Exclusions are read from the stage 1
registries rather than restated, so the report cannot drift from what the code
believes.
