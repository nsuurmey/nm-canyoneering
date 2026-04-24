// ===== Theme toggle =====
(function () {
  const t = document.querySelector('[data-theme-toggle]');
  const r = document.documentElement;
  let d = matchMedia('(prefers-color-scheme:dark)').matches ? 'dark' : 'light';
  r.setAttribute('data-theme', d);
  updateIcon();

  t && t.addEventListener('click', () => {
    d = d === 'dark' ? 'light' : 'dark';
    r.setAttribute('data-theme', d);
    updateIcon();
  });

  function updateIcon() {
    if (!t) return;
    t.innerHTML = d === 'dark'
      ? '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>'
      : '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>';
  }
})();

// ===== View toggle =====
document.querySelectorAll('.view-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const view = btn.dataset.view;
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    document.getElementById(view + 'View').classList.add('active');
    if (view === 'map' && map) map.resize();
  });
});

// ===== Class color helpers =====
const CLASS_COLORS = { '1': '#3b82f6', '2': '#f59e0b', '3': '#ef4444', 'other': '#8b5cf6' };

function getClassNum(cls) {
  const m = cls.match(/^(\d)/);
  return m ? m[1] : 'other';
}

function getColor(cls) {
  return CLASS_COLORS[getClassNum(cls)] || CLASS_COLORS['other'];
}

// ===== Data =====
let canyons = [];
let map = null;
let sortKey = 'quality';
let sortDir = 'desc';

async function init() {
  const res = await fetch('canyons_data.json');
  canyons = await res.json();

  // Legend counts
  const counts = { '1': 0, '2': 0, '3': 0, 'other': 0 };
  canyons.forEach(c => { counts[getClassNum(c.class)]++; });
  Object.keys(counts).forEach(k => {
    const el = document.getElementById('count-' + k);
    if (el) el.textContent = '(' + counts[k] + ')';
  });

  initMap();
  populateClassFilter();
  attachTableListeners();
  renderTable();
}

// ===== MAP =====
function initMap() {
  map = new maplibregl.Map({
    container: 'mapContainer',
    style: 'https://tiles.openfreemap.org/styles/liberty',
    center: [-106.6, 34.5],
    zoom: 6.2,
    attributionControl: true,
  });

  map.addControl(new maplibregl.NavigationControl(), 'top-left');

  map.on('load', () => {
    // Build GeoJSON
    const features = canyons
      .filter(c => c.lat !== null && c.lon !== null)
      .map(c => ({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
        properties: {
          name: c.name,
          url: c.url,
          class: c.class,
          classNum: getClassNum(c.class),
          color: getColor(c.class),
          quality: c.quality,
          distance_mi: c.distance_mi,
          rappels: c.rappels,
          longest_rappel_ft: c.longest_rappel_ft,
          season: c.season,
          notes: c.notes,
        }
      }));

    map.addSource('canyons', {
      type: 'geojson',
      data: { type: 'FeatureCollection', features },
    });

    // Circle layer
    map.addLayer({
      id: 'canyon-dots',
      type: 'circle',
      source: 'canyons',
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          5, 5,
          8, 8,
          12, 12,
        ],
        'circle-color': ['get', 'color'],
        'circle-stroke-color': '#ffffff',
        'circle-stroke-width': [
          'interpolate', ['linear'], ['zoom'],
          5, 1.5,
          10, 2,
        ],
        'circle-opacity': 0.9,
      },
    });

    // Hover effect
    map.on('mouseenter', 'canyon-dots', () => {
      map.getCanvas().style.cursor = 'pointer';
    });
    map.on('mouseleave', 'canyon-dots', () => {
      map.getCanvas().style.cursor = '';
    });

    // Tooltip on hover
    const tooltip = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
    });

    map.on('mousemove', 'canyon-dots', (e) => {
      const f = e.features[0];
      const classNum = f.properties.classNum;
      tooltip
        .setLngLat(f.geometry.coordinates)
        .setHTML(`<strong>${f.properties.name}</strong><br>Class ${classNum} &middot; ${f.properties.class}`)
        .addTo(map);
    });
    map.on('mouseleave', 'canyon-dots', () => {
      tooltip.remove();
    });

    // Click to show details
    map.on('click', 'canyon-dots', (e) => {
      const f = e.features[0];
      const p = f.properties;
      showInfoPanel(p);
      // Fly to
      map.flyTo({ center: f.geometry.coordinates, zoom: Math.max(map.getZoom(), 9), speed: 0.8 });
    });

    // ABQ marker
    const abqEl = document.createElement('div');
    abqEl.className = 'abq-marker';
    abqEl.innerHTML = '<svg width="20" height="20" viewBox="0 0 24 24" fill="#a0522d" stroke="#fff" stroke-width="1.5"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>';
    new maplibregl.Marker({ element: abqEl })
      .setLngLat([-106.6504, 35.0844])
      .setPopup(new maplibregl.Popup({ offset: 12 }).setHTML('<strong>Albuquerque</strong>'))
      .addTo(map);

    // Legend filter
    document.querySelectorAll('[data-class-filter]').forEach(cb => {
      cb.addEventListener('change', applyMapFilter);
    });
  });
}

