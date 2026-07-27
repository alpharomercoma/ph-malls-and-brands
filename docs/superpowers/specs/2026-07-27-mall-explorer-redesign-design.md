# Philippine Mall Explorer: data correctness and interface redesign

Date: 2026-07-27
Status: approved design, pending implementation plan

## Why

Two questions drove this: "let me search a brand and see which malls have it",
and "does every part of the visualization earn its keep". Auditing the data to
answer the second one surfaced defects that make the first one untrustworthy,
so this spec covers both.

## Findings the design responds to

1. **Ortigas categories are unresolved foreign keys.** `category` holds `1`,
   `4`, `9`. The lookup (`1=Shop, 4=Dining, 7=Chapel, 9=Bank`) is in the same
   Inertia payload we already cache. 1,075 of 1,279 Ortigas listings are
   `unknown` for no reason.

2. **XentroMalls was removed entirely on 2026-07-27.** Four of its 19 mall
   pages listed two tenants per line with no delimiter, verified at byte level,
   with no cleaner source available and no XHR to intercept. Separately, 16 of
   19 pages had not been edited since 2019-02-11. The operator is recorded in
   `registry/unscraped_chains.json` with that evidence. The detector described
   in P2 remains, because the next operator to do this must not go unnoticed.

4. **There is no brand resolution step.** `brand_key` is a normalized string,
   so `starbucks coffee` (79 malls) and `starbucks` (57) are two brands and
   Starbucks ranks wrong. Same for `national bookstore` / `national book store`.

5. **Categories are not comparable across operators.** `shopping` (9,004) is
   each operator's own catch-all; `fashion` (159) exists almost only because
   Filinvest labels apparel specifically. Bench is `fashion` in Filinvest,
   `shopping` in six chains and `unknown` in five. Propagating the most
   specific label a brand carries anywhere recovers 50% of `unknown` and 52%
   of `shopping`, about 10,490 listings.

6. **The Share bar is misleading.** It is `brand malls / properties in scope`
   with no label, no denominator and no number, floored at 2% so a brand in 1
   of 296 malls draws the same mark as one in 6.

7. **Stat tiles do not respond to filters** while the count, the bar and the
   map do. Filtering to Visayas still reports 322 properties.

8. **The Properties tab duplicates the map.** Same set, same filters, and the
   map already carries a property list and a detail popup.

## Pipeline changes

### P1. Resolve Ortigas categories (stage 1)

Parse `props.categories` from the cached Inertia payload into `{id: name}` and
map each store's id. An id absent from the lookup keeps its raw value and
raises a scraper warning rather than passing through as data.

### P2. Detect combined names and recover brands without splitting (stage 2)

New module `2_clean/mallscape_clean/combined_names.py`.

**Status.** The chain that prompted this has since been removed, so nothing in
the current snapshot is flagged. The detector stays because the defect is not
unique to one operator, and silence must not be mistaken for absence.

**Why not split.** Splitting was attempted and rejected on measurement. A
one-sided longest-attested-prefix/suffix rule splits 212 of 381 rows at roughly
67% precision, and its failure modes are the damaging kind: `CEBUANA LHUILLIER`
becomes `cebuana` + `lhuillier`, destroying a real brand; `RCBC ATM` becomes
`rcbc` + `atm`, inventing a phantom tenant and breaking the deliberate
bank/ATM separation; `FRESH SALON AND SPA CA EXHIBITS ( PROPERTY PRO )` splits
at the wrong point entirely. Requiring both halves to be attested raises
precision but resolves only 45 of 381. No threshold makes guessing a split
point safe, because the delimiter genuinely is not in the data.

**Detect.** Per mall, compute median token count and the rate at which a
nationally attested brand is a strict prefix. A mall is suspect when median
tokens >= 4 or prefix rate >= 0.40. Detection runs for *every* chain, so the
next occurrence anywhere is caught.

**Decide.** Suspect malls are recorded in
`1_scrape/mallscape_scrape/registry/combined_name_malls.json` with the measured
evidence. The registry decides; the heuristic only proposes, and disagreement
in either direction is a loud warning. Coverage facts are data, not code.

**Recover brands by mention, not by splitting.** For rows in flagged malls:

* the raw string does **not** become a brand, which removes the fabricated
  brand keys those malls currently contribute;
* the row is scanned for occurrences of attested brands as whole words,
  longest match first, scanning continuing after each match so one brand is
  never found inside another;
* each match emits a brand-to-property association;
* the listing row itself is kept verbatim and flagged `combined_name`.

The vocabulary is national brands only: attested in >= 3 malls across other
chains, raised to >= 8 for single-word names so a generic word is not mistaken
for a brand. Xentro's own clean malls are deliberately excluded, because
including them readmits descriptors like `barber shop` and `exhibit`.

