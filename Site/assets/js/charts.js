const CansatCharts = (() => {
  const groups = [
    {
      id: "temperature",
      title: "Temperature Sensors",
      unit: "C",
      series: [["tmp36_temp", "TMP36 temp", "#f6d36d"], ["bme_temp", "BME temp", "#6db6ff"]]
    },
    {
      id: "pressure",
      title: "Pressure",
      unit: "hPa",
      series: [["bme_pressure", "BME pressure", "#80d27e"]]
    },
    {
      id: "altitude",
      title: "Altitude",
      unit: "m",
      series: [["bme_altitude", "BME altitude", "#6db6ff"], ["gps_altitude", "GPS altitude", "#c69cff"]]
    },
    {
      id: "air",
      title: "Humidity and Gas",
      unit: "",
      series: [["bme_humidity", "Humidity %", "#6db6ff"], ["bme_gas", "Gas ohms", "#ffd166"]]
    },
    {
      id: "acceleration",
      title: "Acceleration",
      unit: "g",
      series: [["ax", "Ax", "#ff6b6b"], ["ay", "Ay", "#80d27e"], ["az", "Az", "#6db6ff"]]
    },
    {
      id: "gyro",
      title: "Gyroscope",
      unit: "dps",
      series: [["gx", "Gx", "#ff6b6b"], ["gy", "Gy", "#80d27e"], ["gz", "Gz", "#6db6ff"]]
    },
    {
      id: "orientation",
      title: "Orientation",
      unit: "deg",
      series: [["pitch", "Pitch", "#ff6b6b"], ["roll", "Roll", "#80d27e"], ["heading", "Heading", "#6db6ff"]]
    },
    {
      id: "magnetometer",
      title: "Magnetometer",
      unit: "",
      series: [["mag_x", "X", "#ff6b6b"], ["mag_y", "Y", "#80d27e"], ["mag_z", "Z", "#6db6ff"]]
    },
    {
      id: "gps",
      title: "GPS",
      unit: "",
      series: [["gps_fix", "Fix", "#80d27e"], ["gps_satellites", "Satellites", "#6db6ff"], ["gps_lat", "Latitude", "#ffd166"], ["gps_lon", "Longitude", "#c69cff"]]
    }
  ];

  function labelFor(row) {
    if (row.device_time) {
      return row.device_time;
    }

    if (row.received_at) {
      return String(row.received_at).slice(11, 19);
    }

    return String(row.line_number || row.id || "");
  }

  function numericValue(row, key) {
    if (row[key] === null || row[key] === undefined || row[key] === "") {
      return null;
    }

    const value = Number(row[key]);
    return Number.isFinite(value) ? value : null;
  }

  function hasValues(rows, key) {
    return rows.some((row) => numericValue(row, key) !== null);
  }

  function setMessage(element, text, type = "") {
    if (!element) {
      return;
    }

    element.textContent = text;
    element.className = `message ${type}`.trim();
  }

  function render(rows, container, charts, messageElement) {
    if (!window.Chart) {
      setMessage(messageElement, "Chart.js is not loaded. Add Site/assets/vendor/chart.umd.min.js for offline use.", "error");
      return;
    }

    container.dataset.ready = "1";

    const labels = rows.map(labelFor);
    let rendered = 0;

    groups.forEach((group) => {
      const activeSeries = group.series.filter(([key]) => hasValues(rows, key));
      const existing = charts[group.id];

      if (activeSeries.length === 0) {
        if (existing) {
          existing.destroy();
          delete charts[group.id];
        }

        const oldBlock = document.getElementById(`chart-${group.id}`);
        if (oldBlock) {
          oldBlock.remove();
        }
        return;
      }

      rendered += 1;
      let canvas = document.getElementById(`chart-${group.id}-canvas`);

      if (!canvas) {
        const block = document.createElement("section");
        block.className = "chart-block";
        block.id = `chart-${group.id}`;

        const title = document.createElement("h2");
        title.textContent = group.title;

        canvas = document.createElement("canvas");
        canvas.id = `chart-${group.id}-canvas`;

        block.append(title, canvas);
        container.appendChild(block);
      }

      const datasets = activeSeries.map(([key, label, color]) => ({
        label,
        data: rows.map((row) => numericValue(row, key)),
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.2,
        spanGaps: true
      }));

      if (existing) {
        existing.data.labels = labels;
        existing.data.datasets = datasets;
        existing.update("none");
        return;
      }

      charts[group.id] = new Chart(canvas, {
        type: "line",
        data: { labels, datasets },
        options: {
          animation: false,
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            intersect: false,
            mode: "index"
          },
          plugins: {
            legend: {
              labels: {
                color: "#edf2f7"
              }
            }
          },
          scales: {
            x: {
              ticks: { color: "#98a4b3", maxTicksLimit: 12 },
              grid: { color: "#303846" },
              title: { display: true, text: "Time", color: "#98a4b3" }
            },
            y: {
              ticks: { color: "#98a4b3" },
              grid: { color: "#303846" },
              title: { display: Boolean(group.unit), text: group.unit, color: "#98a4b3" }
            }
          }
        }
      });
    });

    if (rows.length === 0) {
      setMessage(messageElement, "No telemetry rows for this dataset yet.");
    } else if (rendered === 0) {
      setMessage(messageElement, "Rows exist, but no numeric telemetry fields could be graphed.", "error");
    }
  }

  return { render, setMessage };
})();
