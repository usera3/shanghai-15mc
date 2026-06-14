const state = {
  mode: "walk",
  layer: "composite",
  geojson: null,
  manifest: null,
  topPicks: [],
  bounds: null,
  projected: [],
  map: null,
  redrawFrame: null,
  mapEventsBound: false,
  featureIndexByH3: new Map(),
  stats: null,
  overlayOpacity: 0.72,
  hoveredIndex: null,
  selectedIndex: 0,
};

const mapContainer = document.getElementById("map");
const canvas = document.getElementById("hex-map");
const ctx = canvas.getContext("2d");

const palette = [
  [0, [241, 231, 207]],
  [25, [244, 196, 111]],
  [50, [233, 127, 68]],
  [75, [178, 66, 43]],
  [100, [94, 24, 17]],
];

const SCORE_FIELDS = [
  ...["walk", "bike", "transit", "car"].flatMap((mode) => [
    `score_baseline_${mode}`,
    `score_track_${mode}`,
    `score_composite_${mode}`,
  ]),
];

function setStatus(message) {
  const el = document.getElementById("status-line");
  if (el) el.textContent = message;
}

function setLoadingState(isLoading) {
  document.body.classList.toggle("is-loading", isLoading);
  const loader = document.getElementById("map-loader");
  if (loader) {
    loader.classList.toggle("is-hidden", !isLoading);
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function scoreProperty() {
  return `score_${state.layer}_${state.mode}`;
}

function updateActiveButtons(groupId, key, value) {
  document.querySelectorAll(`#${groupId} button`).forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset[key] === value);
  });
}

function scoreValue(properties, layer, mode) {
  return Number(properties[`score_${layer}_${mode}`] || 0);
}

