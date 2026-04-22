const replayElements = {
  message: document.getElementById("replayMessage"),
  dataset: document.getElementById("replayDataset"),
  refresh: document.getElementById("replayRefresh"),
  followLive: document.getElementById("followLive"),
  status: document.getElementById("replayStatus"),
  slider: document.getElementById("replaySlider"),
  position: document.getElementById("replayPosition"),
  time: document.getElementById("replayTime"),
  viewport: document.getElementById("replayViewport"),
  hud: {
    dataset: document.getElementById("hudDataset"),
    sample: document.getElementById("hudSample"),
    time: document.getElementById("hudTime"),
    received: document.getElementById("hudReceived"),
    row: document.getElementById("hudRow"),
    parse: document.getElementById("hudParse"),
    gpsFix: document.getElementById("hudGpsFix"),
    gpsSatellites: document.getElementById("hudGpsSatellites"),
    gpsPosition: document.getElementById("hudGpsPosition"),
    gpsAltitude: document.getElementById("hudGpsAltitude"),
    bmeAltitude: document.getElementById("hudBmeAltitude"),
    tmp36: document.getElementById("hudTmp36"),
    bmeTemp: document.getElementById("hudBmeTemp"),
    pressure: document.getElementById("hudPressure"),
    humidity: document.getElementById("hudHumidity"),
    gas: document.getElementById("hudGas"),
    attitude: document.getElementById("hudAttitude"),
    accel: document.getElementById("hudAccel"),
    gyro: document.getElementById("hudGyro"),
    gpsMotion: document.getElementById("hudGpsMotion"),
    rawLine: document.getElementById("hudRawLine")
  }
};

const replayState = {
  rowCount: 0,
  rowIndex: 0,
  followTimer: null,
  sliderTimer: null,
  requestId: 0,
  selectedDataset: null,
  scene: null,
  camera: null,
  renderer: null,
  controls: null,
  craft: null,
  modelHolder: null,
  visualAltitude: 0
};

const ASSET_BASE = "assets/3d/";
const DEG_TO_RAD = Math.PI / 180;

function setReplayMessage(text, type = "") {
  if (!replayElements.message) {
    return;
  }

  replayElements.message.textContent = text;
  replayElements.message.className = `message ${type}`.trim();
}

function numericValue(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }

  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value, digits = 1) {
  const number = numericValue(value);
  if (number === null) {
    return "--";
  }

  return number.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function formatValue(value, digits, unit) {
  const text = formatNumber(value, digits);
  return text === "--" ? text : `${text}${unit ? ` ${unit}` : ""}`;
}

function timeOnly(value) {
  if (value === null || value === undefined || value === "") {
    return "";
  }

  const text = String(value);
  const match = text.match(/(\d{2}:\d{2}:\d{2})/);
  if (match) {
    return match[1];
  }

  const compact = text.match(/\b(\d{2})(\d{2})(\d{2})\b/);
  if (compact) {
    return `${compact[1]}:${compact[2]}:${compact[3]}`;
  }

  return text;
}

function setHudValue(key, value) {
  const element = replayElements.hud[key];
  if (element) {
    element.textContent = value;
  }
}

function selectedDataset() {
  const option = replayElements.dataset.options[replayElements.dataset.selectedIndex];
  if (!option) {
    return null;
  }

  return {
    id: option.value,
    name: option.textContent.replace(/\s+\([0-9,]+ rows\)$/, ""),
    type: option.dataset.type || "",
    isProtected: option.dataset.protected === "1"
  };
}

function selectedDatasetIsLive() {
  const dataset = selectedDataset();
  return Boolean(dataset && (dataset.type === "live" || dataset.isProtected));
}

function updateFollowLiveState(defaultToLive = false) {
  const isLive = selectedDatasetIsLive();
  replayElements.followLive.disabled = !isLive;

  if (!isLive) {
    replayElements.followLive.checked = false;
  } else if (defaultToLive) {
    replayElements.followLive.checked = true;
  }

  syncFollowTimer();
}

function stopFollowTimer() {
  if (replayState.followTimer) {
    clearInterval(replayState.followTimer);
    replayState.followTimer = null;
  }
}

function syncFollowTimer() {
  stopFollowTimer();

  if (replayElements.followLive.checked && selectedDatasetIsLive()) {
    replayState.followTimer = setInterval(() => {
      loadReplayRow({ latest: true, quiet: true }).catch((error) => setReplayMessage(error.message, "error"));
    }, 1000);
  }
}

async function loadDatasets() {
  const response = await fetch("api/datasets.php", { cache: "no-store" });
  const data = await response.json();

  if (!data.ok) {
    throw new Error(data.error || "Could not load datasets.");
  }

  replayElements.dataset.innerHTML = "";
  let liveId = null;

  data.datasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.dataset.type = dataset.type;
    option.dataset.protected = dataset.is_protected;
    option.dataset.rowCount = dataset.row_count;
    option.textContent = `${dataset.name} (${Number(dataset.row_count || 0).toLocaleString()} rows)`;
    replayElements.dataset.appendChild(option);

    if (!liveId && (dataset.type === "live" || Number(dataset.is_protected) === 1)) {
      liveId = dataset.id;
    }
  });

  if (liveId !== null) {
    replayElements.dataset.value = String(liveId);
  }

  updateFollowLiveState(true);
}

