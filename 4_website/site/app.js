/* Philippine Mall Explorer
 *
 * Three constraints drive the design:
 *   Size    the bundle is columnar with integer indices, so it stays small
 *           enough for a phone. It is fetched once and kept in memory.
 *   Speed   tens of thousands of tenant identities never all reach the DOM. A fixed row
 *           height lets the list render only the visible window plus an overscan, so
 *           scrolling cost is constant regardless of result count.
 *   Safety  every value from the data is written with textContent. No innerHTML
 *           and no template interpolation of data anywhere, so a store name can
 *           never become markup. The page also runs under a strict CSP with no
 *           inline script.
 */

import * as mapview from './map.js';

const ROW_HEIGHT = 44;   // must match --row-h in styles.css
const OVERSCAN = 6;      // rows rendered beyond the viewport, to hide scroll seams
const POPUP_BRANDS = 6;  // brands named in a map popup before it gets unwieldy

const state = {
  data: null,
  view: 'map',   // the map is the landing view; the list is one tab away
  query: '',
  chain: new Set(),
  region: new Set(),
  category: new Set(),
  mallsOnly: false,
  brandFocus: null,      // brand index; a property-scoped filter set from a brand row
  expanded: null,
  rows: [],
};

const el = (id) => document.getElementById(id);
const fmt = (n) => n.toLocaleString('en-US');
// dictionary keys are slugs (metro-manila, health_beauty); show them as words
const SPECIAL = { smdc: 'SMDC', sm: 'SM' };
const label = (s) =>
  SPECIAL[s] ||
  s.replace(/[_-]/g, ' ').replace(/\b[a-z]/g, (c) => c.toUpperCase());

/* ---------- loading ---------- */

async function load() {
  const src = document.body.dataset.bundle;
  if (!src) throw new Error('missing data-bundle attribute on <body>');
  const res = await fetch(src, { cache: 'force-cache' });
  if (!res.ok) throw new Error(`could not load data (${res.status})`);
  const data = await res.json();
  if (!data || data.schema !== 4) {
    throw new Error(`unsupported bundle schema: ${data && data.schema}`);
  }
  return data;
}

/* ---------- derived indexes, built once ---------- */

function prepare(data) {
  // Lowercased names for search. Doing this once turns every keystroke into a
  // plain substring scan over a flat array, which stays well under a frame.
  const aliases = data.aliases || {};
  data.brandSearch = data.brands.map(
    (b, i) => (aliases[i] ? `${b[0]} ${aliases[i]}` : b[0]).toLowerCase(),
  );
  data.mallSearch = data.malls.map((m) => m[0].toLowerCase());

  // brand -> its malls, from the flat edge pairs
  data.brandMalls = data.brands.map(() => []);
  data.mallBrands = data.malls.map(() => []);
  for (let i = 0; i < data.edges.length; i += 2) {
    const b = data.edges[i];
    const m = data.edges[i + 1];
    data.brandMalls[b].push(m);
    data.mallBrands[m].push(b);
  }
  return data;
}

/* ---------- filtering ----------
 * Filters are multi-select. Within one facet the values are OR'd (Ayala or SM),
 * across facets they are AND'd (an Ayala mall AND in Visayas). That is what
 * people expect from faceted search, and it means widening one facet never
 * silently narrows another.
 *
 * Each facet's option counts are computed with every OTHER facet applied but
 * not itself, so the numbers show what selecting an option would actually add
 * rather than what is on screen now. Options that would return nothing are
 * disabled instead of hidden, so the shape of the data stays visible.
 */

function mallPasses(mallIdx, { skipRegion = false } = {}) {
  const d = state.data;
  const m = d.malls[mallIdx];
  if (!skipRegion && state.region.size && !state.region.has(d.dict.regions[m[2]])) return false;
  if (state.mallsOnly && d.dict.propertyTypes[m[3]] !== 'mall') return false;
  return true;
}

