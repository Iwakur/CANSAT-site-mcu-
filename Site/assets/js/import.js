const importForm = document.getElementById("importForm");
const importMessage = document.getElementById("message");
const datasetSelect = document.getElementById("datasetSelect");
const copyLiveButton = document.getElementById("copyLive");
const deleteButton = document.getElementById("deleteDataset");
const clearImportsButton = document.getElementById("clearImports");
const savedStats = document.getElementById("savedStats");
const chartContainer = document.getElementById("charts");
const savedGpsMap = document.getElementById("savedGpsMap");
const rawToggle = document.getElementById("rawToggle");
const charts = {};
let lastRows = [];

function selectedDataset() {
  return datasetSelect.options[datasetSelect.selectedIndex];
}

async function loadDatasets(selectId = null) {
  const response = await fetch("api/datasets.php", { cache: "no-store" });
  const data = await response.json();

  if (!data.ok) {
    throw new Error(data.error || "Could not load datasets.");
  }

  datasetSelect.innerHTML = "";

  data.datasets.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.id;
    option.dataset.protected = dataset.is_protected;
    option.dataset.rowCount = dataset.row_count;
    option.textContent = `${dataset.name} (${dataset.row_count} rows)`;
    datasetSelect.appendChild(option);
  });

  if (selectId) {
    datasetSelect.value = String(selectId);
  }

  updateDeleteState();
}

function updateDeleteState() {
  const option = selectedDataset();
  deleteButton.disabled = !option || option.dataset.protected === "1";
}

async function loadSelectedDataset() {
  const option = selectedDataset();

  if (!option) {
    CansatCharts.setMessage(importMessage, "No dataset selected.");
    return;
  }

  updateDeleteState();

  const response = await fetch(`api/latest.php?dataset_id=${encodeURIComponent(option.value)}&limit=2000`, { cache: "no-store" });
  const data = await response.json();

  if (!data.ok) {
    throw new Error(data.error || "Could not load dataset.");
  }

  const rows = data.rows || [];
  lastRows = rows;
  CansatCharts.renderSummary(rows, data.meta || {}, savedStats);
  CansatCharts.renderGpsMap(rows, savedGpsMap);
  CansatCharts.setMessage(importMessage, rows.length ? "Dataset loaded." : "Dataset has no rows.");
  CansatCharts.render(rows, chartContainer, charts, importMessage, { showRaw: Boolean(rawToggle && rawToggle.checked) });
}

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  try {
    CansatCharts.setMessage(importMessage, "Importing file...");
    const response = await fetch("api/import.php", {
      method: "POST",
      body: new FormData(importForm)
    });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Import failed.");
    }

    CansatCharts.setMessage(
      importMessage,
      `Imported ${data.rows_inserted} row(s) from ${data.lines_read} line(s). Bad rows: ${data.bad_rows}.`,
      "ok"
    );
    importForm.reset();
    await loadDatasets(data.dataset_id);
    await loadSelectedDataset();
  } catch (error) {
    CansatCharts.setMessage(importMessage, error.message, "error");
  }
});

datasetSelect.addEventListener("change", () => {
  loadSelectedDataset().catch((error) => CansatCharts.setMessage(importMessage, error.message, "error"));
});

copyLiveButton.addEventListener("click", async () => {
  try {
    CansatCharts.setMessage(importMessage, "Copying live dataset...");
    const body = new URLSearchParams({ action: "copy_live" });
    const response = await fetch("api/datasets.php", { method: "POST", body });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Could not copy live dataset.");
    }

    CansatCharts.setMessage(importMessage, `Copied Live to ${data.dataset_name}.`, "ok");
    await loadDatasets(data.dataset_id);
    await loadSelectedDataset();
  } catch (error) {
    CansatCharts.setMessage(importMessage, error.message, "error");
  }
});

deleteButton.addEventListener("click", async () => {
  const option = selectedDataset();

  if (!option || option.dataset.protected === "1") {
    return;
  }

  if (!confirm(`Delete dataset "${option.textContent}"?`)) {
    return;
  }

  const body = new URLSearchParams({ action: "delete", dataset_id: option.value });
  const response = await fetch("api/datasets.php", { method: "POST", body });
  const data = await response.json();

  if (!data.ok) {
    CansatCharts.setMessage(importMessage, data.error || "Could not delete dataset.", "error");
    return;
  }

  Object.values(charts).forEach((chart) => chart.destroy());
  Object.keys(charts).forEach((key) => delete charts[key]);
  chartContainer.innerHTML = "";
  CansatCharts.renderGpsMap([], savedGpsMap);
  await loadDatasets();
  await loadSelectedDataset();
});

clearImportsButton.addEventListener("click", async () => {
  if (!confirm("Delete every imported/saved dataset? The protected Live dataset will stay.")) {
    return;
  }

  const body = new URLSearchParams({ action: "clear_imports" });
  const response = await fetch("api/maintenance.php", { method: "POST", body });
  const data = await response.json();

  if (!data.ok) {
    CansatCharts.setMessage(importMessage, data.error || "Could not clear saved datasets.", "error");
    return;
  }

  CansatCharts.setMessage(importMessage, data.message || "Saved datasets cleared.", "ok");
  Object.values(charts).forEach((chart) => chart.destroy());
  Object.keys(charts).forEach((key) => delete charts[key]);
  chartContainer.innerHTML = "";
  CansatCharts.renderGpsMap([], savedGpsMap);
  await loadDatasets();
  await loadSelectedDataset();
});

if (rawToggle) {
  rawToggle.addEventListener("change", () => {
    CansatCharts.render(lastRows, chartContainer, charts, importMessage, { showRaw: rawToggle.checked });
  });
}

loadDatasets()
  .then(loadSelectedDataset)
  .catch((error) => CansatCharts.setMessage(importMessage, error.message, "error"));