function updateTimeline(index, rowCount, row) {
  replayState.rowCount = rowCount;
  replayState.rowIndex = index;

  const max = Math.max(rowCount - 1, 0);
  replayElements.slider.min = "0";
  replayElements.slider.max = String(max);
  replayElements.slider.value = String(Math.min(index, max));
  replayElements.slider.disabled = rowCount < 1;

  replayElements.position.textContent = rowCount
    ? `${index + 1} / ${rowCount.toLocaleString()}`
    : "0 / 0";
  replayElements.time.textContent = row ? (timeOnly(row.device_time) || timeOnly(row.received_at) || "--") : "--";
}

function clearHud(datasetName = "--") {
  setHudValue("dataset", datasetName);
  setHudValue("sample", "--");
  setHudValue("time", "--");
  setHudValue("received", "--");
  setHudValue("row", "--");
  setHudValue("parse", "--");
  setHudValue("gpsFix", "--");
  setHudValue("gpsSatellites", "--");
  setHudValue("gpsPosition", "--");
  setHudValue("gpsAltitude", "--");
  setHudValue("bmeAltitude", "--");
  setHudValue("tmp36", "--");
  setHudValue("bmeTemp", "--");
  setHudValue("pressure", "--");
  setHudValue("humidity", "--");
  setHudValue("gas", "--");
  setHudValue("attitude", "--");
  setHudValue("accel", "--");
  setHudValue("gyro", "--");
  setHudValue("gpsMotion", "--");
  setHudValue("rawLine", "--");
  applyModelState(null);
}