function applyMapFilter() {
  const visible = {};
  document.querySelectorAll('[data-class-filter]').forEach(cb => {
    visible[cb.dataset.classFilter] = cb.checked;
  });

  map.setFilter('canyon-dots', [
    'match',
    ['get', 'classNum'],
    ...Object.entries(visible).flatMap(([k, v]) => v ? [k, true] : []).length === 0
      ? ['__none__', true]  // nothing selected
      : (() => {
          const allowed = Object.entries(visible).filter(([, v]) => v).map(([k]) => k);
          return [allowed, true, false];
        })(),
  ]);
}

function showInfoPanel(p) {
  const panel = document.getElementById('mapInfoPanel');
  const quality = parseFloat(p.quality);
  let stars = '';
  if (quality > 0) {
    const full = Math.floor(quality);
    const half = quality % 1 >= 0.3;
    for (let i = 0; i < full; i++) stars += '★';
    if (half) stars += '½';
  } else {
    stars = 'Not rated';
  }

  panel.innerHTML = `
    <div class="info-name"><a href="${p.url}" target="_blank" rel="noopener">${p.name}</a></div>
    <div class="info-grid">
      <span class="info-label">Class</span>
      <span class="info-value">${p.class}</span>
      <span class="info-label">Quality</span>
      <span class="info-value" style="color: var(--color-warning);">${stars}</span>
      <span class="info-label">Distance</span>
      <span class="info-value">${p.distance_mi != null ? p.distance_mi + ' mi from ABQ' : '—'}</span>
      <span class="info-label">Rappels</span>
      <span class="info-value">${p.rappels}</span>
      <span class="info-label">Longest</span>
      <span class="info-value">${p.longest_rappel_ft === '—' ? '—' : p.longest_rappel_ft + ' ft'}</span>
      <span class="info-label">Season</span>
      <span class="info-value">${p.season}</span>
      <span class="info-label">Notes</span>
      <span class="info-value">${p.notes}</span>
    </div>
  `;
}

// ===== TABLE =====
function populateClassFilter() {
  const select = document.getElementById('classFilter');
  const classNums = new Set();
  canyons.forEach(c => {
    const m = c.class.match(/^(\d)/);
    if (m) classNums.add(m[1]);
  });
  [...classNums].sort().forEach(cls => {
    const opt = document.createElement('option');
    opt.value = cls;
    opt.textContent = 'Class ' + cls;
    select.appendChild(opt);
  });
}

function attachTableListeners() {
  document.getElementById('searchInput').addEventListener('input', renderTable);
  document.getElementById('classFilter').addEventListener('change', renderTable);
  document.getElementById('distanceFilter').addEventListener('change', renderTable);
  document.getElementById('rappelFilter').addEventListener('change', renderTable);
  document.getElementById('qualityFilter').addEventListener('change', renderTable);

  document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
      const key = th.dataset.sort;
      if (sortKey === key) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }
      else { sortKey = key; sortDir = key === 'name' ? 'asc' : 'desc'; }
      document.querySelectorAll('th.sortable').forEach(h => h.classList.remove('sort-asc', 'sort-desc'));
      th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
      renderTable();
    });
  });
}