function ordinalRank(n) {
  const value = Math.round(Number(n) || 0);
  const mod100 = value % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${value}th`;
  switch (value % 10) {
    case 1:
      return `${value}st`;
    case 2:
      return `${value}nd`;
    case 3:
      return `${value}rd`;
    default:
      return `${value}th`;
  }
}

function safePercentile(stats, field, value, { invert = false } = {}) {
  if (!stats?.[field] || !Number.isFinite(value)) return null;
  const list = stats[field];
  if (!list.length) return null;
  let lo = 0;
  let hi = list.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (list[mid] <= value) lo = mid + 1;
    else hi = mid;
  }
  let percentile = (lo / list.length) * 100;
  if (invert) percentile = 100 - percentile;
  return Math.max(0, Math.min(100, percentile));
}

function percentileSummary(properties) {
  const currentScore = Number(properties[scoreProperty()] || 0);
  const affordability = properties.has_housing_sample ? Number(properties.price_affordability_norm || 0) * 100 : null;
  const ndvi = Number(properties.ndvi_norm || 0) * 100;
  const aqi = Number(properties.aqi_norm || 0) * 100;

  const cards = [
    {
      label: `${state.layer} ${state.mode}`,
      percentile: safePercentile(state.stats, scoreProperty(), currentScore),
      note: "Citywide score standing",
    },
    {
      label: "Affordability",
      percentile: affordability === null ? null : safePercentile(state.stats, "price_affordability_norm", affordability),
      note: properties.has_housing_sample ? "Higher is more affordable" : "No housing sample",
    },
    {
      label: "Greenery",
      percentile: safePercentile(state.stats, "ndvi_norm", ndvi),
      note: "NDVI percentile",
    },
    {
      label: "Air quality",
      percentile: safePercentile(state.stats, "aqi_norm", aqi, { invert: true }),
      note: "Lower AQI ranks better",
    },
  ];

  return `
    <div class="detail-kpi-grid">
      ${cards
        .map((card) => {
          if (card.percentile === null) {
            return `
              <div class="detail-kpi">
                <strong>${escapeHtml(card.label)}</strong>
                <span>n/a</span>
                <small>${escapeHtml(card.note)}</small>
              </div>
            `;
          }
          return `
            <div class="detail-kpi">
              <strong>${escapeHtml(card.label)}</strong>
              <span>Top ${ordinalRank(Math.max(1, Math.round(100 - card.percentile + 1)))}</span>
              <small>${card.percentile.toFixed(0)}th percentile · ${escapeHtml(card.note)}</small>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function modeScoreTable(properties) {
  const rows = [
    ["Walk", "walk"],
    ["Bike", "bike"],
    ["Transit", "transit"],
    ["Car", "car"],
  ];
  const layers = [
    ["Baseline", "baseline"],
    ["Track A", "track"],
    ["Composite", "composite"],
  ];
  return `
    <div class="score-matrix">
      ${rows
        .map(
          ([label, mode]) => `
            <div class="score-row">
              <strong>${label}</strong>
              ${layers
                .map(([layerLabel, layer]) => {
                  const active = state.mode === mode && state.layer === layer ? "is-active" : "";
                  return `<div class="score-cell ${active}" title="${layerLabel} ${label}">${scoreValue(properties, layer, mode).toFixed(1)}</div>`;
                })
                .join("")}
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function accessBars(properties) {
  const rows = [
    ["Walk", Number(properties.proxy_access_walk || 0)],
    ["Bike", Number(properties.proxy_access_bike || 0)],
    ["Transit", Number(properties.proxy_access_transit || 0)],
    ["Car", Number(properties.proxy_access_car || 0)],
  ];
  return `
    <div class="access-bars">
      ${rows
        .map(
          ([label, value]) => `
            <div class="access-bar">
              <strong>${label}</strong>
              <div class="access-track">
                <div class="access-fill" style="width:${Math.max(0, Math.min(100, value))}%"></div>
              </div>
              <span>${value.toFixed(1)}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function amenityCards(properties) {
  const items = [
    ["Schools", properties.school_count],
    ["Healthcare", properties.healthcare_count],
    ["Groceries", properties.grocery_count],
    ["Parks", properties.park_count],
    ["Bus stops", properties.bus_stop_count],
    ["Subway exits", properties.subway_exit_count],
    ["Gyms", properties.gym_count],
    ["Bike km proxy", Number(properties.bike_length_km || 0).toFixed(2)],
  ];
  return `
    <div class="amenity-grid">
      ${items
        .map(
          ([label, value]) => `
            <div class="amenity-card">
              <strong>${escapeHtml(label)}</strong>
              <span>${escapeHtml(value)}</span>
            </div>
          `
        )
        .join("")}
    </div>
  `;
}

function renderDetail(properties) {
  const currentNetworkAccess = ["walk", "bike"].includes(state.mode)
    ? Number(properties[`network_access_${state.mode}`] || 0).toFixed(1)
    : "Proxy-only mode";
  const trackNetworkAccess = ["walk", "bike"].includes(state.mode)
    ? Number(properties[`network_track_access_${state.mode}`] || 0).toFixed(1)
    : "";
  const priceLine = properties.has_housing_sample
    ? `¥${Math.round(properties.avg_price_m2).toLocaleString()}/m²`
    : "No housing sample in this hex";
  const html = `
    <div class="detail-grid">
      <div class="detail-kpi-grid">
        <div class="detail-kpi">
          <strong>Current ${state.layer} ${state.mode}</strong>
          <span>${Number(properties[scoreProperty()]).toFixed(1)}</span>
        </div>
        <div class="detail-kpi">
          <strong>Current network support</strong>
          <span>${currentNetworkAccess}</span>
        </div>
        <div class="detail-kpi">
          <strong>Housing band</strong>
          <span>${escapeHtml(properties.housing_band)}</span>
        </div>
        <div class="detail-kpi">
          <strong>Subway distance</strong>
          <span>${Math.round(properties.avg_subway_distance_m).toLocaleString()} m</span>
        </div>
      </div>

      <div class="detail-section">
        <h3>Hex identity</h3>
        <p><strong>H3:</strong> <code>${properties.h3_index}</code></p>
        <p><strong>Top amenity mix:</strong> ${escapeHtml(properties.top_amenities)}</p>
        <p><strong>Average sale-price proxy:</strong> ${priceLine}</p>
        <p><strong>Track network support:</strong> ${trackNetworkAccess || "Proxy-only mode"}</p>
        <p>
          <span class="metric-pill">NDVI ${Number(properties.ndvi ?? 0).toFixed(3)}</span>
          <span class="metric-pill">AQI ${Number(properties.european_aqi ?? 0).toFixed(0)}</span>
        </p>
      </div>

      <div class="detail-section">
        <h3>Mode x score matrix</h3>
        <p class="microcopy">Compare baseline, Track A, and composite performance across all four transport modes.</p>
        ${modeScoreTable(properties)}
      </div>

      <div class="detail-section">
        <h3>Citywide standing</h3>
        <p class="microcopy">Percentile summaries help interpret whether this hex is relatively strong, average, or weak across the city.</p>
        ${percentileSummary(properties)}
      </div>

      <div class="detail-section">
        <h3>15-minute access profile</h3>
        <p class="microcopy">These values are the current per-mode proxy accessibility scores used before H3 ranking.</p>
        ${accessBars(properties)}
      </div>

      <div class="detail-section">
        <h3>Amenity and mobility counts</h3>
        ${amenityCards(properties)}
      </div>
    </div>
  `;
  document.getElementById("detail-content").innerHTML = html;
}

function topPicksHtml() {
  if (!state.topPicks.length) return "<p>No top picks computed yet.</p>";
  return `
    <p class="microcopy">Click a shortlist item to zoom to its hex on the map.</p>
    <ul class="recommendation-list">
      ${state.topPicks
        .map((feature, idx) => {
          const p = feature.properties;
          const isSelected = state.selectedIndex === state.featureIndexByH3.get(p.h3_index);
          return `
            <li>
              <button class="recommendation-card ${isSelected ? "is-selected" : ""}" type="button" data-h3="${escapeHtml(p.h3_index)}">
                <span class="recommendation-rank">${idx + 1}</span>
                <span>
                  <strong>${escapeHtml(p.housing_band)}</strong>
                  <small>${escapeHtml(p.top_amenities)} · score ${Number(p.reco_score).toFixed(1)}</small>
                </span>
              </button>
            </li>
          `;
        })
        .join("")}
    </ul>
  `;
}

function bindRecommendationButtons() {
  document.querySelectorAll(".recommendation-card").forEach((button) => {
    button.addEventListener("click", () => {
      const index = state.featureIndexByH3.get(button.dataset.h3);
      if (typeof index === "number") {
        selectFeature(index, { focus: true, popup: true });
      }
    });
  });
}

function updateActiveRecommendation() {
  document.querySelectorAll(".recommendation-card").forEach((button) => {
    const index = state.featureIndexByH3.get(button.dataset.h3);
    button.classList.toggle("is-selected", index === state.selectedIndex);
  });
}

function renderManifest() {
  const manifest = state.manifest;
  const sources = manifest.source_provenance || [];
  const methodSummary = manifest.method_summary || [];
  const scoreMethod = manifest.score_method || {};
  const external = manifest.external_platform_status || {};
  const speed = manifest.speed_assumptions_m_s || {};
  const trackStatus = Object.values(manifest.track_indicator_status || {});
  const implementedIndicators = trackStatus.filter((status) => String(status).startsWith("Implemented")).length;
  const partialIndicators = trackStatus.filter((status) => String(status).startsWith("Partially")).length;
  const platformLinks = [
    ["GitHub repository", external.github_repository],
    ["Public app", external.public_deployment_url],
    ["Trello board", external.trello_shared_board],
  ].filter(([, url]) => url);
  document.getElementById("manifest-content").innerHTML = `
    <div class="transparency-grid">
      <article class="manifest-card">
        <h4>Submission Snapshot</h4>
        <p><strong>Track:</strong> ${escapeHtml(manifest.track)}</p>
        <p><strong>Resolution:</strong> H3 r${manifest.h3_resolution}</p>
        <p><strong>Grid:</strong> ${manifest.grid_cell_size_m} m · ${manifest.grid_cell_count.toLocaleString()} cells</p>
        <p><strong>Hex count:</strong> ${manifest.feature_count.toLocaleString()}</p>
        <p><strong>Updated:</strong> ${escapeHtml(manifest.created_at_utc || "local prototype build")}</p>
      </article>
      <article class="manifest-card">
        <h4>Scoring Method</h4>
        <p>${escapeHtml(scoreMethod.baseline || "Baseline score combines everyday accessibility indicators.")}</p>
        <p>${escapeHtml(scoreMethod.track || "Track score focuses on Healthy Lifestyle & Sport indicators.")}</p>
        <p><strong>Composite:</strong> ${escapeHtml(scoreMethod.composite || "Composite score combines baseline and track scores.")}</p>
      </article>
      <article class="manifest-card">
        <h4>Mode Assumptions</h4>
        <p>Walk ${Number(speed.walk || 0).toFixed(2)} m/s · Bike ${Number(speed.bike || 0).toFixed(2)} m/s</p>
        <p>Transit ${Number(speed.transit || 0).toFixed(2)} m/s · Car ${Number(speed.car || 0).toFixed(2)} m/s</p>
        <p><strong>Track A coverage:</strong> ${implementedIndicators} implemented, ${partialIndicators} partial indicators.</p>
      </article>
      <article class="manifest-card">
        <h4>Platform Evidence</h4>
        <div class="external-links">
          ${platformLinks
            .map(([label, url]) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`)
            .join("")}
        </div>
        <p>Instructor invited to Trello: <strong>${external.trello_instructor_invited ? "yes" : "check manually"}</strong></p>
      </article>
    </div>
    <h4>Method Summary</h4>
    <ol class="compact-list">
      ${methodSummary.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ol>
    <h4>Source Provenance</h4>
    <ul class="compact-list">
      ${sources
        .map((item) => `<li><strong>${escapeHtml(item.type)}:</strong> ${escapeHtml(item.source)}. ${escapeHtml(item.role)}</li>`)
        .join("")}
    </ul>
    <h4>Honest Limitations</h4>
    <ul class="compact-list">
      ${manifest.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function renderSubmissionLinks() {
  const external = state.manifest?.external_platform_status || {};
  const links = [
    {
      label: "GitHub repository",
      href: external.github_repository,
      note: "Source code, notebooks, evidence, and deploy workflow",
      badge: "Repo",
    },
    {
      label: "Public app",
      href: external.public_deployment_url,
      note: "Interactive Leaflet + H3 delivery page",
      badge: "Live",
    },
    {
      label: "Trello board",
      href: external.trello_shared_board,
      note: "Weekly planning, screenshots, and external process evidence",
      badge: "Board",
    },
    {
      label: "Public manifest",
      href: external.public_deployment_url ? `${external.public_deployment_url.replace(/\/$/, "")}/data/project_manifest.json` : null,
      note: "Source provenance, scoring method, counts, and limitations",
      badge: "Data",
    },
  ].filter((item) => item.href);

  document.getElementById("submission-links-content").innerHTML = `
    <div class="submission-link-list">
      ${links
        .map(
          (item) => `
            <a class="submission-link" href="${escapeHtml(item.href)}" target="_blank" rel="noopener">
              <span>
                <strong>${escapeHtml(item.label)}</strong>
                <small>${escapeHtml(item.note)}</small>
              </span>
              <span class="submission-badge">${escapeHtml(item.badge)}</span>
            </a>
          `
        )
        .join("")}
    </div>
  `;
}

function computeRecommendation(feature) {
  const p = feature.properties;
  const wLifestyle = Number(document.getElementById("weight-lifestyle").value);
  const wAff = Number(document.getElementById("weight-affordability").value);
  const wTransit = Number(document.getElementById("weight-transit").value);
  const wParks = Number(document.getElementById("weight-parks").value);
  const affordability = p.has_housing_sample ? Number(p.price_affordability_norm) * 100 : 0;
  return (
    (Number(p[`score_composite_${state.mode}`]) * wLifestyle) +
    (affordability * wAff) +
    (Number(p.transit_norm) * 100 * wTransit) +
    (Number(p.park_norm) * 100 * wParks) +
    (Number(p.ndvi_norm || 0) * 40) +
    (Number(p.aqi_norm || 0) * 35)
  ) / Math.max(wLifestyle + wAff + wTransit + wParks, 1);
}

function buildStats() {
  if (!state.geojson?.features?.length) return {};
  const fields = [
    ...SCORE_FIELDS,
    "price_affordability_norm",
    "ndvi_norm",
    "aqi_norm",
  ];
  const stats = {};
  for (const field of fields) {
    stats[field] = state.geojson.features
      .map((feature) => {
        const raw = Number(feature.properties[field] || 0);
        if (field === "price_affordability_norm" || field === "ndvi_norm" || field === "aqi_norm") {
          return raw * 100;
        }
        return raw;
      })
      .filter((value) => Number.isFinite(value))
      .sort((a, b) => a - b);
  }
  return stats;
}

function interpolateColor(value) {
  const v = Math.max(0, Math.min(100, Number(value) || 0));
  for (let i = 0; i < palette.length - 1; i += 1) {
    const [s0, c0] = palette[i];
    const [s1, c1] = palette[i + 1];
    if (v <= s1) {
      const t = (v - s0) / (s1 - s0 || 1);
      const rgb = c0.map((base, idx) => Math.round(base + (c1[idx] - base) * t));
      return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
    }
  }
  const last = palette[palette.length - 1][1];
  return `rgb(${last[0]}, ${last[1]}, ${last[2]})`;
}

function computeBounds(features) {
  let minLng = Infinity;
  let maxLng = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  features.forEach((feature) => {
    feature.geometry.coordinates[0].forEach(([lng, lat]) => {
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    });
  });
  return { minLng, maxLng, minLat, maxLat };
}

function fitMapToData() {
  if (!state.map || !state.bounds) return;
  const { minLng, maxLng, minLat, maxLat } = state.bounds;
  state.map.fitBounds(
    [
      [minLat, minLng],
      [maxLat, maxLng],
    ],
    {
      padding: [18, 18],
      animate: true,
    }
  );
}

function featureBounds(feature) {
  return L.latLngBounds(feature.geometry.coordinates[0].map(([lng, lat]) => [lat, lng]));
}

function popupHtml(feature) {
  const p = feature.properties;
  const score = Number(p[scoreProperty()] || 0).toFixed(1);
  const reco = Number.isFinite(Number(p.reco_score))
    ? `<p><strong>Recommendation:</strong> ${Number(p.reco_score).toFixed(1)}</p>`
    : "";
  return `
    <div class="hex-popup">
      <strong>${escapeHtml(p.h3_index)}</strong>
      <p>${escapeHtml(p.top_amenities)}</p>
      <p><strong>${state.layer} ${state.mode}:</strong> ${score}</p>
      ${reco}
      <p>${escapeHtml(p.housing_band)}</p>
    </div>
  `;
}

function selectFeature(index, options = {}) {
  const feature = state.geojson?.features?.[index];
  if (!feature) return;

  state.selectedIndex = index;
  renderDetail(feature.properties);
  updateActiveRecommendation();

  if (options.focus && state.map) {
    state.map.fitBounds(featureBounds(feature), {
      animate: true,
      maxZoom: 13.5,
      padding: [64, 64],
    });
  }

  if (options.popup && state.map) {
    L.popup({
      closeButton: true,
      maxWidth: 260,
      className: "hex-popup-shell",
    })
      .setLatLng(featureBounds(feature).getCenter())
      .setContent(popupHtml(feature))
      .openOn(state.map);
  }

  scheduleRender();
}

function bindMapEvents() {
  if (!state.map || state.mapEventsBound) return;
  state.mapEventsBound = true;

  state.map.on("click", (event) => {
    if (!state.projected.length) return;
    const item = findFeatureAt(event.containerPoint.x, event.containerPoint.y);
    if (item) {
      selectFeature(item.index, { popup: true });
    }
  });

  state.map.on("mousemove", (event) => {
    if (!state.projected.length) return;
    const item = findFeatureAt(event.containerPoint.x, event.containerPoint.y);
    const nextIndex = item ? item.index : null;
    mapContainer.style.cursor = item ? "pointer" : "";
    if (nextIndex !== state.hoveredIndex) {
      state.hoveredIndex = nextIndex;
      scheduleRender();
    }
  });

  state.map.on("mouseout zoomstart movestart", () => {
    if (state.hoveredIndex !== null) {
      state.hoveredIndex = null;
      scheduleRender();
    }
    mapContainer.style.cursor = "";
  });

  state.map.on("move zoom resize zoomend moveend viewreset", scheduleRender);
}

function initializeMap() {
  if (state.map) return;
  if (!window.L) {
    throw new Error("Leaflet map library did not load. Check internet/CDN access.");
  }

  state.map = L.map("leaflet-map", {
    zoomControl: true,
    scrollWheelZoom: true,
    doubleClickZoom: true,
    boxZoom: true,
    keyboard: true,
    preferCanvas: true,
    minZoom: 8,
    maxZoom: 18,
    zoomSnap: 0.25,
    zoomDelta: 0.5,
  }).setView([31.2304, 121.4737], 10);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(state.map);

  const fitControl = L.control({ position: "topleft" });
  fitControl.onAdd = () => {
    const button = L.DomUtil.create("button", "map-fit-control");
    button.type = "button";
    button.textContent = "Fit Shanghai";
    button.setAttribute("aria-label", "Fit map to Shanghai H3 extent");
    L.DomEvent.disableClickPropagation(button);
    L.DomEvent.on(button, "click", (event) => {
      L.DomEvent.stop(event);
      fitMapToData();
    });
    return button;
  };
  fitControl.addTo(state.map);

  bindMapEvents();
}

function scheduleRender() {
  if (state.redrawFrame) return;
  state.redrawFrame = window.requestAnimationFrame(() => {
    state.redrawFrame = null;
    renderMap();
  });
}

function project(lng, lat) {
  const point = state.map.latLngToContainerPoint([lat, lng]);
  return [point.x, point.y];
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  const width = Math.max(1, Math.round(rect.width));
  const height = Math.max(1, Math.round(rect.height));
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width, height };
}

function buildProjectedFeatures() {
  state.projected = state.geojson.features.map((feature, index) => ({
    index,
    feature,
    points: feature.geometry.coordinates[0].map(([lng, lat]) => project(lng, lat)),
  }));
}

function tracePolygon(points) {
  if (!points.length) return;
  ctx.beginPath();
  ctx.moveTo(points[0][0], points[0][1]);
  for (let i = 1; i < points.length; i += 1) {
    ctx.lineTo(points[i][0], points[i][1]);
  }
  ctx.closePath();
}

function renderMap() {
  if (!state.geojson?.features?.length || !state.map) return;

  const { width, height } = resizeCanvas();
  buildProjectedFeatures();
  const prop = scoreProperty();
  const topPickIds = new Set(state.topPicks.map((feature) => feature.properties.h3_index));

  ctx.clearRect(0, 0, width, height);
  ctx.lineJoin = "round";
  ctx.lineCap = "round";

  for (const item of state.projected) {
    const p = item.feature.properties;
    tracePolygon(item.points);
    ctx.fillStyle = interpolateColor(Number(p[prop] || 0));
    ctx.globalAlpha = state.overlayOpacity;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.lineWidth = item.index === state.hoveredIndex ? 2 : 0.45;
    ctx.strokeStyle = item.index === state.hoveredIndex ? "rgba(25, 33, 38, 0.92)" : "rgba(62, 45, 30, 0.22)";
    ctx.stroke();
  }

  ctx.lineWidth = 2.4;
  ctx.strokeStyle = "#1f7a6d";
  for (const item of state.projected) {
    if (!topPickIds.has(item.feature.properties.h3_index)) continue;
    tracePolygon(item.points);
    ctx.stroke();
  }

  if (state.selectedIndex !== null && state.projected[state.selectedIndex]) {
    ctx.lineWidth = 2.8;
    ctx.strokeStyle = "rgba(25, 33, 38, 0.94)";
    tracePolygon(state.projected[state.selectedIndex].points);
    ctx.stroke();
  }
}

function recomputeRecommendations() {
  if (!state.geojson?.features?.length) return;

  const features = state.geojson.features.map((feature) => {
    feature.properties.reco_score = computeRecommendation(feature);
    return feature;
  });

  state.topPicks = features
    .slice()
    .sort((a, b) => b.properties.reco_score - a.properties.reco_score)
    .slice(0, 10);

  document.getElementById("recommendations-content").innerHTML = topPicksHtml();
  bindRecommendationButtons();
  updateActiveRecommendation();
  scheduleRender();
}

function normalizePayload(appPayload) {
  if (Array.isArray(appPayload)) {
    return appPayload;
  }

  const schema = appPayload.schema || [];
  return (appPayload.features || []).map((record) => {
    const coordinates = record[0];
    const values = record[1] || [];
    return {
      coordinates,
      properties: Object.fromEntries(schema.map((key, idx) => [key, values[idx]])),
    };
  });
}

async function boot() {
  try {
    initializeMap();
    setLoadingState(true);
    setStatus("Loading submission links and transparency metadata…");
    const manifest = await fetch("./data/project_manifest.json").then((r) => {
      if (!r.ok) throw new Error(`Manifest request failed: ${r.status}`);
      return r.json();
    });
    state.manifest = manifest;
    renderSubmissionLinks();
    renderManifest();

    setStatus("Loading H3 payload and computing citywide statistics…");
    const appPayload = await fetch("./data/shanghai_h3_seed_min.json").then((r) => {
      if (!r.ok) throw new Error(`App JSON request failed: ${r.status}`);
      return r.json();
    });
    const payloadFeatures = normalizePayload(appPayload);

    state.geojson = {
      type: "FeatureCollection",
      features: payloadFeatures.map((item) => ({
        type: "Feature",
        geometry: {
          type: "Polygon",
          coordinates: [[...item.coordinates, item.coordinates[0]]],
        },
        properties: item.properties,
      })),
    };
    state.bounds = computeBounds(state.geojson.features);
    state.featureIndexByH3 = new Map(
      state.geojson.features.map((feature, index) => [feature.properties.h3_index, index])
    );
    state.stats = buildStats();

    setStatus("Rendering Shanghai hexes, recommendations, and detail panels…");
    fitMapToData();
    recomputeRecommendations();
    if (state.geojson.features.length) {
      selectFeature(0, { popup: false });
    }
    setLoadingState(false);
    setStatus(
      `Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells over a zoomable basemap for ${state.layer} ${state.mode}.`
    );
  } catch (error) {
    console.error(error);
    setLoadingState(false);
    setStatus(`Load error: ${error.message}`);
  }
}

function pointInPolygon(x, y, points) {
  let inside = false;
  for (let i = 0, j = points.length - 1; i < points.length; j = i, i += 1) {
    const [xi, yi] = points[i];
    const [xj, yj] = points[j];
    const crosses = yi > y !== yj > y;
    if (crosses) {
      const xAtY = ((xj - xi) * (y - yi)) / (yj - yi) + xi;
      if (x < xAtY) inside = !inside;
    }
  }
  return inside;
}

function findFeatureAt(x, y) {
  for (let i = state.projected.length - 1; i >= 0; i -= 1) {
    const item = state.projected[i];
    if (pointInPolygon(x, y, item.points)) return item;
  }
  return null;
}

document.querySelectorAll("#mode-toggle button").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    updateActiveButtons("mode-toggle", "mode", state.mode);
    scheduleRender();
    recomputeRecommendations();
    if (state.geojson?.features?.[state.selectedIndex]) {
      renderDetail(state.geojson.features[state.selectedIndex].properties);
    }
    if (state.manifest) {
      setStatus(
        `Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells over a zoomable basemap for ${state.layer} ${state.mode}.`
      );
    }
  });
});

document.querySelectorAll("#layer-toggle button").forEach((button) => {
  button.addEventListener("click", () => {
    state.layer = button.dataset.layer;
    updateActiveButtons("layer-toggle", "layer", state.layer);
    scheduleRender();
    if (state.geojson?.features?.[state.selectedIndex]) {
      renderDetail(state.geojson.features[state.selectedIndex].properties);
    }
    if (state.manifest) {
      setStatus(
        `Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells over a zoomable basemap for ${state.layer} ${state.mode}.`
      );
    }
  });
});

document.getElementById("recompute-button").addEventListener("click", recomputeRecommendations);

document.getElementById("overlay-opacity").addEventListener("input", (event) => {
  state.overlayOpacity = Number(event.target.value) / 100;
  document.getElementById("overlay-opacity-value").textContent = `${event.target.value}%`;
  scheduleRender();
});

window.addEventListener("resize", () => {
  if (state.map) state.map.invalidateSize();
  if (state.geojson) scheduleRender();
});

boot();