function renderHud(row, dataset, index, rowCount) {
  if (!row) {
    clearHud(dataset ? dataset.name : "--");
    return;
  }

  setHudValue("dataset", dataset ? dataset.name : "--");
  setHudValue("sample", row.mcu_sample_id ?? "--");
  setHudValue("time", timeOnly(row.device_time) || "--");
  setHudValue("received", timeOnly(row.received_at) || "--");
  setHudValue("row", rowCount ? `${index + 1} / ${rowCount.toLocaleString()}` : "--");
  setHudValue("parse", Number(row.parse_ok) ? "OK" : (row.parse_message || "Parse error"));
  setHudValue("gpsFix", row.gps_fix === null || row.gps_fix === undefined ? "--" : (Number(row.gps_fix) ? "Yes" : "No"));
  setHudValue("gpsSatellites", row.gps_satellites ?? "--");

  const lat = numericValue(row.gps_lat);
  const lon = numericValue(row.gps_lon);
  setHudValue("gpsPosition", lat === null || lon === null ? "--" : `${formatNumber(lat, 6)}, ${formatNumber(lon, 6)}`);
  setHudValue("gpsAltitude", formatValue(row.gps_altitude, 1, "m"));
  setHudValue("bmeAltitude", formatValue(row.bme_altitude, 1, "m"));
  setHudValue("tmp36", formatValue(row.tmp36_temp, 1, "C"));
  setHudValue("bmeTemp", formatValue(row.bme_temp, 1, "C"));
  setHudValue("pressure", formatValue(row.bme_pressure, 1, "hPa"));
  setHudValue("humidity", formatValue(row.bme_humidity, 1, "%"));

  const gas = formatValue(row.bme_gas, 0, "ohm");
  const gasValid = row.bme_gas_valid === null || row.bme_gas_valid === undefined ? "--" : (Number(row.bme_gas_valid) ? "valid" : "not valid");
  setHudValue("gas", `${gas} / ${gasValid}`);

  setHudValue(
    "attitude",
    `P ${formatValue(row.pitch, 1, "deg")} | R ${formatValue(row.roll, 1, "deg")} | H ${formatValue(row.heading, 1, "deg")}`
  );
  setHudValue(
    "accel",
    `Ax ${formatValue(row.ax, 2, "g")} | Ay ${formatValue(row.ay, 2, "g")} | Az ${formatValue(row.az, 2, "g")}`
  );
  setHudValue(
    "gyro",
    `Gx ${formatValue(row.gx, 2, "dps")} | Gy ${formatValue(row.gy, 2, "dps")} | Gz ${formatValue(row.gz, 2, "dps")}`
  );
  setHudValue(
    "gpsMotion",
    `${formatValue(row.gps_speed_kmh, 1, "km/h")} | C ${formatValue(row.gps_course_deg, 1, "deg")} | V ${formatValue(row.gps_vertical_speed_ms, 2, "m/s")}`
  );
  setHudValue("rawLine", row.raw_line || "--");

  applyModelState(row);
}

async function loadReplayRow({ latest = false, index = null, quiet = false } = {}) {
  const dataset = selectedDataset();
  if (!dataset) {
    setReplayMessage("No dataset selected.");
    return;
  }

  const requestId = replayState.requestId + 1;
  replayState.requestId = requestId;

  if (!quiet) {
    setReplayMessage("Loading sample...");
  }

  const params = new URLSearchParams({ dataset_id: dataset.id });
  if (latest) {
    params.set("latest", "1");
  } else {
    params.set("index", String(index === null ? Number(replayElements.slider.value || 0) : index));
  }

  const response = await fetch(`api/replay.php?${params.toString()}`, { cache: "no-store" });
  const data = await response.json();

  if (requestId !== replayState.requestId) {
    return;
  }

  if (!data.ok) {
    throw new Error(data.error || "Could not load replay row.");
  }

  replayState.selectedDataset = data.dataset;
  const rowCount = Number(data.meta && data.meta.row_count ? data.meta.row_count : 0);
  const rowIndex = Number(data.index || 0);

  updateTimeline(rowIndex, rowCount, data.row);
  renderHud(data.row, dataset, rowIndex, rowCount);

  const mode = replayElements.followLive.checked && selectedDatasetIsLive() ? "Follow Live" : "Replay";
  replayElements.status.textContent = `${mode} - ${dataset.name}`;
  setReplayMessage(rowCount ? "Replay data loaded." : "Selected dataset has no telemetry rows.", rowCount ? "ok" : "");
}

function queueSliderLoad() {
  stopFollowTimer();
  replayElements.followLive.checked = false;
  replayElements.position.textContent = replayState.rowCount
    ? `${Number(replayElements.slider.value) + 1} / ${replayState.rowCount.toLocaleString()}`
    : "0 / 0";

  if (replayState.sliderTimer) {
    clearTimeout(replayState.sliderTimer);
  }

  replayState.sliderTimer = setTimeout(() => {
    loadReplayRow({ index: Number(replayElements.slider.value || 0) }).catch((error) => setReplayMessage(error.message, "error"));
  }, 120);
}

