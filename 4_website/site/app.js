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
  chain: '',
  region: '',
  category: '',
  mallsOnly: false,
  expanded: null,
  rows: [],
};

const el = (id) => document.getElementById(id);
const fmt = (n) => n.toLocaleString('en-US');
// taxonomy keys are snake_case; show them as words
const label = (s) => s.replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());

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

/* ---------- filtering ---------- */

function chainIndex(name) {
  return state.data.dict.chains.indexOf(name);
}

function matchingBrands() {
  const d = state.data;
  const q = state.query;
  const chainBit = state.chain ? 1 << chainIndex(state.chain) : 0;
  const catIx = state.category ? d.dict.categories.indexOf(state.category) : -1;
  const regionIx = state.region ? d.dict.regions.indexOf(state.region) : -1;
  const out = [];

  for (let i = 0; i < d.brands.length; i++) {
    const b = d.brands[i];
    if (q && !d.brandSearch[i].includes(q)) continue;
    if (chainBit && !(b[3] & chainBit)) continue;
    if (catIx >= 0 && b[1] !== catIx) continue;
    if (regionIx >= 0 || state.mallsOnly) {
      // region and property type live on the mall, so check this brand's malls
      const malls = d.brandMalls[i];
      let ok = false;
      for (let k = 0; k < malls.length; k++) {
        const m = d.malls[malls[k]];
        if (regionIx >= 0 && m[2] !== regionIx) continue;
        if (state.mallsOnly && d.dict.propertyTypes[m[3]] !== 'mall') continue;
        ok = true;
        break;
      }
      if (!ok) continue;
    }
    out.push(i);
  }
  out.sort((a, b) => d.brands[b][2] - d.brands[a][2] || (d.brands[a][0] < d.brands[b][0] ? -1 : 1));
  return out;
}

function matchingMalls() {
  const d = state.data;
  const q = state.query;
  const chainIx = state.chain ? chainIndex(state.chain) : -1;
  const regionIx = state.region ? d.dict.regions.indexOf(state.region) : -1;
  const out = [];
  for (let i = 0; i < d.malls.length; i++) {
    const m = d.malls[i];
    if (q && !d.mallSearch[i].includes(q)) continue;
    if (chainIx >= 0 && m[1] !== chainIx) continue;
    if (regionIx >= 0 && m[2] !== regionIx) continue;
    if (state.mallsOnly && d.dict.propertyTypes[m[3]] !== 'mall') continue;
    out.push(i);
  }
  out.sort((a, b) => d.malls[b][4] - d.malls[a][4] || (d.malls[a][0] < d.malls[b][0] ? -1 : 1));
  return out;
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
  el('col-2').textContent = state.view === 'brands' ? 'Category' : 'Chain';
  el('col-3').textContent = state.view === 'brands' ? 'Malls' : 'Listings';
  renderList();
}

/* ---------- setup ---------- */

function fillSelect(select, values, allLabel) {
  const first = document.createElement('option');
  first.value = '';
  first.textContent = allLabel;
  select.appendChild(first);
  for (const v of values) {
    const opt = document.createElement('option');
    opt.value = v;
    opt.textContent = label(v);
    select.appendChild(opt);
  }
}

function renderStats() {
  const t = state.data.totals;
  const tiles = [
    [fmt(t.properties), 'properties'],
    [fmt(t.malls), 'malls'],
    [fmt(t.listings), 'listings'],
    [fmt(t.brands), 'brands'],
    [String(state.data.dict.chains.length), 'operators'],
  ];
  const box = el('stats');
  for (const [value, label] of tiles) {
    const card = document.createElement('div');
    card.className = 'stat';
    const b = document.createElement('b');
    b.textContent = value;
    const s = document.createElement('span');
    s.textContent = label;
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

  for (const [id, key] of [['chain', 'chain'], ['region', 'region'], ['category', 'category']]) {
    el(id).addEventListener('change', (e) => { state[key] = e.target.value; refresh(); });
  }

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
    fillSelect(el('chain'), state.data.dict.chains, 'All operators');
    fillSelect(el('region'), state.data.dict.regions, 'All regions');
    fillSelect(el('category'), state.data.dict.categories, 'All categories');
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