This recovers 182 correct associations from 160 of the 381 rows. The remainder
are purely local businesses (`ANX KABAYAN PAWNSHOP`, `BUGS BUNNY BARBER SHOP`)
that exist in no other mall and so could never be reached by a brand search
anyway. Nothing is invented, no real brand is broken, listing totals are
unchanged, and no manual review is required.

It is a pure function of the snapshot, so it is fully repeatable and pins
directly into regression tests. These cases are fixed as unit tests:

| input | expected |
|---|---|
| `CEBUANA LHUILLIER` | `[cebuana lhuillier]` — one brand, not two |
| `RCBC ATM` | `[rcbc atm]` — ATM stays distinct from the bank |
| `SAMSUNG MOBILE CAPTAINS BURGER` | `[samsung]` |
| `JOLLIBEE MINI GEM EXHIBIT (29)` | `[jollibee]` |
| `BUGS BUNNY BARBER SHOP` | `[]` — no generic-word false positive |

### P3. Brand resolution (stage 2)

New module `2_clean/mallscape_clean/brands.py` adding `brand_canonical`
alongside `brand_key`.

A committed `registry/brand_aliases.json` holds explicit equivalences
(`starbucks coffee -> starbucks`). Automatic near-match detection only
*proposes* candidates into `normalization_review.csv`; nothing merges unless it
is written down. This preserves the deliberate BPI / BPI ATM separation: an
allow-list cannot merge two entities by accident.

### P4. Category propagation (stage 2)

Rank buckets by specificity, with `unknown` and `shopping` marked generic. A
brand's most specific label anywhere becomes its label everywhere. New
`category_source` column: `operator` | `propagated`.

Known limit, stated in the docs rather than hidden: brands no operator ever
labels specifically (Uniqlo, Zara) stay generic. Filinvest is effectively the
only source of fine-grained retail labels.

### P5. Source freshness (stage 1)

Record `source_updated` per property where the source publishes it. Xentro's
WordPress REST API gives all 19 in one request. Null elsewhere until another
chain offers it. Surfaced as a property flag when the directory is over two
years old.

## Site changes

### S1. Two views, map first

`Map` is the default view and absorbs `Properties`. Its side list becomes the
property list: sortable, filtered by the same controls, operator shown on the
row, click to fly and open the popup. The popup is the property detail, so the
row-expansion detail panel is deleted. On viewports under 900px the list moves
below the map instead of being hidden, since it is now the only property list.

`Brands` remains the ranked table.

### S2. Reach replaces Share

Brands view columns become `Brand | Category | Reach (of N malls)`, the cell
reading `171 · 58%`. The header names the denominator and both follow the
current filters. The bar, `barCell()` and all `.bar*` CSS are deleted.

### S3. One search box that answers the brand question

The box filters property names as now, and additionally surfaces matching
brands as chips beneath it (`Uniqlo · 64 malls`). Clicking a chip focuses the
map on those malls.

When a query matches no property but does match a brand, the empty state says
so instead of showing an empty map:

> No property is named "uniqlo". **Uniqlo** is a brand in 64 malls — show them.

### S4. Tiles and caveats

Five tiles become three, and they respond to the filters: `Properties` (with
"of which N malls" as a sub-line), `Listings`, `Brands`. `Operators` moves to
the subtitle, where the count already appears. The permanent "How to read this
data" block becomes a one-line disclosure that expands.

### S5. Deleted

Properties tab · Share column and `.bar*` CSS · mall row-expansion detail ·
two stat tiles · the always-open caveat block.

The Category facet is kept, but only because P4 makes it mean something.
Without propagation it filters on "words this operator happens to use".

## Schema

Bundle schema goes to 4. `stores_clean` gains `brand_canonical`,
`category_source`; `malls` gains `source_updated`. `dq_flags` gains
`split_combined_name` and `combined_name_unsplit`.

## Verification

**Unit.** Ortigas id mapping including an unknown id; combined-name detection
on a clean and a glued mall; splitter longest-prefix, suffix fallback, empty
remainder, no match; alias resolution refusing an unlisted merge; category
specificity vote.

**Integration.** Bundle carries `brand_canonical` and `category_source`; reach
denominator tracks filters; split rows keep lineage to `store_name_raw`;
registry drift raises.

**End to end.** Map is the default view; brand chip filters the map; the
zero-property-one-brand empty state appears; no Properties tab; the list sits
below the map on a phone; reach shows a denominator.

## Risks

- Listing totals are unchanged; brand totals fall, from canonicalization and
  from flagged malls no longer contributing fabricated names. README,
  `breakdown.md` and `DATA.md` are regenerated and the report states it.
- Mention detection has limited recall on purely local businesses. That is a
  deliberate trade: a missing association for a shop that exists in one mall
  costs nothing, while a phantom association would undermine brand search.
- Detection thresholds are tuned to current data. The registry is the decider
  precisely so that a threshold drift warns instead of silently changing data.

## Open for review

None. Combined names are resolved autonomously by mention detection, so there
is no manual review queue and no step that has to be repeated by hand when the
data changes.