function resizeRenderer() {
  if (!replayState.renderer || !replayElements.viewport || !replayState.camera) {
    return;
  }

  const width = Math.max(1, replayElements.viewport.clientWidth);
  const height = Math.max(1, replayElements.viewport.clientHeight);
  replayState.renderer.setSize(width, height, false);
  replayState.camera.aspect = width / height;
  replayState.camera.updateProjectionMatrix();
}

function loadSkybox() {
  if (!window.THREE || !replayState.scene) {
    return;
  }

  const loader = new THREE.CubeTextureLoader();
  loader.setPath(ASSET_BASE);
  loader.load(
    ["px.jpg", "nx.jpg", "py.jpg", "ny.jpg", "pz.jpg", "nz.jpg"],
    (texture) => {
      replayState.scene.background = texture;
    },
    undefined,
    () => {
      replayState.scene.background = new THREE.Color(0x07090e);
    }
  );
}

function createFallbackModel() {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(3.2, 5.2, 3.2),
    new THREE.MeshStandardMaterial({ color: 0xdbe6f3, roughness: 0.45, metalness: 0.18 })
  );
  const nose = new THREE.Mesh(
    new THREE.ConeGeometry(2.25, 2.8, 32),
    new THREE.MeshStandardMaterial({ color: 0x6db6ff, roughness: 0.32, metalness: 0.12 })
  );
  nose.position.y = 4;
  group.add(body, nose);
  return group;
}

function clearObject(object) {
  while (object.children.length) {
    object.remove(object.children[0]);
  }
}

function normalizeLoadedModel(object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  const largest = Math.max(size.x, size.y, size.z) || 1;
  const scale = 8 / largest;
  object.position.sub(center);
  object.scale.setScalar(scale);
  object.rotation.x = -Math.PI / 2;
}

function loadModel() {
  if (!window.THREE || !THREE.GLTFLoader || !replayState.modelHolder) {
    const fallback = createFallbackModel();
    replayState.modelHolder.add(fallback);
    return;
  }

  const loader = new THREE.GLTFLoader();
  loader.load(
    `${ASSET_BASE}model.glb`,
    (gltf) => {
      const object = gltf.scene;
      normalizeLoadedModel(object);
      clearObject(replayState.modelHolder);
      replayState.modelHolder.add(object);
    },
    undefined,
    () => {
      clearObject(replayState.modelHolder);
      replayState.modelHolder.add(createFallbackModel());
      setReplayMessage("3D model asset could not load; using fallback shape.", "error");
    }
  );
}

function init3d() {
  if (!replayElements.viewport) {
    return;
  }

  if (!window.THREE) {
    setReplayMessage("Three.js is not loaded.", "error");
    return;
  }

  replayState.scene = new THREE.Scene();
  replayState.scene.background = new THREE.Color(0x07090e);
  replayState.camera = new THREE.PerspectiveCamera(62, 1, 0.1, 2000);
  replayState.camera.position.set(0, 14, 34);

  replayState.renderer = new THREE.WebGLRenderer({ antialias: true });
  replayState.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  replayElements.viewport.appendChild(replayState.renderer.domElement);

  if (THREE.OrbitControls) {
    replayState.controls = new THREE.OrbitControls(replayState.camera, replayState.renderer.domElement);
    replayState.controls.enableDamping = true;
    replayState.controls.dampingFactor = 0.06;
    replayState.controls.enablePan = false;
    replayState.controls.target.set(0, 0, 0);
  }

  replayState.scene.add(new THREE.AmbientLight(0xffffff, 0.8));

  const keyLight = new THREE.DirectionalLight(0xffffff, 1.8);
  keyLight.position.set(10, 18, 14);
  replayState.scene.add(keyLight);

  const fillLight = new THREE.PointLight(0x6db6ff, 1.2, 160);
  fillLight.position.set(-18, 20, 24);
  replayState.scene.add(fillLight);

  const grid = new THREE.GridHelper(180, 36, 0x6db6ff, 0x303846);
  grid.position.y = 0;
  replayState.scene.add(grid);

  replayState.craft = new THREE.Group();
  replayState.modelHolder = new THREE.Group();
  replayState.craft.add(replayState.modelHolder);
  replayState.craft.add(createAttitudeMarker());
  replayState.scene.add(replayState.craft);

  loadSkybox();
  loadModel();
  resizeRenderer();

  function animate() {
    requestAnimationFrame(animate);
    if (replayState.controls) {
      replayState.controls.update();
    }
    replayState.renderer.render(replayState.scene, replayState.camera);
  }

  animate();
}

