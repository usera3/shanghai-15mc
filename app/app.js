const state = {
  mode: "walk",
  layer: "composite",
  geojson: null,
  manifest: null,
  topPicks: [],
  bounds: null,
  projected: [],
  hoveredIndex: null,
  selectedIndex: 0,
};

const canvas = document.getElementById("hex-map");
const ctx = canvas.getContext("2d");

const palette = [
  [0, [241, 231, 207]],
  [25, [244, 196, 111]],
  [50, [233, 127, 68]],
  [75, [178, 66, 43]],
  [100, [94, 24, 17]],
];

function setStatus(message) {
  const el = document.getElementById("status-line");
  if (el) el.textContent = message;
}

function scoreProperty() {
  return `score_${state.layer}_${state.mode}`;
}

function updateActiveButtons(groupId, key, value) {
  document.querySelectorAll(`#${groupId} button`).forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset[key] === value);
  });
}

function renderDetail(properties) {
  const networkAccess = ["walk", "bike"].includes(state.mode)
    ? `<p><strong>Road-network access (${state.mode}):</strong> ${Number(properties[`network_access_${state.mode}`] || 0).toFixed(1)}</p>`
    : "";
  const priceLine = properties.has_housing_sample
    ? `¥${Math.round(properties.avg_price_m2).toLocaleString()}/m²`
    : "No housing sample in this hex";
  const html = `
    <p><strong>H3:</strong> <code>${properties.h3_index}</code></p>
    <p><strong>Top amenity mix:</strong> ${properties.top_amenities}</p>
    <p><strong>${state.layer} ${state.mode} score:</strong> ${Number(properties[scoreProperty()]).toFixed(1)}</p>
    <p><strong>15-minute proxy access (${state.mode}):</strong> ${Number(properties[`proxy_access_${state.mode}`] || 0).toFixed(1)}</p>
    ${networkAccess}
    <p><strong>Average sale-price proxy:</strong> ${priceLine}</p>
    <p><strong>Average subway distance:</strong> ${Math.round(properties.avg_subway_distance_m).toLocaleString()} m</p>
    <p><strong>Housing band:</strong> ${properties.housing_band}</p>
    <p>
      <span class="metric-pill">NDVI ${Number(properties.ndvi ?? 0).toFixed(3)}</span>
      <span class="metric-pill">AQI ${Number(properties.european_aqi ?? 0).toFixed(0)}</span>
    </p>
    <ul>
      <li>Schools: ${properties.school_count}</li>
      <li>Healthcare: ${properties.healthcare_count}</li>
      <li>Groceries: ${properties.grocery_count}</li>
      <li>Parks: ${properties.park_count}</li>
      <li>Bus stops: ${properties.bus_stop_count}</li>
      <li>Subway exits: ${properties.subway_exit_count}</li>
      <li>Gyms: ${properties.gym_count}</li>
      <li>Bike km proxy: ${Number(properties.bike_length_km).toFixed(2)}</li>
    </ul>
  `;
  document.getElementById("detail-content").innerHTML = html;
}

function topPicksHtml() {
  if (!state.topPicks.length) return "<p>No top picks computed yet.</p>";
  return `
    <ul>
      ${state.topPicks
        .map(
          (feature, idx) =>
            `<li><strong>${idx + 1}.</strong> ${feature.properties.h3_index} · ${feature.properties.housing_band} · score ${feature.properties.reco_score.toFixed(1)}</li>`
        )
        .join("")}
    </ul>
  `;
}

