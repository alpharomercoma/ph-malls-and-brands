/* Map view.
 *
 * This module knows about points, pixels and tiles. It knows nothing about
 * brands, operators or filters: the caller hands it a plain array of points and
 * a function that builds a popup for one, which keeps the data model in app.js
 * and the geometry here.
 *
 * Three decisions worth knowing about:
 *
 * Lazy    Leaflet is 147 KB and most visits never open the map, so the library
 *         and its stylesheet are injected on first use rather than shipped in
 *         the critical path. A phone that only ever reads the list pays nothing.
 * Stable  Clustering projects each point at an explicit zoom, so groups depend
 *         on zoom alone. Panning cannot reshuffle them, which is what makes the
 *         map feel steady rather than alive.
 * Safe    Every label and popup is built from DOM nodes with textContent. The
 *         page's no-innerHTML rule does not stop at the edge of the map.
 */

const PH_CENTER = [12.6, 122.6];   // roughly the centroid of the archipelago
const PH_ZOOM = 6;
const MAX_ZOOM = 18;
const CLUSTER_CELL = 62;           // px; a cluster owns a square of this size
const R_MIN = 5;
const R_MAX = 17;
const FIT_PADDING = [20, 20];
const FOCUS_ZOOM = 16;             // close enough that one property stands alone

let L = null;
let loading = null;
let map = null;
let markerLayer = null;
let tileLayer = null;
let popupFor = null;
let points = [];
let maxListings = 1;
let tilesFailed = false;
let onTileError = null;
const markerByIndex = new Map();   // only individual points; clusters have no one index

/* ---------- lazy library load ---------- */

function injectStylesheet(href) {
  return new Promise((resolve, reject) => {
    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = href;
    link.onload = resolve;
    link.onerror = () => reject(new Error(`could not load ${href}`));
    document.head.appendChild(link);
  });
}

function injectScript(src) {
  return new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = src;
    script.onload = resolve;
    script.onerror = () => reject(new Error(`could not load ${src}`));
    document.head.appendChild(script);
  });
}

/** Load Leaflet once. Repeat calls share the first promise, including failure,
 *  so a broken deploy reports the same error every time instead of retrying
 *  a fetch that will not succeed. */
function loadLeaflet() {
  if (loading) return loading;
  loading = Promise.all([
    injectStylesheet('vendor/leaflet.css'),
    injectScript('vendor/leaflet.js'),
  ]).then(() => {
    if (!window.L) throw new Error('the map library loaded but did not initialise');
    L = window.L;
    return L;
  });
  return loading;
}

/* ---------- geometry ---------- */

/** Group points into fixed pixel cells at one zoom level.
 *  Projecting at an explicit zoom rather than the current view means the result
 *  is a pure function of (points, zoom): pan does not change it. */
function clusterAt(zoom) {
  const cells = new Map();
  for (const point of points) {
    const pixel = map.project([point.lat, point.lon], zoom);
    const key = `${Math.floor(pixel.x / CLUSTER_CELL)}:${Math.floor(pixel.y / CLUSTER_CELL)}`;
    const cell = cells.get(key);
    if (cell) cell.push(point);
    else cells.set(key, [point]);
  }
  return [...cells.values()];
}

/** Radius encoding listing count. Area, not radius, carries the value, so the
 *  radius grows with the square root. A circle twice as wide then really does
 *  mean four times as much. */
function radiusFor(listings) {
  const share = maxListings > 0 ? Math.sqrt(Math.max(listings, 0) / maxListings) : 0;
  return R_MIN + (R_MAX - R_MIN) * share;
}

function boundsOf(group) {
  return L.latLngBounds(group.map((p) => [p.lat, p.lon]));
}

/* ---------- drawing ---------- */

function clusterIcon(count) {
  const node = document.createElement('span');
  node.className = 'cluster-label';
  node.textContent = String(count);
  const size = count >= 100 ? 46 : count >= 25 ? 40 : 34;
  return L.divIcon({
    html: node,                    // an Element, so Leaflet appends rather than parses
    className: 'cluster',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function drawCluster(group) {
  const marker = L.marker(boundsOf(group).getCenter(), {
    icon: clusterIcon(group.length),
    keyboard: true,
    title: `${group.length} properties. Select to zoom in.`,
    alt: `${group.length} properties`,
  });
  marker.on('click', () => {
    // Zooming to the group's own bounds is what a reader expects, except when
    // the points sit on top of each other and the bounds are a single spot;
    // then step in far enough for the cell to split.
    const bounds = boundsOf(group);
    if (bounds.getNorthEast().equals(bounds.getSouthWest())) {
      map.setView(bounds.getCenter(), Math.min(map.getZoom() + 3, MAX_ZOOM));
    } else {
      map.fitBounds(bounds, { padding: FIT_PADDING, maxZoom: MAX_ZOOM });
    }
  });
  return marker;
}

function drawPoint(point) {
  const marker = L.circleMarker([point.lat, point.lon], {
    radius: radiusFor(point.listings),
    className: 'pin' + (point.approximate ? ' pin--approx' : ''),
    // Colour comes from the stylesheet so the two themes stay in one place;
    // Leaflet only needs to be told not to paint its own defaults over it.
    weight: 1.5,
    fillOpacity: 0.75,
  });
  marker.bindPopup(() => popupFor(point), { maxWidth: 280, closeButton: true });
  marker.on('add', () => {
    const element = marker.getElement();
    if (!element) return;
    element.setAttribute('tabindex', '0');
    element.setAttribute('role', 'button');
    element.setAttribute('aria-label', `${point.name}, ${point.listings} listings`);
    element.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        marker.openPopup();
      }
    });
  });
  return marker;
}