function applyModelState(row) {
  if (!replayState.craft) {
    return;
  }

  const pitch = numericValue(row && row.pitch) || 0;
  const roll = numericValue(row && row.roll) || 0;
  const heading = numericValue(row && row.heading) || 0;
  const altitude = numericValue(row && row.bme_altitude) || 0;
  const deltaAltitude = altitude - replayState.visualAltitude;

  replayState.craft.rotation.set(pitch * DEG_TO_RAD, -heading * DEG_TO_RAD, roll * DEG_TO_RAD, "YXZ");
  replayState.craft.position.y = altitude;

  if (replayState.camera && Number.isFinite(deltaAltitude)) {
    replayState.camera.position.y += deltaAltitude;
  }

  if (replayState.controls && Number.isFinite(deltaAltitude)) {
    replayState.controls.target.y += deltaAltitude;
    replayState.controls.update();
  }

  replayState.visualAltitude = altitude;
}

function createAttitudeMarker() {
  const group = new THREE.Group();
  const ringMaterial = new THREE.MeshBasicMaterial({
    color: 0xf6d36d,
    transparent: true,
    opacity: 0.9,
    depthTest: false
  });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(6.5, 0.08, 8, 96), ringMaterial);
  ring.rotation.x = Math.PI / 2;
  ring.renderOrder = 10;

  const center = new THREE.Mesh(
    new THREE.SphereGeometry(1.05, 24, 16),
    new THREE.MeshBasicMaterial({ color: 0xf6d36d, depthTest: false })
  );
  center.renderOrder = 10;

  const xAxis = new THREE.ArrowHelper(new THREE.Vector3(1, 0, 0), new THREE.Vector3(0, 0, 0), 9, 0xff6b6b, 1.25, 0.6);
  const yAxis = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(0, 0, 0), 9, 0x80d27e, 1.25, 0.6);
  const zAxis = new THREE.ArrowHelper(new THREE.Vector3(0, 0, 1), new THREE.Vector3(0, 0, 0), 9, 0x6db6ff, 1.25, 0.6);

  group.add(ring, center, xAxis, yAxis, zAxis);
  group.traverse((child) => {
    if (child.material) {
      child.material.depthTest = false;
    }
    child.renderOrder = 10;
  });
  return group;
}

replayElements.dataset.addEventListener("change", () => {
  updateFollowLiveState(true);
  loadReplayRow({ latest: true }).catch((error) => setReplayMessage(error.message, "error"));
});

replayElements.refresh.addEventListener("click", () => {
  loadDatasets()
    .then(() => loadReplayRow({ latest: true }))
    .catch((error) => setReplayMessage(error.message, "error"));
});

replayElements.followLive.addEventListener("change", () => {
  syncFollowTimer();
  loadReplayRow({ latest: replayElements.followLive.checked }).catch((error) => setReplayMessage(error.message, "error"));
});

replayElements.slider.addEventListener("input", queueSliderLoad);
replayElements.slider.addEventListener("change", () => {
  if (replayState.sliderTimer) {
    clearTimeout(replayState.sliderTimer);
  }
  loadReplayRow({ index: Number(replayElements.slider.value || 0) }).catch((error) => setReplayMessage(error.message, "error"));
});

window.addEventListener("resize", resizeRenderer);

init3d();
loadDatasets()
  .then(() => loadReplayRow({ latest: true }))
  .catch((error) => setReplayMessage(error.message, "error"));