function brandPasses(i, opts = {}) {
  const d = state.data;
  const b = d.brands[i];
  const { skipChain = false, skipCategory = false, skipRegion = false } = opts;

  if (state.query && !d.brandSearch[i].includes(state.query)) return false;
  if (!skipCategory && state.category.size) {
    const cats = d.brandCategories[i] || (b[1] >= 0 ? [b[1]] : []);
    if (!cats.some((c) => state.category.has(d.dict.categories[c]))) return false;
  }
  // chain, region and property type all live on the malls this brand occupies,
  // so one pass over them answers every remaining facet at once
  const malls = d.brandMalls[i];
  const needChain = !skipChain && state.chain.size > 0;
  const needMall = needChain || state.region.size > 0 || state.mallsOnly;
  if (!needMall) return true;
  for (let k = 0; k < malls.length; k++) {
    const mi = malls[k];
    if (needChain && !state.chain.has(d.dict.chains[d.malls[mi][1]])) continue;
    if (!mallPasses(mi, { skipRegion })) continue;
    return true;
  }
  return false;
}

function matchingBrands() {
  const d = state.data;
  const out = [];
  for (let i = 0; i < d.brands.length; i++) if (brandPasses(i)) out.push(i);
  out.sort((a, b) => brandMallCount(b) - brandMallCount(a) || (d.brands[a][0] < d.brands[b][0] ? -1 : 1));
  return out;
}

function matchingMallsForBrand(i) {
  const d = state.data;
  return d.brandMalls[i].filter((mi) => {
    const mall = d.malls[mi];
    return (!state.chain.size || state.chain.has(d.dict.chains[mall[1]])) && mallPasses(mi);
  });
}

function brandMallCount(i) {
  return matchingMallsForBrand(i).length;
}

function scopedMalls() {
  const d = state.data;
  const out = [];
  for (let i = 0; i < d.malls.length; i++) {
    const mall = d.malls[i];
    if (state.chain.size && !state.chain.has(d.dict.chains[mall[1]])) continue;
    if (!mallPasses(i)) continue;
    out.push(i);
  }
  return out;
}

function matchingMalls() {
  const d = state.data;
  // A brand focus narrows the properties to the ones carrying that brand. It
  // only exists in the property-shaped views, so it is tested here rather than
  // in mallPasses, which brand filtering also runs through.
  const focus = state.brandFocus === null ? null : new Set(d.brandMalls[state.brandFocus]);
  const out = [];
  for (let i = 0; i < d.malls.length; i++) {
    const m = d.malls[i];
    if (focus && !focus.has(i)) continue;
    if (state.query && !d.mallSearch[i].includes(state.query)) continue;
    if (state.chain.size && !state.chain.has(d.dict.chains[m[1]])) continue;
    if (!mallPasses(i)) continue;
    if (state.category.size) {
      const brands = d.mallBrands[i];
      let ok = false;
      for (let k = 0; k < brands.length; k++) {
        const bi = brands[k];
        const cats = d.brandCategories[bi] || (d.brands[bi][1] >= 0 ? [d.brands[bi][1]] : []);
        if (cats.some((c) => state.category.has(d.dict.categories[c]))) { ok = true; break; }
      }
      if (!ok) continue;
    }
    out.push(i);
  }
  out.sort((a, b) => d.malls[b][4] - d.malls[a][4] || (d.malls[a][0] < d.malls[b][0] ? -1 : 1));
  return out;
}

/** How many results each option of one facet would yield, with the other
 *  facets still applied. */