function getFiltered() {
  const search = document.getElementById('searchInput').value.toLowerCase().trim();
  const cf = document.getElementById('classFilter').value;
  const df = document.getElementById('distanceFilter').value;
  const rf = document.getElementById('rappelFilter').value;
  const qf = document.getElementById('qualityFilter').value;

  return canyons.filter(c => {
    if (search && !c.name.toLowerCase().includes(search)) return false;
    if (cf && !c.class.startsWith(cf)) return false;
    if (df && (c.distance_mi === null || c.distance_mi > parseInt(df))) return false;
    if (rf === 'yes' && c.rappels === '—') return false;
    if (rf === 'no' && c.rappels !== '—') return false;
    if (qf && c.quality < parseFloat(qf)) return false;
    return true;
  });
}

function parseRappelNum(str) {
  if (str === '—') return 0;
  const nums = str.match(/\d+/g);
  return nums ? Math.max(...nums.map(Number)) : 0;
}

function parseLongestNum(str) {
  if (str === '—') return 0;
  const num = parseInt(str);
  return isNaN(num) ? 0 : num;
}

function getSorted(data) {
  const sorted = [...data];
  sorted.sort((a, b) => {
    let va, vb;
    switch (sortKey) {
      case 'name':
        return sortDir === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
      case 'class':
        return sortDir === 'asc' ? a.class.localeCompare(b.class) : b.class.localeCompare(a.class);
      case 'quality': va = a.quality; vb = b.quality; break;
      case 'distance': va = a.distance_mi ?? 9999; vb = b.distance_mi ?? 9999; break;
      case 'rappels': va = parseRappelNum(a.rappels); vb = parseRappelNum(b.rappels); break;
      case 'longest': va = parseLongestNum(a.longest_rappel_ft); vb = parseLongestNum(b.longest_rappel_ft); break;
      default: return 0;
    }
    return sortDir === 'asc' ? va - vb : vb - va;
  });
  return sorted;
}

function renderStars(quality) {
  if (quality === 0) return '<span class="quality-none">Not rated</span>';
  const full = Math.floor(quality);
  const half = quality % 1 >= 0.3;
  let html = '<span class="quality-stars">';
  for (let i = 0; i < full; i++) html += '★';
  if (half) html += '½';
  html += '</span>';
  return html;
}

function renderTable() {
  const filtered = getFiltered();
  const sorted = getSorted(filtered);
  const tbody = document.getElementById('canyonBody');
  document.getElementById('resultsCount').textContent = `Showing ${sorted.length} of ${canyons.length} canyons`;

  if (sorted.length === 0) {
    tbody.innerHTML = '<tr class="no-results"><td colspan="8">No canyons match your filters</td></tr>';
    return;
  }

  tbody.innerHTML = sorted.map(c => {
    const isTech = c.class.startsWith('3');
    const longestNum = parseLongestNum(c.longest_rappel_ft);
    const longestClass = longestNum >= 100 ? 'longest-cell highlight' : 'longest-cell';
    const distText = c.distance_mi !== null ? `${c.distance_mi} mi` : '—';
    const longestText = c.longest_rappel_ft === '—' ? '—' : `${c.longest_rappel_ft} ft`;

    return `<tr>
      <td><a class="canyon-name" href="${c.url}" target="_blank" rel="noopener">${c.name}</a></td>
      <td><span class="class-badge${isTech ? ' technical' : ''}">${c.class}</span></td>
      <td>${renderStars(c.quality)}</td>
      <td class="distance-cell">${distText}</td>
      <td class="rappel-cell">${c.rappels}</td>
      <td class="${longestClass}">${longestText}</td>
      <td class="season-cell">${c.season}</td>
      <td class="notes-cell">${c.notes}</td>
    </tr>`;
  }).join('');
}

init();
