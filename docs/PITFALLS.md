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

One scraper dropped any name ending in `.` as noise. Real tenants end in
`INC.`, `CORP.`, `ACC.` — 21 of them vanished.

**Rule:** filters must target the specific junk observed, by its own
vocabulary or structure, never by a generic shape that legitimate data shares.
The leasing-form filter in the same module is the right pattern: it matches the
checklist's actual wording.

## Assuming one markup shape

One community mall rendered its tenants as `<br>`-separated text inside a
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
used for tenants, so a rates paragraph parsed as a store. One site rendered
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
lander, and `shangrilaplaza.com.ph` is for sale.
Search results and old links point at all of them.

**Rule:** confirm the live domain before writing a scraper, and record the dead
ones so nobody re-adds them.

## A validator strict enough to reject the right answer

The geocoder accepted a candidate only if the region derived from its
coordinates equalled the region already recorded for the property. That sounds
conservative. It is not: `derive_region()` falls back to coarse latitude and
longitude boxes, and the Metro Manila box reaches well into Cavite and Bulacan.
So the correct OpenStreetMap feature for "SM City Bacoor" derived to
`metro-manila`, the property was recorded as `south-luzon`, and the exact
name match was thrown away. Twenty-two properties were rejected this way.

Two independent signals, both fallible, must be combined rather than ANDed. The
rule now is that a candidate needs an exact name **or** a corroborating region.
A merely similar name in the wrong region is still rejected.

## A containment rule that matched everything

The same matcher gave a 0.93 score whenever one name's distinctive tokens were
a subset of the other's, in either direction. "SM Store" is a subset of "SM
City Bacoor", so every branch supermarket in the country scored 0.93 against
every SM property. Once the real match was rejected by the bug above, two of
these near-ties 400 km apart made the property "ambiguous".

Containment is only evidence in one direction: the candidate may add tokens to
ours, never drop them. Subset matching also needs a floor on how many tokens
are being matched, or a one-word name matches the whole dataset.

## Output that becomes input

`attach()` skipped any row that already had a coordinate, so the second run
treated its own output as operator-supplied truth. Deleting the registry and
regenerating it therefore preserved 249 coordinates that were no longer in it,
and the committed registry stopped describing the committed data.

A column with two owners needs a field that says which one wrote each value.
The test is now `geo_source == "operator"`, not `lat is not None`, and a row the
registry cannot answer has its coordinate cleared rather than kept.

## Regexes that match the comment above the code

The build rewrites the page's `img-src` so the tile host and the policy
permitting it cannot drift. `img-src [^;]*;` matched the words "img-src" in the
HTML comment explaining the tag, consumed everything up to the first semicolon
of the real policy, and rewrote the comment while leaving the policy untouched.
The substitution reported success because it did replace exactly one match.

Anchor a rewrite to the structure it targets, not to a string that also appears
in prose. Counting substitutions proves something was replaced, not that the
right thing was.

## A filter that means different things in different views

The search box matches brand names in the brand view and property names in the
property view. "Show these on the map" carried the query across, so searching
"uniqlo", then asking to see its 64 malls, produced an empty map: no property
is named Uniqlo. The button had just promised 64.

When one control changes meaning across views, switching views has to decide
explicitly what happens to it. Here the brand focus is the more specific
expression of the same intent, so it replaces the query rather than stacking
with it.

## A foreign key stored as if it were a value

Ortigas publishes `store.type` as `1`, `4`, `9`, and ships the lookup in the
same payload under `props.categories` (`1=Shop, 4=Dining, 9=Bank`). The scraper
stored the integer. Everything downstream saw a number where it expected a
word, mapped it to `unknown`, and 1,075 listings lost a category that was
sitting in the response the whole time.

When a field is small integers and the payload has a sibling collection, it is
a key, not a value. The parser now resolves it and warns on an id the lookup
does not contain.

## A category taxonomy that compares vocabularies, not tenants

Each operator has a catch-all bucket, and they are not the same bucket.
`shopping` held 9,004 listings across six chains, while `fashion` held 159 and
came almost entirely from Filinvest, the only operator that labels apparel
specifically. Bench was `fashion` at Filinvest, `shopping` at SM and `unknown`
at Robinsons: one brand, eleven labels. Filtering by category returned malls
whose operator used that word.

The fix is to categorize the brand rather than the listing: the most specific
label a brand carries anywhere becomes its label everywhere, with `unknown` and
`shopping` explicitly ranked as generic so a real label always wins. That moved
category coverage from 73.8% to 89.5% and gave Robinsons 652 fashion listings
where it had zero.

## Normalizing a name is not resolving an entity

`brand_key` lowercases and folds punctuation. It does not decide that two
names are the same business, so `starbucks` (57 malls) and `starbucks coffee`
(79) were two brands and neither number was Starbucks' reach. Thirty-eight such
pairs existed among brands present in five or more malls.

Resolution is a separate step, and it must be an explicit allow-list. A
similarity threshold high enough to catch `national book store` /
`national bookstore` (0.973) also catches `mi store` / `sm store` (0.875),
which are Xiaomi and The SM Store. The registry now records the merges *and*
the rejected pairs, so the same false positive is not re-argued every time.

## Counting a marker that only exists in a template

Checking whether three WalterMart malls had tenants, a `grep -c wm-store`
returned 90 for each, which looked like a directory we had failed to parse. The
matches were the hidden modal template (`id="wm-store-name"`), present on every
page whether or not it has tenants. Parsing properly returned zero anchors for
those malls and 22 for a control.

Count the thing, not a string that appears near the thing. A control page with
a known answer turns a plausible number into a checkable one.