function facetCounts(facet) {
  const d = state.data;
  const counts = new Map();
  if (state.view !== 'brands') {
    const focus = state.brandFocus === null ? null : new Set(d.brandMalls[state.brandFocus]);
    for (let i = 0; i < d.malls.length; i++) {
      const m = d.malls[i];
      if (focus && !focus.has(i)) continue;
      if (state.query && !d.mallSearch[i].includes(state.query)) continue;
      if (facet !== 'chain' && state.chain.size && !state.chain.has(d.dict.chains[m[1]])) continue;
      if (!mallPasses(i, { skipRegion: facet === 'region' })) continue;
      const key = facet === 'chain' ? d.dict.chains[m[1]]
                : facet === 'region' ? (m[2] >= 0 ? d.dict.regions[m[2]] : null)
                : null;
      if (facet === 'category') {
        for (const bi of d.mallBrands[i]) {
          const cats = d.brandCategories[bi] || (d.brands[bi][1] >= 0 ? [d.brands[bi][1]] : []);
          for (const c of cats) {
            const name = d.dict.categories[c];
            counts.set(name, (counts.get(name) || 0) + 1);
          }
        }
      } else if (key) counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  }
  for (let i = 0; i < d.brands.length; i++) {
    const opts = { skipChain: facet === 'chain', skipCategory: facet === 'category', skipRegion: facet === 'region' };
    if (!brandPasses(i, opts)) continue;
    if (facet === 'category') {
      const cats = d.brandCategories[i] || (d.brands[i][1] >= 0 ? [d.brands[i][1]] : []);
      for (const c of cats) {
        const name = d.dict.categories[c];
        counts.set(name, (counts.get(name) || 0) + 1);
      }
      continue;
    }
    const seen = new Set();
    for (const mi of d.brandMalls[i]) {
      const m = d.malls[mi];
      if (!mallPasses(mi, { skipRegion: facet === 'region' })) continue;
      // Counting one facet must still respect the others. Without both of
      // these, selecting an operator left region counts computed over every
      // mall the brand occupies, so regions that operator does not reach still
      // showed a non-zero count and stayed enabled.
      if (facet === 'chain' && state.region.size && m[2] >= 0 && !state.region.has(d.dict.regions[m[2]])) continue;
      if (facet === 'region' && state.chain.size && !state.chain.has(d.dict.chains[m[1]])) continue;
      const key = facet === 'chain' ? d.dict.chains[m[1]] : (m[2] >= 0 ? d.dict.regions[m[2]] : null);
      if (key && !seen.has(key)) { seen.add(key); counts.set(key, (counts.get(key) || 0) + 1); }
    }
  }
  return counts;
}

/* ---------- rendering ---------- */

function cell(className, text) {
  const div = document.createElement('div');
  div.className = className;
  div.textContent = text;          // never innerHTML: data can contain anything
  return div;
}

/** The count, and that count as a share of the malls in scope.
 *
 * This replaced an unlabelled bar with no denominator and a 2% floor, which
 * drew the same mark for a brand in 1 mall as for one in 6. A number with its
 * denominator named in the column header cannot mislead the same way. */
function reachCell(value, total) {
  const wrap = document.createElement('div');
  wrap.className = 'n reach';
  const n = document.createElement('b');
  n.textContent = fmt(value);
  const pct = document.createElement('span');
  pct.className = 'pct';
  pct.textContent = total > 0 ? `${Math.round((value / total) * 100)}%` : '';
  wrap.append(n, pct);
  return wrap;
}

function buildRow(index, total) {
  const d = state.data;
  const row = document.createElement('button');
  row.className = 'row';
  row.type = 'button';
  row.setAttribute('aria-expanded', String(state.expanded === index));

  {
    const b = d.brands[index];
    const count = brandMallCount(index);
    row.appendChild(cell('name', b[0]));
    row.appendChild(cell('muted hide-sm', b[1] >= 0 ? label(d.dict.categories[b[1]]) : 'unlabelled'));
    row.appendChild(reachCell(count, total));
    row.setAttribute('aria-label',
      `${b[0]}, in ${count} of ${total} malls matching your filters`);
  }
  row.addEventListener('click', () => {
    state.expanded = state.expanded === index ? null : index;
    renderList();
  });
  return row;
}

function buildDetail(index) {
  const d = state.data;
  const box = document.createElement('div');
  box.className = 'detail';
  const h = document.createElement('h3');
  const pills = document.createElement('div');
  pills.className = 'pills';

  {
    const malls = matchingMallsForBrand(index).sort((a, b) => d.malls[b][4] - d.malls[a][4]);
    h.textContent = `Present in ${malls.length} ${malls.length === 1 ? 'mall' : 'malls'}`;
    const placed = malls.filter((mi) => d.malls[mi][5] !== null).length;
    if (placed > 0) {
      const toMap = document.createElement('button');
      toMap.type = 'button';
      toMap.className = 'chip chip--map';
      toMap.textContent = `Show ${fmt(placed)} on the map`;
      toMap.addEventListener('click', (event) => {
        event.stopPropagation();
        state.brandFocus = index;
        // The query that found this brand matches brand names. In the
        // property-shaped views it matches property names instead, so
        // searching "uniqlo" and then asking for its malls would leave a
        // filter no property can satisfy and an empty map. The focus is the
        // more specific expression of the same intent, so it replaces it.
        state.query = '';
        el('q').value = '';
        setView('map');
      });
      h.appendChild(toMap);
    }
    for (const mi of malls.slice(0, 60)) {
      const p = document.createElement('span');
      p.className = 'pill';
      p.textContent = d.malls[mi][0];
      pills.appendChild(p);
    }
    if (malls.length > 60) {
      const p = document.createElement('span');
      p.className = 'pill muted';
      p.textContent = `and ${malls.length - 60} more`;
      pills.appendChild(p);
    }
  }
  box.appendChild(h);
  box.appendChild(pills);
  return box;
}

function renderList() {
  const viewport = el('viewport');
  const sizer = el('sizer');
  const win = el('window');
  const rows = state.rows;

  if (rows.length === 0) {
    sizer.style.height = '0px';
    win.replaceChildren();
    el('empty').hidden = false;
    return;
  }
  el('empty').hidden = true;

  const d = state.data;
  const total = scopedMalls().length;

  sizer.style.height = rows.length * ROW_HEIGHT + 'px';
  const first = Math.max(0, Math.floor(viewport.scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visible = Math.ceil(viewport.clientHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const last = Math.min(rows.length, first + visible);

  const frag = document.createDocumentFragment();
  for (let i = first; i < last; i++) {
    frag.appendChild(buildRow(rows[i], total));
    if (state.expanded === rows[i]) frag.appendChild(buildDetail(rows[i]));
  }
  win.style.transform = `translateY(${first * ROW_HEIGHT}px)`;
  win.replaceChildren(frag);
}

/* ---------- map ----------
 * The map is the property result set drawn geographically. It shares every
 * filter, the search box and the brand focus with the list, so the two views
 * can never disagree about what is in scope. The only thing it adds is that a
 * property without a resolvable coordinate cannot be drawn, which is stated
 * under the map rather than hidden.
 */

function mapPoints() {
  const d = state.data;
  const out = [];
  for (const mi of state.rows) {
    const m = d.malls[mi];
    if (m[5] === null || m[6] === null) continue;
    out.push({
      index: mi,
      name: m[0],
      lat: m[5],
      lon: m[6],
      listings: m[4],
      approximate: d.dict.geoPrecisions[m[8]] === 'locality',
    });
  }
  return out;
}

/** Popup for one property, built as DOM so no data ever becomes markup. */
function buildPopup(point) {
  const d = state.data;
  const m = d.malls[point.index];
  const box = document.createElement('div');
  box.className = 'popup';

  const title = document.createElement('strong');
  title.textContent = point.name;

  const meta = document.createElement('p');
  meta.className = 'popup-meta';
  meta.textContent = [
    label(d.dict.chains[m[1]]),
    m[2] >= 0 ? label(d.dict.regions[m[2]]) : 'region unavailable',
    `${fmt(m[4])} listings`,
  ].join(' · ');
  box.append(title, meta);

  const brands = d.mallBrands[point.index]
    .slice()
    .sort((a, b) => d.brands[b][2] - d.brands[a][2]);
  if (brands.length) {
    const pills = document.createElement('div');
    pills.className = 'pills';
    for (const bi of brands.slice(0, POPUP_BRANDS)) {
      const pill = document.createElement('span');
      pill.className = 'pill';
      pill.textContent = d.brands[bi][0];
      pills.appendChild(pill);
    }
    if (brands.length > POPUP_BRANDS) {
      const rest = document.createElement('span');
      rest.className = 'pill muted';
      rest.textContent = `and ${fmt(brands.length - POPUP_BRANDS)} more`;
      pills.appendChild(rest);
    }
    box.appendChild(pills);
  }

  const flags = d.quality?.propertyFlags[point.index] || [];
  if (point.approximate) flags.push('approximate location, resolved to the town only');
  if (flags.length) {
    const note = document.createElement('p');
    note.className = 'popup-flag';
    note.textContent = flags.join(' · ');
    box.appendChild(note);
  }
  return box;
}

/** Everything under the map: what the marks mean, and what is missing. */
function renderMapNote(shown) {
  const note = el('mapnote');
  note.replaceChildren();

  const legend = document.createElement('span');
  legend.className = 'legend';
  for (const [cls, text] of [['dot', 'located'], ['dot dot--approx', 'approximate']]) {
    const swatch = document.createElement('i');
    swatch.className = cls;
    const caption = document.createElement('span');
    caption.textContent = text;
    legend.append(swatch, caption);
  }

  const missing = state.rows.length - shown;
  const parts = ['Circle area shows listing count.'];
  if (missing > 0) {
    parts.push(
      `${fmt(missing)} of ${fmt(state.rows.length)} matching ${missing === 1 ? 'property has' : 'properties have'} no resolvable location and ${missing === 1 ? 'is' : 'are'} not drawn.`,
    );
  }
  const text = document.createElement('span');
  text.textContent = parts.join(' ');

  const credit = document.createElement('span');
  credit.className = 'credit';
  credit.append(document.createTextNode('Tiles '));
  const link = document.createElement('a');
  link.href = 'https://www.openstreetmap.org/copyright';
  link.rel = 'noopener noreferrer';
  link.target = '_blank';
  link.textContent = document.body.dataset.tileAttribution || 'OpenStreetMap contributors';
  credit.appendChild(link);

  note.append(legend, text, credit);
}

function tileFailureNotice() {
  const banner = document.createElement('span');
  banner.className = 'popup-flag';
  banner.textContent =
    'Map tiles could not be loaded, so the background is blank. The markers below are still positioned correctly.';
  el('mapnote').prepend(banner);
}

/** The plotted properties, listed beside the map on wide screens.
 *
 * The country is far taller than it is wide, so a full-width map has to zoom
 * out until half the canvas is sea and neighbouring countries. This column
 * uses that width for something, and gives a way to reach a specific property
 * by name instead of by hunting for its pin.
 */
function renderMapList(points) {
  const host = el('maplist');
  const frag = document.createDocumentFragment();
  const heading = document.createElement('h3');
  heading.textContent = 'Most listings';
  frag.appendChild(heading);

  for (const point of [...points].sort((a, b) => b.listings - a.listings)) {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'maplist-item';
    const name = document.createElement('span');
    name.className = 'name';
    name.textContent = point.name;
    const n = document.createElement('span');
    n.className = 'n';
    n.textContent = fmt(point.listings);
    item.append(name, n);
    item.addEventListener('click', () => mapview.focusOn(point));
    frag.appendChild(item);
  }
  host.replaceChildren(frag);
  host.scrollTop = 0;
}

async function syncMap() {
  const points = mapPoints();
  el('mapcount').textContent = `${fmt(points.length)} on the map`;
  renderMapNote(points.length);
  renderMapList(points);
  mapview.setPopupBuilder(buildPopup);
  try {
    await mapview.ensure({
      container: el('map'),
      tiles: document.body.dataset.tiles,
      onTileFailure: tileFailureNotice,
    });
  } catch (err) {
    el('mapnote').replaceChildren();
    tileFailureNotice();
    el('mapnote').firstChild.textContent = `The map could not start: ${err.message}`;
    return;
  }
  mapview.refresh();                     // the panel was hidden when it was built
  mapview.update(points, { fit: true });
}

function refresh() {
  state.expanded = null;
  const isMap = state.view === 'map';
  state.rows = state.view === 'brands' ? matchingBrands() : matchingMalls();
  el('listPanel').hidden = isMap;
  el('mapPanel').hidden = !isMap;
  el('count').textContent =
    `${fmt(state.rows.length)} ${state.view === 'brands' ? 'brands' : 'properties'}`;
  paintFocusChip();
  renderStats();
  renderHits();
  if (isMap) {
    paintFacets();
    void syncMap();
    renderScope();
    return;
  }
  el('viewport').scrollTop = 0;
  el('col-2').textContent = state.view === 'brands' ? 'Category' : 'Operator';
  const scope = scopedMalls().length;
  // The two right-hand columns mean different things per view, so their
  // labels and their explanations both have to follow the view. Leaving the
  // brand wording in place while showing property numbers was worse than
  // having no explanation at all.
  const brands = state.view === 'brands';
  // The header carries the denominator, which is what made the old Share
  // column unreadable: a percentage with nothing to divide by.
  el('col-3').firstChild.textContent = brands ? `Reach of ${fmt(scope)} malls` : 'Listings';
  setHelp('help-rank', brands
    ? `How many of the ${fmt(scope)} malls matching your filters carry this brand, and that as a percentage. One mall counts once however many outlets it has there.`
    : 'How many store listings this property publishes. A brand with outlets on two floors counts twice.');
  paintFacets();
  renderList();
  renderScope();
}

function renderScope() {
  const active = [];
  if (state.brandFocus !== null) {
    active.push(`Brand: ${state.data.brands[state.brandFocus][0]}`);
  }
  for (const [key, title] of [['chain', 'Operator'], ['region', 'Region'], ['category', 'Category']]) {
    if (state[key].size) active.push(`${title}: ${[...state[key]].map(label).join(' or ')}`);
  }
  if (state.mallsOnly) active.push('Malls only');
  el('scope').textContent = active.length ? `Filtered by ${active.join(' · ')}` : 'Showing the full snapshot';
}

/** The brand focus is the one filter set from a row rather than a control, so
 *  it needs its own visible, dismissible chip. A filter a reader cannot see is
 *  a filter they will blame on the data. */
/** Brands matching the query, offered as chips.
 *
 * The search box filters property names, so typing a brand in the map view
 * used to return nothing. These chips are the bridge: they name the brand,
 * say how many malls carry it, and set the focus when clicked. */
function renderHits() {
  const host = el('hits');
  const d = state.data;
  host.replaceChildren();
  if (!state.query || state.view === 'brands' || state.brandFocus !== null) {
    host.hidden = true;
    return;
  }
  const matches = [];
  for (let i = 0; i < d.brands.length && matches.length < 60; i++) {
    if (d.brandSearch[i].includes(state.query)) matches.push(i);
  }
  matches.sort((a, b) => d.brands[b][2] - d.brands[a][2]);
  const top = matches.slice(0, 4);
  if (!top.length) {
    host.hidden = true;
    return;
  }
  const lead = document.createElement('span');
  lead.className = 'hits-lead';
  lead.textContent = state.rows.length === 0
    ? `No property is named "${state.query}". Matching brands:`
    : 'Matching brands:';
  host.appendChild(lead);
  for (const bi of top) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip chip--hit';
    const placed = d.brandMalls[bi].length;
    chip.textContent = `${d.brands[bi][0]} · ${fmt(placed)} malls`;
    chip.addEventListener('click', () => {
      state.brandFocus = bi;
      state.query = '';
      el('q').value = '';
      setView('map');
    });
    host.appendChild(chip);
  }
  host.hidden = false;
}

function paintFocusChip() {
  const chip = el('focus');
  if (state.brandFocus === null) {
    chip.hidden = true;
    return;
  }
  const name = state.data.brands[state.brandFocus][0];
  chip.hidden = false;
  chip.textContent = `${name} ×`;
  chip.setAttribute('aria-label', `Stop showing only properties carrying ${name}`);
}

function setView(view) {
  // The brand focus filters properties, so it cannot survive a return to the
  // brand list. Dropping it here beats leaving an invisible filter applied.
  if (view === 'brands') state.brandFocus = null;
  state.view = view;
  for (const [id, name] of [['tab-map', 'map'], ['tab-brands', 'brands']]) {
    el(id).setAttribute('aria-selected', String(view === name));
  }
  refresh();
}

/* ---------- setup ---------- */

const FACETS = [
  ['chain', 'Operator', 'chains'],
  ['region', 'Region', 'regions'],
  ['category', 'Category', 'categories'],
];

/** A trigger button plus a checkbox panel, one per facet. */
function buildFacets() {
  for (const [key, title, dictName] of FACETS) {
    const host = el(`dd-${key}`);
    host.replaceChildren();

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.setAttribute('aria-expanded', 'false');
    trigger.setAttribute('aria-haspopup', 'true');
    const text = document.createElement('span');
    text.textContent = title;
    const badge = document.createElement('span');
    badge.className = 'badge';
    badge.hidden = true;
    const caret = document.createElement('span');
    caret.className = 'caret';
    caret.textContent = '\u25be';
    trigger.append(text, badge, caret);

    const panel = document.createElement('div');
    panel.className = 'dd-panel' + (key === 'category' ? ' dd-panel--cat' : '');
    panel.hidden = true;

    for (const value of state.data.dict[dictName]) {
      const opt = document.createElement('button');
      opt.type = 'button';
      opt.className = 'dd-opt';
      opt.setAttribute('role', 'checkbox');
      opt.setAttribute('aria-checked', 'false');
      opt.dataset.facet = key;
      opt.dataset.value = value;

      const box = document.createElement('span');
      box.className = 'box';
      box.textContent = '\u2713';
      const name = document.createElement('span');
      name.className = 'label';
      name.textContent = label(value);
      const n = document.createElement('span');
      n.className = 'n2';
      opt.append(box, name, n);

      opt.addEventListener('click', () => {
        const set = state[key];
        if (set.has(value)) set.delete(value);
        else set.add(value);
        refresh();
      });
      panel.appendChild(opt);
    }

    trigger.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = panel.hidden;
      closeAllPanels();
      panel.hidden = !open;
      trigger.setAttribute('aria-expanded', String(open));
    });
    panel.addEventListener('click', (e) => e.stopPropagation());

    host.append(trigger, panel);
  }

  // one document-level handler closes any open panel
  document.addEventListener('click', closeAllPanels);
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAllPanels();
  });
}