function renderManifest() {
  const manifest = state.manifest;
  const sources = manifest.source_provenance || [];
  const methodSummary = manifest.method_summary || [];
  document.getElementById("manifest-content").innerHTML = `
    <p><strong>Track:</strong> ${manifest.track}</p>
    <p><strong>Resolution:</strong> H3 r${manifest.h3_resolution}</p>
    <p><strong>Grid:</strong> ${manifest.grid_cell_size_m} m · ${manifest.grid_cell_count.toLocaleString()} cells</p>
    <p><strong>Hex count:</strong> ${manifest.feature_count}</p>
    <p><strong>Updated:</strong> ${manifest.created_at_utc || "local prototype build"}</p>
    <p><strong>Prototype note:</strong> Proxy scores aggregated from housing, POI, environmental, and road-network layers.</p>
    <p><strong>Sources:</strong> ${sources.map((item) => item.source).join(" · ")}</p>
    <p><strong>Method:</strong> ${methodSummary.slice(0, 3).join(" ")}</p>
    <ul>
      ${manifest.limitations.map((item) => `<li>${item}</li>`).join("")}
    </ul>
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

function project(lng, lat, width, height, padding = 28) {
  const { minLng, maxLng, minLat, maxLat } = state.bounds;
  const usableW = width - padding * 2;
  const usableH = height - padding * 2;
  const x = padding + ((lng - minLng) / (maxLng - minLng || 1)) * usableW;
  const y = height - padding - ((lat - minLat) / (maxLat - minLat || 1)) * usableH;
  return [x, y];
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

function buildProjectedFeatures(width, height) {
  state.projected = state.geojson.features.map((feature, index) => ({
    index,
    feature,
    points: feature.geometry.coordinates[0].map(([lng, lat]) => project(lng, lat, width, height)),
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
  if (!state.geojson?.features?.length) return;

  const { width, height } = resizeCanvas();
  buildProjectedFeatures(width, height);
  const prop = scoreProperty();
  const topPickIds = new Set(state.topPicks.map((feature) => feature.properties.h3_index));

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "rgba(249, 246, 237, 0.68)";
  ctx.fillRect(0, 0, width, height);

  for (const item of state.projected) {
    const p = item.feature.properties;
    tracePolygon(item.points);
    ctx.fillStyle = interpolateColor(Number(p[prop] || 0));
    ctx.globalAlpha = 0.96;
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.lineWidth = item.index === state.hoveredIndex ? 1.7 : 0.55;
    ctx.strokeStyle = item.index === state.hoveredIndex ? "rgba(25, 33, 38, 0.85)" : "rgba(62, 45, 30, 0.24)";
    ctx.stroke();
  }

  ctx.lineWidth = 2.4;
  ctx.strokeStyle = "#1f7a6d";
  for (const item of state.projected) {
    if (!topPickIds.has(item.feature.properties.h3_index)) continue;
    tracePolygon(item.points);
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
  renderMap();
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
    const [appPayload, manifest] = await Promise.all([
      fetch("./data/shanghai_h3_seed_min.json").then((r) => {
        if (!r.ok) throw new Error(`App JSON request failed: ${r.status}`);
        return r.json();
      }),
      fetch("./data/project_manifest.json").then((r) => {
        if (!r.ok) throw new Error(`Manifest request failed: ${r.status}`);
        return r.json();
      }),
    ]);
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
    state.manifest = manifest;
    state.bounds = computeBounds(state.geojson.features);

    renderManifest();
    recomputeRecommendations();
    if (state.geojson.features.length) {
      state.selectedIndex = 0;
      renderDetail(state.geojson.features[state.selectedIndex].properties);
    }
    setStatus(`Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells for ${state.layer} ${state.mode}.`);
  } catch (error) {
    console.error(error);
    setStatus(`Load error: ${error.message}`);
  }
}

function eventPoint(event) {
  const rect = canvas.getBoundingClientRect();
  return [event.clientX - rect.left, event.clientY - rect.top];
}

function findFeatureAt(x, y) {
  for (let i = state.projected.length - 1; i >= 0; i -= 1) {
    const item = state.projected[i];
    tracePolygon(item.points);
    if (ctx.isPointInPath(x, y)) return item;
  }
  return null;
}

canvas.addEventListener("click", (event) => {
  if (!state.projected.length) return;
  const [x, y] = eventPoint(event);
  const item = findFeatureAt(x, y);
  if (item) {
    state.selectedIndex = item.index;
    renderDetail(item.feature.properties);
  }
});

canvas.addEventListener("mousemove", (event) => {
  if (!state.projected.length) return;
  const [x, y] = eventPoint(event);
  const item = findFeatureAt(x, y);
  const nextIndex = item ? item.index : null;
  canvas.style.cursor = item ? "pointer" : "default";
  if (nextIndex !== state.hoveredIndex) {
    state.hoveredIndex = nextIndex;
    renderMap();
  }
});

canvas.addEventListener("mouseleave", () => {
  state.hoveredIndex = null;
  canvas.style.cursor = "default";
  renderMap();
});

document.querySelectorAll("#mode-toggle button").forEach((button) => {
  button.addEventListener("click", () => {
    state.mode = button.dataset.mode;
    updateActiveButtons("mode-toggle", "mode", state.mode);
    renderMap();
    recomputeRecommendations();
    if (state.geojson?.features?.[state.selectedIndex]) {
      renderDetail(state.geojson.features[state.selectedIndex].properties);
    }
    if (state.manifest) {
      setStatus(`Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells for ${state.layer} ${state.mode}.`);
    }
  });
});

document.querySelectorAll("#layer-toggle button").forEach((button) => {
  button.addEventListener("click", () => {
    state.layer = button.dataset.layer;
    updateActiveButtons("layer-toggle", "layer", state.layer);
    renderMap();
    if (state.geojson?.features?.[state.selectedIndex]) {
      renderDetail(state.geojson.features[state.selectedIndex].properties);
    }
    if (state.manifest) {
      setStatus(`Loaded ${state.manifest.feature_count.toLocaleString()} H3 cells for ${state.layer} ${state.mode}.`);
    }
  });
});

document.getElementById("recompute-button").addEventListener("click", recomputeRecommendations);

window.addEventListener("resize", () => {
  if (state.geojson) renderMap();
});

boot();
