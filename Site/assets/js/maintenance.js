const maintenanceMessage = document.getElementById("maintenanceMessage");
const maintenanceButtons = document.querySelectorAll("[data-maintenance-action]");

const maintenanceLabels = {
  clear_logs: "Clear all ground-station logs?",
  clear_live: "Clear all rows from the Live dataset?",
  clear_imports: "Delete every imported/saved dataset?",
  renew_database: "Renew the database by clearing logs, live telemetry, and imported datasets?"
};

function setMaintenanceMessage(text, state = "") {
  if (!maintenanceMessage) {
    return;
  }

  maintenanceMessage.textContent = text;
  maintenanceMessage.className = `message ${state}`.trim();
}

async function runMaintenance(action) {
  const question = maintenanceLabels[action] || "Run this maintenance action?";

  if (!confirm(question)) {
    return;
  }

  setMaintenanceMessage("Working...");
  maintenanceButtons.forEach((button) => {
    button.disabled = true;
  });

  try {
    const body = new URLSearchParams({ action });
    const response = await fetch("api/maintenance.php", { method: "POST", body });
    const data = await response.json();

    if (!data.ok) {
      throw new Error(data.error || "Maintenance action failed.");
    }

    setMaintenanceMessage(data.message || "Done.", "ok");
  } catch (error) {
    setMaintenanceMessage(error.message, "error");
  } finally {
    maintenanceButtons.forEach((button) => {
      button.disabled = false;
    });
  }
}

maintenanceButtons.forEach((button) => {
  button.addEventListener("click", () => runMaintenance(button.dataset.maintenanceAction));
});