function setHelp(id, text) {
  const b = el(id);
  if (!b) return;
  b.title = text;
  b.setAttribute('aria-label', text);
  b.dataset.help = text;
}

function closeAllPanels() {
  for (const panel of document.querySelectorAll('.dd-panel')) {
    panel.hidden = true;
    panel.previousElementSibling.setAttribute('aria-expanded', 'false');
  }
  document.querySelectorAll('.help-popover').forEach((node) => node.remove());
}

/** Refresh every option's checked state, count and availability. */
function paintFacets() {
  for (const [key] of FACETS) {
    const counts = facetCounts(key);
    for (const opt of document.querySelectorAll(`.dd-opt[data-facet="${key}"]`)) {
      const value = opt.dataset.value;
      const n = counts.get(value) || 0;
      const on = state[key].has(value);
      opt.setAttribute('aria-checked', String(on));
      opt.disabled = n === 0 && !on;
      opt.querySelector('.n2').textContent = fmt(n);
    }
    const badge = el(`dd-${key}`).querySelector('.badge');
    badge.hidden = state[key].size === 0;
    badge.textContent = String(state[key].size);
  }
  const active =
    state.chain.size + state.region.size + state.category.size + (state.mallsOnly ? 1 : 0);
  el('reset').hidden = active === 0;
}

