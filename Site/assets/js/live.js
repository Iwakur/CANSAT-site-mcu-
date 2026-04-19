const liveCharts = {};
const liveChartContainer = document.getElementById("charts");
const liveMessage = document.getElementById("message");
const liveStats = document.getElementById("liveStats");
const clearButton = document.getElementById("clearLive");
let liveRequestInFlight = false;
let lastRenderedSignature = "";
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
    liveStats.textContent = rows.length
      ? `Rows in DB: ${meta.row_count || rows.length} | Last received: ${meta.last_received_at || rows[rows.length - 1].received_at}${lastLiveUpdateAt ? ` | Updated: ${lastLiveUpdateAt.toLocaleTimeString()}` : ""}`
      : "No rows received yet.";

    if (signature !== lastRenderedSignature) {
      CansatCharts.render(rows, liveChartContainer, liveCharts, liveMessage);
      lastRenderedSignature = signature;
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
    lastGoodRows = [];
    lastLiveUpdateAt = null;
    loadLive();
  });
}

loadLive();
setInterval(loadLive, 1000);
