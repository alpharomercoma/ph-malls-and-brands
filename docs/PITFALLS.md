# Pitfalls

Every entry here is a bug that actually shipped in this repo and silently lost
or corrupted data. They are recorded because the same mistakes recur when
adding a chain, and because several survived a first audit that pronounced the
data sound.

## The meta-lesson

Re-parsing the same cached input twice and getting identical output proves
**stability, not correctness**. All twelve scrapers passed that check while
four of them were quietly dropping records.

What actually catches this class of bug is comparing a parser's output against
what the *source itself claims to contain*:

- the site's own filter/nav list vs. the malls you produced
- the API's reported `count` vs. the rows you kept
- the raw element count in the cached HTML vs. the parsed row count
- a category page that returns exactly N every time (a cap, not a coincidence)

Write that comparison **before** declaring a chain done.

## Dedupe keys that silently merge distinct records

SM's dedupe keyed on `tenant_slug`. About 1% of SM records ship with an *empty*
slug, so the key silently degraded to the display name and merged genuinely
distinct outlets — two Potato Corners on different floors of the same mall
became one. 238 records lost. Worse, because SM's pagination is not a stable
sort, *which* floor survived varied between fetches.

**Rule:** a dedupe key must include every field that distinguishes two real
records, and must not silently degrade when part of it is missing.

## Deriving a roster from data instead of from the roster

One chain's mall list was derived from its tenant table's branch column. Two
branches were offered by the site's own filter but carried zero tenant rows, so
they never became malls at all: a chain-level undercount invisible in every
report, including the zero-store list.

**Rule:** derive the roster from the site's roster (filter, nav, index), then
attach data to it. Never infer existence from the presence of data.

## Partial unescaping

Starmall's directory sits in a JSON-escaped blob. The parser decoded
`"`, `<`, `>` by hand and stopped there — so `'`
(apostrophe) survived into store names. `brand_key("BAKER'S FAIR")`
produced `baker u0027s fair`, making 21 tenants invisible to the cross-chain
brand matching that is the point of the dataset.

**Rule:** decode the whole escape class (`\\u[0-9a-fA-F]{4}`), never a
hand-picked subset. Corruption that survives into a *key* is worse than
corruption in a display field.

## Cosmetic filters that eat real data

XentroMall dropped any name ending in `.` as noise. Real tenants end in
`INC.`, `CORP.`, `ACC.` — 21 of them vanished.

**Rule:** filters must target the specific junk observed, by its own
vocabulary or structure, never by a generic shape that legitimate data shares.
The leasing-form filter in the same module is the right pattern: it matches the
checklist's actual wording.

## Assuming one markup shape

XentroMall's ShopKing renders its tenants as `<br>`-separated text inside a
`<ul>` with zero `<li>` elements. The parser read `<li>` only, produced zero
stores, and the mall was filed as a verified upstream gap. It published 27
tenants.

**Rule:** when a page yields zero rows, prove the page is empty before
recording it as an upstream gap. "Zero" is a claim that needs evidence.

## Documentation that asserts the opposite of reality

`waltermart.py` stated that category pages were the authoritative uncapped
source. In fact every category page caps at 10 tenants, the mall page returns
an identical set, and no `page`/`offset`/`limit`/`show=all` parameter lifts it.
The chain's totals are a **floor**, and the docstring said otherwise.

**Rule:** a docstring claiming completeness needs the same evidence as a
completeness assertion in code. If you cannot cite the test, do not write the
claim.

## Site-reused markup

Robinsons puts parking-rate notices inside `li.store-name`, the same element
used for tenants, so a rates paragraph parsed as a store. XentroMall renders
its leasing-requirements checklist in the same `div.zn_text_box` as tenant
lists.

**Rule:** container-based selectors need a content-based guard when a site
reuses the container for prose.

## Non-mall properties counted as malls

SM's directory returns 126 properties, of which 20 are SMDC condo retail
podiums, 3 are Sky Ranch amusement parks and 2 are office annexes. Comparing
that 126 against Ayala's 32 overstates SM by a quarter.

**Rule:** classify `property_type` and filter to `mall` before any
chain-vs-chain comparison. Currently only SM is classified — see the open items
in `README.md`.

## Stale and parked domains

Three operators' "official" sites were dead: `megaworldlifestylemalls.com` (no
hyphen) now redirects to an ad/scam domain, `filinvestmalls.com` is a parked
lander, and `xentromall.com.ph` and `shangrilaplaza.com.ph` are both for sale.
Search results and old links point at all of them.

**Rule:** confirm the live domain before writing a scraper, and record the dead
ones so nobody re-adds them.