/** Three tiles, and they follow the filters.
 *
 * Five static totals sat above a filtered table and never moved, so filtering
 * to Visayas still reported 322 properties. Numbers that do not respond to the
 * controls above them teach a reader to distrust the ones that do. */
function renderStats() {
  const d = state.data;
  const malls = scopedMalls();
  const isAll = malls.length === d.malls.length;
  let listings = 0;
  const brandSet = new Set();
  for (const mi of malls) {
    listings += d.malls[mi][4];
    for (const bi of d.mallBrands[mi]) brandSet.add(bi);
  }
  const onlyMalls = malls.filter((mi) => d.dict.propertyTypes[d.malls[mi][3]] === 'mall').length;
  const tiles = [
    [fmt(malls.length), isAll ? 'properties' : 'properties matching',
     `Everything the operators publish a directory for, including condo retail podiums, amusement parks and office annexes. ${fmt(onlyMalls)} of these are malls, which is the fair basis for comparing operators.`],
    [fmt(listings), 'listings',
     'One row per store as published. A brand with outlets on two floors of the same mall counts twice.'],
    [fmt(brandSet.size), 'brands',
     'Distinct businesses after resolving spelling variants to one canonical name. Bank branches and ATMs stay separate.'],
  ];
  const box = el('stats');
  box.replaceChildren();
  for (const [value, name, explain] of tiles) {
    const card = document.createElement('div');
    card.className = 'stat';
    const b = document.createElement('b');
    b.textContent = value;
    const s = document.createElement('span');
    s.textContent = name;
    if (explain) {
      const help = document.createElement('button');
      help.type = 'button';
      help.className = 'help';
      help.textContent = '?';
      help.title = explain;
      help.dataset.help = explain;
      help.setAttribute('aria-label', `${name}: ${explain}`);
      s.appendChild(help);
    }
    card.append(b, s);
    box.appendChild(card);
  }
  wireHelp();
}

