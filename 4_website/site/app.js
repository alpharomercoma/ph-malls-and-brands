/* Philippine Mall Explorer
 *
 * Three constraints drive the design:
 *   Size    the bundle is columnar with integer indices, so it stays small
 *           enough for a phone. It is fetched once and kept in memory.
 *   Speed   11,660 brands never all reach the DOM. A fixed row height lets the
 *           list render only the visible window plus a small overscan, so
 *           scrolling cost is constant regardless of result count.
 *   Safety  every value from the data is written with textContent. No innerHTML
 *           and no template interpolation of data anywhere, so a store name can
 *           never become markup. The page also runs under a strict CSP with no
 *           inline script.
 */

const ROW_HEIGHT = 44;   // must match --row-h in styles.css
const OVERSCAN = 6;      // rows rendered beyond the viewport, to hide scroll seams

const state = {
  data: null,
  view: 'brands',
  query: '',
  chain: new Set(),
  region: new Set(),
  category: new Set(),
  mallsOnly: false,
  expanded: null,
  rows: [],
};

const el = (id) => document.getElementById(id);
const fmt = (n) => n.toLocaleString('en-US');
// dictionary keys are slugs (metro-manila, health_beauty); show them as words
const SPECIAL = { smdc: 'SMDC', sm: 'SM', gmall: 'GMall', xentro: 'XentroMalls' };
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
  if (!data || data.schema !== 1) {
    throw new Error(`unsupported bundle schema: ${data && data.schema}`);
  }
  return data;
}

/* ---------- derived indexes, built once ---------- */

function prepare(data) {
  // Lowercased names for search. Doing this once turns every keystroke into a
  // plain substring scan over a flat array, which stays well under a frame.
  data.brandSearch = data.brands.map((b) => b[0].toLowerCase());
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
    const name = b[1] >= 0 ? d.dict.categories[b[1]] : null;
    if (!name || !state.category.has(name)) return false;
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
  out.sort((a, b) => d.brands[b][2] - d.brands[a][2] || (d.brands[a][0] < d.brands[b][0] ? -1 : 1));
  return out;
}

