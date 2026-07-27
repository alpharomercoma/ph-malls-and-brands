# Philippine Mall Explorer

A reproducible dataset of what is inside Philippine malls, and a site for
exploring it.

**303 properties, 40,462 store listings, 10,374 tenant identities, 10 operators.**
**292 properties are placed on a map.**

| | |
|---|---|
| Live site | <https://alpharomercoma.github.io/philippine-mall-explorer/> |
| Explore locally | `make dev`, then <http://localhost:3000> |
| Data | [`data/snapshots/2026-07-26/`](data/snapshots/2026-07-26/) |
| Breakdown | [`breakdown.md`](data/snapshots/2026-07-26/3_report/breakdown.md) |
| Design | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Mistakes worth not repeating | [docs/PITFALLS.md](docs/PITFALLS.md) |

## Just run it

```bash
make setup   # dependencies, plus the browser used by end-to-end tests
make all     # stages 2 to 4 over the committed snapshot
make dev     # serve the site on http://localhost:3000
```

The snapshot is committed, so nothing above touches the network. `make scrape`
re-fetches from the operators and is the only slow step.

## Follow it step by step

The pipeline is four stages. Each reads the stage before it and writes only its
own directory, so lineage is visible on disk and any stage can be rerun alone.

```
1_scrape  ->  2_clean  ->  3_report  ->  4_website
```

### 1. Scrape

```bash
uv run mallscape scrape              # every operator
uv run mallscape scrape --chain sm   # or one
```

Writes `data/snapshots/<date>/1_scrape/`: `malls`, `stores`, and a run report
that diffs against the previous snapshot. Store names are recorded verbatim;
nothing interpretive happens here. Full details in [1_scrape/README.md](1_scrape/README.md).

Cold, this is about 3,000 requests over 25 minutes. Responses are cached, so
re-parsing is free and offline.

### 1b. Geocode

```bash
uv run mallscape geocode
```

Resolves coordinates for properties the committed registry cannot already
place, and is the only command that needs the network for the map. Ordinary
runs read
[`registry/mall_coordinates.json`](1_scrape/mallscape_scrape/registry/mall_coordinates.json)
and stay offline, so the map is reproducible. Run this only when a scrape finds
properties that are new.

### 2. Clean

```bash
uv run mallscape clean
```

Writes `data/snapshots/<date>/2_clean/stores_clean.*`, which keeps every raw
column and adds normalized ones: display name, brand key, a ten-bucket category
harmonized from 101 operator-specific strings, floor label and numeric level,
phone in `+63` form, and quality flags.

Values that cannot be normalized confidently are kept raw and flagged rather
than coerced. See [2_clean/README.md](2_clean/README.md).

### 3. Report

```bash
uv run mallscape report
```

Writes analysis tables and `breakdown.md`, which is byte identical for the same
snapshot. A diff in the report always means a diff in the data. See
[3_report/README.md](3_report/README.md).

### 4. Website

```bash
uv run mallscape website --serve     # http://localhost:3000
```

Writes a content hashed JSON bundle next to a checked-in page. The list is
virtualized, search is instant, and every value is written as text rather than
markup. The Map tab draws the same result set geographically, so every filter,
the search box and the brand focus apply to both. See
[4_website/README.md](4_website/README.md).

## Operators covered

| operator | properties | malls | listings |
|---|---:|---:|---:|
| SM Supermalls | 126 | 100 | 19,640 |
| Robinsons Malls | 54 | 54 | 8,392 |
| Ayala Malls | 32 | 32 | 5,640 |
| Megaworld Lifestyle Malls | 26 | 26 | 2,118 |
| WalterMart | 46 | 46 | 1,497 |
| Ortigas Land | 4 | 4 | 1,279 |
| Filinvest Malls | 5 | 5 | 956 |
| Fisher Mall | 2 | 2 | 342 |
| Araneta City | 4 | 4 | 319 |
| Starmall | 4 | 4 | 279 |

`malls` excludes non-mall retail such as condo podiums, amusement parks and
office annexes. Compare operators on that column, not on `properties`.

## Coverage is verified, not assumed

Each operator's website is an incomplete view of its own portfolio, so rosters
are checked against corporate disclosures. SM publishes 126 properties but
around 90 malls. Robinsons reported 57 malls while their site lists 54. Ayala's
API exposes 32 of roughly 46 properties, missing Arca South and Evo City
entirely.

Eleven operators were investigated and are deliberately not scraped, including Vista
Malls, CityMall, Gaisano Grand and Puregold. Every gap is recorded as data in
`1_scrape/mallscape_scrape/registry/`, is re-reported on each run, and appears
in `breakdown.md` with the evidence.

## Accuracy limits

- **WalterMart totals are a floor.** Its category pages cap at 10 tenants
  server side and no parameter lifts the cap.
- **Ayala listing counts run about 7 percent high.** Its API returns duplicate
  merchant rows with no distinguishing fields. Brand presence is unaffected.
- **Roughly 26 percent of listings carry no usable category upstream** and are
  reported as `unknown` rather than being guessed.
- **11 properties have no coordinate** and are absent from the map, which says
  so under it rather than quietly dropping them. Most are SMDC retail podiums
  that no public gazetteer lists. Of the 292 that are placed, 251 sit on the
  building; 41 resolve only to a street or a town and are drawn hollow.

## Configuration

Every operational value reads from the environment with a working default, so
the pipeline runs with nothing set. Copy `.env.example` only to change
something. An invalid value fails immediately and names itself rather than
being ignored.

## Tests

```bash
make check   # lint, unit, integration
make e2e     # drives the built site in a real browser
```

| layer | what it protects |
|---|---|
| lint | style and dead code, via ruff |
| unit | parsers against frozen fixtures, with exact expected counts |
| integration | the handoff between stages, including carry-forward and schema |
| end to end | the built site: bundle validity, search, virtualization, mobile layout, map plotting and filtering, no script errors |

## Etiquette

Rate limited to 3 requests per second with backoff and an identifying user
agent, and every response cached so parser work never re-hits a site.

## Open items

- `region` is null for one property, SMBY Amusement Park, which publishes
  neither an address nor a resolvable coordinate.
- `property_type` is classified only for SM, so a non-mall property from
  another operator still compares against SM malls as a peer.
- Gaisano Capital, LCC Group and NCCC are blocked or unconfirmed rather than
  proven directory-less. Each needs a browser session.
