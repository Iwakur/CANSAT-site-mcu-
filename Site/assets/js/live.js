const liveCharts = {};
const liveChartContainer = document.getElementById("charts");
const liveMessage = document.getElementById("message");
const liveStats = document.getElementById("liveStats");
const clearButton = document.getElementById("clearLive");
const rawToggle = document.getElementById("rawToggle");
let liveRequestInFlight = false;
let lastRenderedSignature = "";
let lastRenderedRawState = false;
let lastGoodRows = [];
let lastLiveUpdateAt = null;

async function loadLive() {
  if (liveRequestInFlight) {
    return;
  }

  liveRequestInFlight = true;

  try {
    const response = await fetch("api/latest.php?limit=1000", { cache: "no-store" });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Could not load live data.");
    }

    const rows = data.rows || [];
    const meta = data.meta || {};
    const signature = `${meta.row_count || rows.length}:${meta.max_id || (rows.length ? rows[rows.length - 1].id : 0)}`;

    if (rows.length > 0) {
      lastGoodRows = rows;
      lastLiveUpdateAt = new Date();
    }

    CansatCharts.setMessage(liveMessage, rows.length ? `Live dataset: ${rows.length} latest row(s).` : "Waiting for live telemetry.");
    CansatCharts.renderSummary(rows, meta, liveStats);

    const showRaw = Boolean(rawToggle && rawToggle.checked);
    if (signature !== lastRenderedSignature || showRaw !== lastRenderedRawState) {
      CansatCharts.render(rows, liveChartContainer, liveCharts, liveMessage, { showRaw });
      lastRenderedSignature = signature;
      lastRenderedRawState = showRaw;
    }
  } catch (error) {
    if (lastGoodRows.length) {
      CansatCharts.setMessage(liveMessage, `${error.message}. Keeping last ${lastGoodRows.length} row(s) on screen.`, "error");
    } else {
      CansatCharts.setMessage(liveMessage, error.message, "error");
    }
  } finally {
    liveRequestInFlight = false;
  }
}

if (clearButton) {
  clearButton.addEventListener("click", async () => {
    if (!confirm("Clear all rows from the Live dataset?")) {
      return;
    }

    const body = new URLSearchParams({ action: "clear_live" });
    const response = await fetch("api/datasets.php", { method: "POST", body });
    const data = await response.json();

    if (!data.ok) {
      CansatCharts.setMessage(liveMessage, data.error || "Could not clear live data.", "error");
      return;
    }

    Object.values(liveCharts).forEach((chart) => chart.destroy());
    Object.keys(liveCharts).forEach((key) => delete liveCharts[key]);
    liveChartContainer.innerHTML = "";
    liveChartContainer.dataset.ready = "";
    lastRenderedSignature = "";
    lastRenderedRawState = Boolean(rawToggle && rawToggle.checked);
    lastGoodRows = [];
    lastLiveUpdateAt = null;
    loadLive();
  });
}

if (rawToggle) {
  rawToggle.addEventListener("change", () => {
    lastRenderedSignature = "";
    if (lastGoodRows.length) {
      CansatCharts.render(lastGoodRows, liveChartContainer, liveCharts, liveMessage, { showRaw: rawToggle.checked });
      lastRenderedRawState = rawToggle.checked;
    }
  });
}

loadLive();
setInterval(loadLive, 1000);
