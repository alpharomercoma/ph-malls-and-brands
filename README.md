# mallscape

Recurring scraper and brand-presence dataset for Philippine mall directories.
**328 properties · 42,412 store listings · 12 operators**, refreshed on a
schedule and diffed against the previous run.

| | |
|---|---|
| Data | [`data/processed/2026-07-26/`](data/processed/2026-07-26/) — committed, see [docs/DATA.md](docs/DATA.md) |
| Breakdown | [`breakdown.md`](data/processed/2026-07-26/breakdown.md) — every chain and property |
| Design | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Hard-won lessons | [docs/PITFALLS.md](docs/PITFALLS.md) |

## Quick start

```bash
uv sync
uv run mallscape scrape     # all chains (~25 min cold; seconds from cache)
uv run mallscape analyze    # brand-presence tables
uv run mallscape report     # deterministic breakdown -> breakdown.md
uv run pytest               # 37 offline regression tests
```

Re-run monthly or weekly. Each run writes a dated snapshot, diffs itself
against the previous one, and reports anomalies.

## Chains

| chain | properties | malls | listings | source |
|---|---:|---:|---:|---|
| sm | 126 | 101 | 19,640 | JSON API |
| robinsons | 54 | 54 | 8,392 | Drupal HTML + Google Sites fallback |
| ayala | 32 | 32 | 5,640 | explore-v2 JSON API |
| megaworld | 26 | 26 | 2,118 | Contentstack headless CMS |
| waltermart | 46 | 46 | 1,497 | server-rendered HTML |
| ortigas | 4 | 4 | 1,279 | Laravel/Inertia embedded JSON |
| xentro | 19 | 19 | 1,006 | server-rendered HTML |
| filinvest | 5 | 5 | 956 | server-rendered table |
| gmall | 6 | 6 | 944 | server-rendered DataTable |
| fishermall | 2 | 2 | 342 | HTML fragment endpoint |
| araneta | 4 | 4 | 319 | server-rendered HTML |
| starmall | 4 | 4 | 279 | Elementor JSON-escaped blob |

`malls` excludes non-mall retail (condo podiums, amusement parks, office
annexes). **Filter to `property_type == "mall"` before comparing chains.**

Per-chain scraping notes — endpoints, gotchas, dead domains — live in each
module's docstring under `src/mallscape/scrapers/`.

## Coverage is verified, not assumed

Each operator's own website is an incomplete view of its portfolio, so the
roster is checked against corporate disclosures:

| chain | operator's own count | we scrape | the gap |
|---|---|---|---|
| SM | ~80–90 malls (SM Prime) | 126 properties, 101 malls | the rest are SMDC podiums, Sky Ranch parks, office annexes |
| Robinsons | 57 malls (RLC, end-2025) | 54 properties | 7 Townville community malls + The Mall @ NUSTAR publish no directory |
| Ayala | ~46 properties | 32 | Arca South (2026), Evo City (2025) and ~12 strips are absent from Ayala's own API |
| GMall | 6 branches | 6 | Cebu and GenSan publish no tenant rows |

Known gaps are **data**, not footnotes: `src/mallscape/registry/*_coverage.json`
records each one with its evidence, and every run re-reports them — including
the good case, where a previously missing mall appears upstream and should be
promoted out of the registry.

Operators investigated and deliberately **not** scraped — Vista Malls, Primark,
CityMall, Gaisano Grand, Gaisano Capital, LCC, NCCC, LTS, Shangri-La Plaza,
Puregold — are in `registry/unscraped_chains.json` with the finding and
re-check criteria for each. `breakdown.md` reproduces this in full.

## Accuracy limits worth knowing

- **WalterMart totals are a floor.** Category pages cap at 10 tenants server-side
  and no parameter lifts it. Capped categories emit a warning per run.
- **Ayala listing counts run ~7% high** — their API returns duplicate
  `(mall, merchant)` pairs with no distinguishing fields. Brand presence is
  unaffected.
- **Category vocabularies are per-chain** and not harmonized.

## Etiquette

Rate-limited (3 req/s default), exponential backoff, identifying user-agent,
and a response cache so parser work never re-hits the sites. SM's WAF issues a
temporary domain-wide 403 after roughly 1,500–2,000 requests in a session; it
lifts on its own and the fetcher retries with long backoff. Prefer
`--rate 1.5` for SM.

## Open items

- `region` is null for all Megaworld (26) and XentroMall (19) properties.
  Megaworld has addresses for all 26 and `ayala.derive_region()` would resolve
  them; it simply is not called. XentroMall parses no address at all.
- `property_type` is classified only for SM, so XentroMall's
  `sta-ana-public-market` currently compares against SM malls as a peer.
- `megaworld._entries()` loops without a page guard, unlike `sm.MAX_PAGES`.
- Gaisano Capital, LCC Group and NCCC are blocked or unconfirmed rather than
  proven directory-less; each needs a browser session.