function draw() {
  if (!map) return;
  markerLayer.clearLayers();
  markerByIndex.clear();
  const zoom = map.getZoom();
  for (const group of clusterAt(zoom)) {
    if (group.length === 1) {
      const marker = drawPoint(group[0]);
      markerByIndex.set(group[0].index, marker);
      markerLayer.addLayer(marker);
    } else {
      markerLayer.addLayer(drawCluster(group));
    }
  }
}

/* ---------- public API ---------- */

export function isLoaded() {
  return map !== null;
}

/** Create the map on first use. Safe to call repeatedly. */
export async function ensure({ container, tiles, attribution, referrerPolicy, onTileFailure }) {
  onTileError = onTileFailure;
  if (map) return map;
  await loadLeaflet();
  if (map) return map;                          // a second caller won the race

  map = L.map(container, {
    center: PH_CENTER,
    zoom: PH_ZOOM,
    minZoom: 5,
    maxZoom: MAX_ZOOM,
    attributionControl: false,   // we render attribution ourselves, as DOM
    worldCopyJump: false,
    zoomControl: true,
    // Integer zoom is too coarse for this country. The archipelago spans 17
    // degrees of latitude, which overflows one whole-number zoom and leaves
    // the next one down showing mostly Vietnam. Quarter steps let the fit
    // land on the level that actually frames it.
    zoomSnap: 0.25,
    zoomDelta: 0.5,
  });
  // Keep the view over the archipelago. Without this a stray drag lands the
  // reader in the empty Pacific with no way back except the reset button.
  map.setMaxBounds(L.latLngBounds([1.0, 112.0], [24.0, 132.0]));

  // referrerPolicy is set on the tile images only. The document sends no
  // referrer at all, which leaves the tile host unable to attribute the
  // request; its usage policy requires either a Referer or an identifying
  // User-Agent, and a browser cannot supply the second. Leaflet applies this
  // before setting src, so it governs the request rather than arriving late.
  tileLayer = L.tileLayer(tiles, {
    maxZoom: MAX_ZOOM,
    attribution: '',
    crossOrigin: false,
    referrerPolicy: referrerPolicy || 'strict-origin-when-cross-origin',
  });
  tileLayer.on('tileerror', () => {
    if (tilesFailed) return;
    tilesFailed = true;
    if (onTileError) onTileError();
  });
  tileLayer.addTo(map);
  markerLayer = L.layerGroup().addTo(map);

  // Recluster on zoom only: pan cannot change the grouping, so redrawing on
  // move would be work with no visible effect.
  map.on('zoomend', draw);
  void attribution;   // rendered by the caller alongside the other map notes
  return map;
}

/** Replace the plotted set. `fit` re-frames the view, which is right when the
 *  filters changed and wrong when the reader is mid-exploration. */
export function update(nextPoints, { fit = false } = {}) {
  points = nextPoints;
  maxListings = points.reduce((max, p) => Math.max(max, p.listings), 1);
  if (!map) return;
  draw();
  if (fit) fitToPoints();
}

export function setPopupBuilder(builder) {
  popupFor = builder;
}

/** Zoom to one property and open its popup. Zooming in far enough guarantees
 *  it is no longer inside a cluster, so there is always a marker to open. */
export function focusOn(point) {
  if (!map) return;
  map.once('moveend', () => {
    // A zoom change redraws through zoomend, which runs before moveend, so the
    // marker map is current by the time this fires either way.
    const marker = markerByIndex.get(point.index);
    if (marker) marker.openPopup();
  });
  map.setView([point.lat, point.lon], FOCUS_ZOOM);
}

export function fitToPoints() {
  if (!map || points.length === 0) {
    if (map) map.setView(PH_CENTER, PH_ZOOM);
    return;
  }
  map.fitBounds(boundsOf(points), { padding: FIT_PADDING, maxZoom: 15 });
}

/** Leaflet measures its container on creation, so a map built while hidden has
 *  no size. Call this after the panel becomes visible. */
export function refresh() {
  if (map) map.invalidateSize();
}
