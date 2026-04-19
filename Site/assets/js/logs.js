const logOutput = document.getElementById("logOutput");
const logMessage = document.getElementById("message");
const searchInput = document.getElementById("search");
const refreshButton = document.getElementById("refreshLogs");
const clearLogsButton = document.getElementById("clearLogs");

async function loadLogs() {
  try {
    const query = new URLSearchParams({
      limit: "2000",
      q: searchInput.value.trim()
    });
    const response = await fetch(`api/logs.php?${query.toString()}`, { cache: "no-store" });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Could not load logs.");
    }

    const logs = data.logs || [];
    logMessage.className = "message";
    logMessage.textContent = logs.length ? `Showing ${logs.length} log line(s), newest first.` : "No logs found.";
    logOutput.textContent = logs.map((row) => `${row.received_at} [${row.source}] ${row.raw_line}`).join("\n");
  } catch (error) {
    logMessage.textContent = error.message;
    logMessage.className = "message error";
  }
}

refreshButton.addEventListener("click", loadLogs);
clearLogsButton.addEventListener("click", async () => {
  if (!confirm("Clear all ground-station logs?")) {
    return;
  }

  try {
    const body = new URLSearchParams({ action: "clear_logs" });
    const response = await fetch("api/maintenance.php", { method: "POST", body });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Could not clear logs.");
    }

    logMessage.textContent = data.message || "Logs cleared.";
    logMessage.className = "message ok";
    await loadLogs();
  } catch (error) {
    logMessage.textContent = error.message;
    logMessage.className = "message error";
  }
});
searchInput.addEventListener("input", () => {
  clearTimeout(searchInput.searchTimer);
  searchInput.searchTimer = setTimeout(loadLogs, 250);
});

loadLogs();
setInterval(loadLogs, 3000);
