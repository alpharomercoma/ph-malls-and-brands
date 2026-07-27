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

2. **Four Xentro malls list two tenants per row.** The source HTML is
   `<li>Jollibee Auto Sonix Watch Store</li>` with no delimiter. Confirmed at
   byte level; `wp-json` exposes no cleaner copy (`content.rendered` is empty,
   the content lives in page-builder post meta), and `/revisions` is 401. The
   affected malls are montalban-town-center, tanay-town-center,
   xentro-mall-calapan and xentro-mall-lemery: 381 rows. The other 13 Xentro
   malls are clean. A rescrape would return byte-identical HTML.

3. **Xentro is stale.** 16 of 19 mall pages were last modified 2019-02-11,
   seven years before the snapshot. The REST API reports this authoritatively
   in one request.

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

### P2. Detect, split and flag combined names (stage 2)

New module `2_clean/mallscape_clean/combined_names.py`.

**Detect.** Per mall, compute median token count and the rate at which a
nationally attested brand is a strict prefix. A mall is suspect when median
tokens >= 4 or prefix rate >= 0.40. Detection runs for *every* chain, not just
Xentro, so the next occurrence anywhere is caught.

**Decide.** Suspect malls are recorded in
`1_scrape/mallscape_scrape/registry/combined_name_malls.json` with the measured
evidence. The registry decides what gets split; the heuristic only proposes.
A mall that crosses the threshold without a registry entry, or an entry whose
mall no longer crosses it, is a loud warning. This follows the existing rule
that coverage facts are data, not code.

**Split.** Dictionary is national brands (in >= 3 malls, excluding the chain
under repair) plus exact names from the same chain's clean malls. Longest
attested prefix wins; failing that, longest attested suffix. The remainder
must contain a letter and be at least two characters. Splits 212 of 381 rows.

**Flag.** Both halves keep the original `store_name_raw` for lineage and carry
`split_combined_name`. The 169 rows that do not split carry
`combined_name_unsplit` and are written to a review file for a human decision;
many are genuinely single tenants and need no action.

Xentro listing counts rise. The report states this rather than absorbing it.

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

- Listing totals rise (Xentro splits) and brand totals fall (canonicalization
  plus fewer fabricated names). README, `breakdown.md` and `DATA.md` are
  regenerated, and the report states both movements.
- The splitter will be wrong on some rows. Every split is flagged and carries
  its original raw name, so it is auditable and reversible.
- Detection thresholds are tuned to current data. The registry is the decider
  precisely so that a threshold drift warns instead of silently changing data.

## Open for review

169 unsplit rows in the four affected malls are written to a review file for a
human decision. No further work depends on that review.