function matchingMalls() {
  const d = state.data;
  const out = [];
  for (let i = 0; i < d.malls.length; i++) {
    const m = d.malls[i];
    if (state.query && !d.mallSearch[i].includes(state.query)) continue;
    if (state.chain.size && !state.chain.has(d.dict.chains[m[1]])) continue;
    if (!mallPasses(i)) continue;
    if (state.category.size) {
      const brands = d.mallBrands[i];
      let ok = false;
      for (let k = 0; k < brands.length; k++) {
        const c = d.brands[brands[k]][1];
        if (c >= 0 && state.category.has(d.dict.categories[c])) { ok = true; break; }
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
  if (state.view === 'malls') {
    for (let i = 0; i < d.malls.length; i++) {
      const m = d.malls[i];
      if (state.query && !d.mallSearch[i].includes(state.query)) continue;
      if (facet !== 'chain' && state.chain.size && !state.chain.has(d.dict.chains[m[1]])) continue;
      if (!mallPasses(i, { skipRegion: facet === 'region' })) continue;
      const key = facet === 'chain' ? d.dict.chains[m[1]]
                : facet === 'region' ? (m[2] >= 0 ? d.dict.regions[m[2]] : null)
                : null;
      if (facet === 'category') {
        for (const bi of d.mallBrands[i]) {
          const c = d.brands[bi][1];
          if (c >= 0) counts.set(d.dict.categories[c], (counts.get(d.dict.categories[c]) || 0) + 1);
        }
      } else if (key) counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  }
  for (let i = 0; i < d.brands.length; i++) {
    const opts = { skipChain: facet === 'chain', skipCategory: facet === 'category', skipRegion: facet === 'region' };
    if (!brandPasses(i, opts)) continue;
    if (facet === 'category') {
      const c = d.brands[i][1];
      if (c >= 0) {
        const name = d.dict.categories[c];
        counts.set(name, (counts.get(name) || 0) + 1);
      }
      continue;
    }
    const seen = new Set();
    for (const mi of d.brandMalls[i]) {
      const m = d.malls[mi];
      if (!mallPasses(mi, { skipRegion: facet === 'region' })) continue;
      if (facet === 'chain' && state.region.size && m[2] >= 0 && !state.region.has(d.dict.regions[m[2]])) continue;
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

function barCell(value, max) {
  const wrap = document.createElement('div');
  wrap.className = 'bar-cell hide-sm';
  const track = document.createElement('div');
  track.className = 'bar-track';
  const bar = document.createElement('div');
  bar.className = 'bar';
  const pct = max > 0 ? Math.max(2, Math.round((value / max) * 100)) : 2;
  bar.style.width = pct + '%';
  track.appendChild(bar);
  wrap.appendChild(track);
  return wrap;
}

function buildRow(index, max) {
  const d = state.data;
  const row = document.createElement('button');
  row.className = 'row';
  row.type = 'button';
  row.setAttribute('aria-expanded', String(state.expanded === index));

  if (state.view === 'brands') {
    const b = d.brands[index];
    row.appendChild(cell('name', b[0]));
    row.appendChild(cell('muted hide-sm', b[1] >= 0 ? label(d.dict.categories[b[1]]) : 'unlabelled'));
    row.appendChild(cell('n', fmt(b[2])));
    row.appendChild(barCell(b[2], max));
    row.setAttribute('aria-label', `${b[0]}, in ${b[2]} malls`);
  } else {
    const m = d.malls[index];
    row.appendChild(cell('name', m[0]));
    row.appendChild(cell('muted hide-sm', d.dict.chains[m[1]]));
    row.appendChild(cell('n', fmt(m[4])));
    row.appendChild(barCell(m[4], max));
    row.setAttribute('aria-label', `${m[0]}, ${m[4]} listings`);
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

  if (state.view === 'brands') {
    const malls = d.brandMalls[index].slice().sort((a, b) => d.malls[b][4] - d.malls[a][4]);
    h.textContent = `Present in ${malls.length} ${malls.length === 1 ? 'mall' : 'malls'}`;
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
  } else {
    const brands = d.mallBrands[index].slice().sort((a, b) => d.brands[b][2] - d.brands[a][2]);
    h.textContent = `Top brands of ${brands.length}`;
    for (const bi of brands.slice(0, 60)) {
      const p = document.createElement('span');
      p.className = 'pill';
      p.textContent = d.brands[bi][0];
      pills.appendChild(p);
    }
    if (brands.length > 60) {
      const p = document.createElement('span');
      p.className = 'pill muted';
      p.textContent = `and ${brands.length - 60} more`;
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

  el('count').textContent =
    `${fmt(rows.length)} ${state.view === 'brands' ? 'brands' : 'properties'}`;

  if (rows.length === 0) {
    sizer.style.height = '0px';
    win.replaceChildren();
    el('empty').hidden = false;
    return;
  }
  el('empty').hidden = true;

  const d = state.data;
  const max = state.view === 'brands'
    ? d.brands[rows[0]][2]
    : d.malls[rows[0]][4];

  sizer.style.height = rows.length * ROW_HEIGHT + 'px';
  const first = Math.max(0, Math.floor(viewport.scrollTop / ROW_HEIGHT) - OVERSCAN);
  const visible = Math.ceil(viewport.clientHeight / ROW_HEIGHT) + OVERSCAN * 2;
  const last = Math.min(rows.length, first + visible);

  const frag = document.createDocumentFragment();
  for (let i = first; i < last; i++) {
    frag.appendChild(buildRow(rows[i], max));
    if (state.expanded === rows[i]) frag.appendChild(buildDetail(rows[i]));
  }
  win.style.transform = `translateY(${first * ROW_HEIGHT}px)`;
  win.replaceChildren(frag);
}

function refresh() {
  state.expanded = null;
  state.rows = state.view === 'brands' ? matchingBrands() : matchingMalls();
  el('viewport').scrollTop = 0;
  el('col-2').textContent = state.view === 'brands' ? 'Category' : 'Operator';
  el('col-3').firstChild.textContent = state.view === 'brands' ? 'Malls' : 'Listings';
  paintFacets();
  renderList();
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

function closeAllPanels() {
  for (const panel of document.querySelectorAll('.dd-panel')) {
    panel.hidden = true;
    panel.previousElementSibling.setAttribute('aria-expanded', 'false');
  }
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

function renderStats() {
  const t = state.data.totals;
  // Each number gets one sentence saying how it was derived. These are the
  // four places where a reader would otherwise have to guess.
  const tiles = [
    [fmt(t.properties), 'properties',
     'Everything the operators publish a directory for, including condo retail podiums, amusement parks and office annexes.'],
    [fmt(t.malls), 'malls',
     'Properties that are actually malls. This is the fair basis for comparing one operator against another.'],
    [fmt(t.listings), 'listings',
     'One row per store as published. A brand with outlets on two floors of the same mall counts twice.'],
    [fmt(t.brands), 'brands',
     'Distinct brands after normalizing names, so BPI, BPI (ATM) and BPI - ATM count as one.'],
    [String(state.data.dict.chains.length), 'operators', null],
  ];
  const box = el('stats');
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
      help.setAttribute('aria-label', `${name}: ${explain}`);
      s.appendChild(help);
    }
    card.append(b, s);
    box.appendChild(card);
  }
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
    el('mallsOnly').setAttribute('aria-pressed', 'false');
    el('q').value = '';
    state.query = '';
    refresh();
  });

  el('mallsOnly').addEventListener('click', (e) => {
    state.mallsOnly = !state.mallsOnly;
    e.currentTarget.setAttribute('aria-pressed', String(state.mallsOnly));
    refresh();
  });

  for (const id of ['tab-brands', 'tab-malls']) {
    el(id).addEventListener('click', () => {
      state.view = id === 'tab-brands' ? 'brands' : 'malls';
      el('tab-brands').setAttribute('aria-selected', String(state.view === 'brands'));
      el('tab-malls').setAttribute('aria-selected', String(state.view === 'malls'));
      refresh();
    });
  }

  el('viewport').addEventListener('scroll', () => {
    // rAF-throttled so scrolling stays at one render per frame
    if (state.ticking) return;
    state.ticking = true;
    requestAnimationFrame(() => { state.ticking = false; renderList(); });
  }, { passive: true });

  window.addEventListener('resize', renderList, { passive: true });

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
    renderStats();
    buildFacets();
    wire();
    refresh();
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
