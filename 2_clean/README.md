# Stage 2: clean

**Reads** `1_scrape/stores.parquet`. **Writes** `data/snapshots/<date>/2_clean/`.

| file | contents |
|---|---|
| `stores_clean.parquet` / `.csv` | every raw column, plus normalized columns |
| `category_mapping.parquet` / `.csv` | audit table: raw category to canonical, with volumes |

Run it with `uv run mallscape clean`.

## Non-destructive by contract

Stage 1 output is never modified. Every raw column survives, and normalization
is added beside it:

| column | meaning |
|---|---|
| `store_name` | display form: unicode normalized, whitespace collapsed, ALL CAPS title cased with possessives and initialisms repaired |
| `brand_key` | matching key used to join a brand across operators |
| `category_std` | one of ten canonical buckets, harmonized from 101 operator-specific strings |
| `store_format` | `atm`, `kiosk`, `cart`, `express`, `drive-thru` and so on, else `standard` |
| `floor_std` | canonical floor label |
| `floor_level` | signed integer level: basement negative, ground 0, null when the label names a place rather than a storey |
| `phone_e164` | `+63` form, null when unparseable |
| `dq_flags` | pipe separated quality flags, empty when clean |

`normalization_review.parquet` / `.csv` lists brand keys with many raw variants
or multiple cleaned variants for human review. It is diagnostic only; no raw
listing is removed from `stores_clean`.

## Tenant identity versus format

A BPI branch and a BPI ATM booth are separate mall tenants. `brand_key` keeps
that distinction (`bpi` versus `bpi atm`), while `store_format` retains the
explicit format for analysis. This prevents ATM-only locations from inflating
branch presence.

## The judgment call

**Anything that cannot be normalized confidently is kept raw and flagged, never
coerced.** A wrong but tidy value is worse than a visibly messy one, because it
survives review. "Kiosk", "Food Hall" and "Roof Deck" keep their labels and get
a null `floor_level`, since they name places rather than storeys. Ortigas
publishes a numeric category id, which becomes `unknown` rather than being
forced into a bucket.

Roughly 77 percent of floors resolve to a numeric level and 73 percent of
listings map to a category. The shortfall is almost entirely input that carries
no usable value upstream, which `category_mapping.csv` shows directly.