function wireHelp() {
  for (const help of document.querySelectorAll('.help')) {
    if (help.dataset.wired) continue;
    help.dataset.wired = 'true';
    help.addEventListener('click', (event) => {
      event.stopPropagation();
      const old = help.parentElement.querySelector('.help-popover');
      document.querySelectorAll('.help-popover').forEach((node) => node.remove());
      if (old) return;
      const popover = document.createElement('span');
      popover.className = 'help-popover';
      popover.setAttribute('role', 'status');
      popover.textContent = help.dataset.help || help.title || 'More information';
      help.parentElement.appendChild(popover);
    });
  }
}

function renderQuality() {
  el('qualityText').textContent =
    'Listings are source rows, not verified open businesses. Brands resolve spelling variants to one name using a curated list, so nothing merges by guesswork. Categories a brand carries anywhere are applied everywhere, because operators label the same store differently. Some operators publish incomplete or duplicated directories.';
}

function applyTheme(mode) {
  document.documentElement.dataset.theme = mode;
  try { localStorage.setItem('pme-theme', mode); } catch { /* private mode */ }
  el('theme').textContent = mode === 'dark' ? 'Light mode' : 'Dark mode';
}

function wire() {
  let timer = null;
  el('q').addEventListener('input', (e) => {
    const value = e.target.value.trim().toLowerCase();
    // Debounced so a fast typist triggers one filter pass, not one per key.
    clearTimeout(timer);
    timer = setTimeout(() => { state.query = value; refresh(); }, 120);
  });

  el('reset').addEventListener('click', () => {
    state.chain.clear(); state.region.clear(); state.category.clear();
    state.mallsOnly = false;
    state.brandFocus = null;
    el('mallsOnly').setAttribute('aria-pressed', 'false');
    el('q').value = '';
    state.query = '';
    refresh();
  });

  el('focus').addEventListener('click', () => {
    state.brandFocus = null;
    refresh();
  });

  el('mapfit').addEventListener('click', () => mapview.fitToPoints());

  el('mallsOnly').addEventListener('click', (e) => {
    state.mallsOnly = !state.mallsOnly;
    e.currentTarget.setAttribute('aria-pressed', String(state.mallsOnly));
    refresh();
  });

  for (const [id, view] of [['tab-map', 'map'], ['tab-brands', 'brands']]) {
    el(id).addEventListener('click', () => setView(view));
  }

  el('viewport').addEventListener('scroll', () => {
    // rAF-throttled so scrolling stays at one render per frame
    if (state.ticking) return;
    state.ticking = true;
    requestAnimationFrame(() => { state.ticking = false; renderList(); });
  }, { passive: true });

  window.addEventListener('resize', () => {
    if (state.view === 'map') mapview.refresh();
    else renderList();
  }, { passive: true });

  el('theme').addEventListener('click', () => {
    const now = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    applyTheme(now);
  });
}

async function main() {
  try {
    let stored = null;
    try { stored = localStorage.getItem('pme-theme'); } catch { /* ignore */ }
    if (stored) applyTheme(stored);

    state.data = prepare(await load());
    el('date').textContent = state.data.date;
    el('opcount').textContent = String(state.data.dict.chains.length);
    renderQuality();
    buildFacets();
    wire();
    refresh();          // renders the stats, which follow the filters
    wireHelp();
    el('app').hidden = false;
    el('loading').hidden = true;
  } catch (err) {
    // Fail loudly and visibly rather than showing an empty page.
    el('loading').hidden = true;
    const box = el('error');
    box.hidden = false;
    box.textContent = `Could not start: ${err.message}`;
    throw err;
  }
}

main();
