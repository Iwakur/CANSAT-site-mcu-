const CansatCharts = (() => {
  const groups = [
    {
      id: "temperature",
      title: "Temperature",
      unit: "C",
      series: [["tmp36_temp", "TMP36", "#f6d36d"], ["bme_temp", "BME688", "#6db6ff"]]
    },
    {
      id: "tmp36-voltage",
      title: "TMP36 Voltage",
      raw: true,
      unit: "V",
      series: [["tmp36_voltage", "Voltage", "#6df6c1"]]
    },
    {
      id: "tmp36-raw",
      title: "TMP36 Raw ADC",
      raw: true,
      unit: "raw",
      series: [["tmp36_raw", "ADC", "#c69cff"]]
    },
    {
      id: "pressure",
      title: "Pressure",
      unit: "hPa",
      series: [["bme_pressure", "BME pressure", "#80d27e"]]
    },
    {
      id: "humidity",
      title: "Humidity",
      unit: "%",
      series: [["bme_humidity", "BME humidity", "#6db6ff"]]
    },
    {
      id: "gas",
      title: "Gas Resistance",
      unit: "ohms",
      series: [["bme_gas", "BME gas", "#ffd166"]]
    },
    {
      id: "bme-altitude",
      title: "BME Pressure Altitude",
      unit: "m",
      series: [["bme_altitude", "BME altitude", "#6db6ff"]]
    },
    {
      id: "gps-altitude",
      title: "GPS Altitude",
      unit: "m",
      series: [["gps_altitude", "GPS altitude", "#c69cff"]]
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
      series: [["pitch", "Pitch", "#ff6b6b"], ["roll", "Roll", "#80d27e"]]
    },
    {
      id: "heading",
      title: "Compass Heading",
      unit: "deg",
      series: [["heading", "Heading", "#6db6ff"]]
    },
    {
      id: "magnetometer",
      title: "Magnetometer",
      unit: "raw",
      series: [["mag_x", "X", "#ff6b6b"], ["mag_y", "Y", "#80d27e"], ["mag_z", "Z", "#6db6ff"]]
    },
    {
      id: "gps-latitude",
      title: "GPS Latitude",
      unit: "deg",
      series: [["gps_lat", "Latitude", "#ffd166"]]
    },
    {
      id: "gps-longitude",
      title: "GPS Longitude",
      unit: "deg",
      series: [["gps_lon", "Longitude", "#c69cff"]]
    },
    {
      id: "gps-satellites",
      title: "GPS Satellites",
      raw: true,
      unit: "count",
      series: [["gps_satellites", "Satellites", "#6db6ff"]]
    },
    {
      id: "gps-hdop",
      title: "GPS HDOP",
      raw: true,
      unit: "HDOP",
      series: [["gps_hdop", "HDOP", "#ff9f6d"]]
    },
    {
      id: "gps-speed",
      title: "GPS Speed",
      unit: "km/h",
      series: [["gps_speed_kmh", "Speed", "#6df6c1"]]
    },
    {
      id: "gps-course",
      title: "GPS Course",
      unit: "deg",
      series: [["gps_course_deg", "Course", "#f66d9b"]]
    },
    {
      id: "gps-vertical-speed",
      title: "GPS Vertical Speed",
      unit: "m/s",
      series: [["gps_vertical_speed_ms", "Vertical speed", "#b8f66d"]]
    }
  ];

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

  function shortTime(value) {
    const time = timeOnly(value);
    return time ? time.slice(3, 8) : "";
  }

  function labelFor(row) {
    return shortTime(row.device_time) || shortTime(row.received_at) || String(row.line_number || row.id || "");
  }

  function fullTimeFor(row) {
    return timeOnly(row.device_time) || timeOnly(row.received_at) || "";
  }

  function tooltipTitle(rows, tooltipItems) {
    if (!tooltipItems.length) {
      return "";
    }

    const row = rows[tooltipItems[0].dataIndex] || {};
    const parts = [];
    const time = fullTimeFor(row) || labelFor(row);

    if (time) {
      parts.push(time);
    }
    if (row.mcu_sample_id !== null && row.mcu_sample_id !== undefined) {
      parts.push(`SID ${row.mcu_sample_id}`);
    }

    return parts.join(" | ");
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

  function lastValue(rows, key) {
    for (let index = rows.length - 1; index >= 0; index -= 1) {
      const value = rows[index][key];
      if (value !== null && value !== undefined && value !== "") {
        return value;
      }
    }

    return null;
  }

  function formatNumber(value, digits = 1) {
    const number = Number(value);
    if (!Number.isFinite(number)) {
      return "--";
    }

    return number.toLocaleString(undefined, {
      maximumFractionDigits: digits
    });
  }

  function decimalsForUnit(unit) {
    if (unit === "raw" || unit === "count") {
      return 0;
    }
    if (unit === "deg") {
      return 2;
    }
    return 1;
  }

  function statsForSeries(rows, key) {
    const values = rows
      .map((row) => numericValue(row, key))
      .filter((value) => value !== null);

    if (!values.length) {
      return null;
    }

    const sum = values.reduce((total, value) => total + value, 0);
    return {
      min: Math.min(...values),
      max: Math.max(...values),
      avg: sum / values.length
    };
  }

  function renderChartStats(block, rows, activeSeries, group) {
    let stats = block.querySelector(".chart-stats");
    if (!stats) {
      stats = document.createElement("div");
      stats.className = "chart-stats";
      const meta = block.querySelector(".chart-meta");
      if (meta) {
        meta.appendChild(stats);
      } else {
        block.appendChild(stats);
      }
    }

    const digits = decimalsForUnit(group.unit);
    stats.innerHTML = "";

    activeSeries.forEach(([key, label, color]) => {
      const values = statsForSeries(rows, key);
      if (!values) {
        return;
      }

      const item = document.createElement("div");
      item.className = "chart-stat-row";
      item.style.setProperty("--series-color", color);

      const name = document.createElement("span");
      name.className = "chart-stat-name";
      name.textContent = label;

      const min = document.createElement("span");
      min.className = "chart-stat-values";
      min.textContent = `min ${formatNumber(values.min, digits)}`;

      const max = document.createElement("span");
      max.className = "chart-stat-values";
      max.textContent = `max ${formatNumber(values.max, digits)}`;

      const avg = document.createElement("span");
      avg.className = "chart-stat-values";
      avg.textContent = `avg ${formatNumber(values.avg, digits)}`;

      item.append(name, min, max, avg);
      stats.appendChild(item);
    });
  }

  function sampleStats(rows) {
    const ids = [];
    let previous = null;

    rows.forEach((row) => {
      if (Number(row.parse_ok) === 0) {
        return;
      }

      const current = numericValue(row, "mcu_sample_id");
      if (current === null || current < 0 || current !== Math.floor(current)) {
        return;
      }

      if (previous === null || current !== previous) {
        ids.push(current);
        previous = current;
      }
    });

    if (ids.length < 2) {
      return { received: ids.length, missing: 0, percent: 0 };
    }

    let missing = 0;
    previous = ids[0];

    ids.slice(1).forEach((current) => {
      const gap = current - previous;
      if (gap > 1) {
        missing += gap - 1;
      }

      previous = current;
    });

    const denominator = ids.length + missing;
    return {
      received: ids.length,
      missing,
      percent: denominator ? (missing / denominator) * 100 : 0
    };
  }

  function buildSummary(rows, meta = {}) {
    const last = rows.length ? rows[rows.length - 1] : {};
    const samples = sampleStats(rows);
    const parseErrors = rows.filter((row) => Number(row.parse_ok) === 0).length;
    const gasValid = lastValue(rows, "bme_gas_valid");
    const gpsFix = lastValue(rows, "gps_fix");
    const satellites = lastValue(rows, "gps_satellites");
    const gpsRow = rows.slice().reverse().find((row) => (
      Number(row.gps_fix) && numericValue(row, "gps_lat") !== null && numericValue(row, "gps_lon") !== null
    ));
    const gpsLat = gpsRow ? numericValue(gpsRow, "gps_lat") : null;
    const gpsLon = gpsRow ? numericValue(gpsRow, "gps_lon") : null;
    const location = gpsLat === null || gpsLon === null ? "--" : {
      text: `${formatNumber(gpsLat, 6)}, ${formatNumber(gpsLon, 6)}`,
      href: `https://www.google.com/maps?q=${gpsLat},${gpsLon}`
    };

    return [
      ["Last received", timeOnly(meta.last_received_at || last.received_at) || "--"],
      ["Device time", timeOnly(last.device_time) || "--"],
      ["Last sample", last.mcu_sample_id ?? "--"],
      ["Rows shown", rows.length.toLocaleString()],
      ["Rows in DB", Number(meta.row_count || rows.length).toLocaleString()],
      ["Samples shown", samples.received.toLocaleString()],
      ["Missing sample IDs", samples.missing.toLocaleString()],
      ["Sample gap est.", `${formatNumber(samples.percent, 2)}%`],
      ["GPS fix", gpsFix === null ? "--" : (Number(gpsFix) ? "Yes" : "No")],
      ["Satellites", satellites === null ? "--" : formatNumber(satellites, 0)],
      ["Last location", location],
      ["Gas valid", gasValid === null ? "--" : (Number(gasValid) ? "Yes" : "No")],
      ["Parse errors", parseErrors.toLocaleString()]
    ];
  }

  function renderSummary(rows, meta, element) {
    if (!element) {
      return;
    }

    const safeRows = rows || [];
    element.className = "telemetry-summary";
    element.innerHTML = "";

    buildSummary(safeRows, meta || {}).forEach(([label, value]) => {
      const item = document.createElement("span");
      item.className = "summary-item";

      const labelElement = document.createElement("span");
      labelElement.className = "summary-label";
      labelElement.textContent = label;

      const valueElement = document.createElement("strong");
      if (value && typeof value === "object") {
        const link = document.createElement("a");
        link.href = value.href;
        link.target = "_blank";
        link.rel = "noopener";
        link.textContent = value.text;
        valueElement.appendChild(link);
      } else {
        valueElement.textContent = value;
      }

      item.append(labelElement, valueElement);
      element.appendChild(item);
    });
  }

  function gpsPoints(rows) {
    return (rows || [])
      .map((row) => ({
        lat: numericValue(row, "gps_lat"),
        lon: numericValue(row, "gps_lon"),
        fix: Number(row.gps_fix)
      }))
      .filter((point) => point.fix && point.lat !== null && point.lon !== null);
  }

  function renderGpsMap(rows, canvas, options = {}) {
    if (!canvas) {
      return;
    }

    const ctx = canvas.getContext("2d");
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.floor(rect.width || canvas.clientWidth || 640));
    const height = Math.max(1, Math.floor(rect.height || canvas.clientHeight || 280));
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    ctx.fillStyle = "#07090e";
    ctx.fillRect(0, 0, width, height);
    ctx.strokeStyle = "rgba(109, 182, 255, 0.22)";
    ctx.lineWidth = 1;
    for (let x = 0; x <= width; x += 48) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = 0; y <= height; y += 48) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    ctx.strokeStyle = "rgba(246, 211, 109, 0.35)";
    ctx.beginPath();
    ctx.moveTo(width / 2 - 8, height / 2);
    ctx.lineTo(width / 2 + 8, height / 2);
    ctx.moveTo(width / 2, height / 2 - 8);
    ctx.lineTo(width / 2, height / 2 + 8);
    ctx.stroke();

    const points = gpsPoints(rows);
    if (!points.length) {
      ctx.fillStyle = "#98a4b3";
      ctx.font = "13px system-ui, sans-serif";
      ctx.fillText("GPS map - waiting for fix", 16, 28);
      return;
    }

    const latValues = points.map((point) => point.lat);
    const lonValues = points.map((point) => point.lon);
    let minLat = Math.min(...latValues);
    let maxLat = Math.max(...latValues);
    let minLon = Math.min(...lonValues);
    let maxLon = Math.max(...lonValues);
    if (minLat === maxLat) {
      minLat -= 0.00001;
      maxLat += 0.00001;
    }
    if (minLon === maxLon) {
      minLon -= 0.00001;
      maxLon += 0.00001;
    }

    const pad = 26;
    const mapPoint = (point) => ({
      x: pad + ((point.lon - minLon) / (maxLon - minLon)) * (width - pad * 2),
      y: height - pad - ((point.lat - minLat) / (maxLat - minLat)) * (height - pad * 2)
    });

    if (options.trace !== false && points.length > 1) {
      ctx.strokeStyle = "#6db6ff";
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach((point, index) => {
        const mapped = mapPoint(point);
        if (index === 0) {
          ctx.moveTo(mapped.x, mapped.y);
        } else {
          ctx.lineTo(mapped.x, mapped.y);
        }
      });
      ctx.stroke();
    }

    const current = options.currentRow ? gpsPoints([options.currentRow])[0] : points[points.length - 1];
    if (current) {
      const mapped = mapPoint(current);
      ctx.fillStyle = "#f6d36d";
      ctx.strokeStyle = "rgba(246, 211, 109, 0.35)";
      ctx.lineWidth = 8;
      ctx.beginPath();
      ctx.arc(mapped.x, mapped.y, 6, 0, Math.PI * 2);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(mapped.x, mapped.y, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    const last = current || points[points.length - 1];
    ctx.fillStyle = "#dbe6f3";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(`${formatNumber(last.lat, 6)}, ${formatNumber(last.lon, 6)}`, 16, 28);
    ctx.fillStyle = "#98a4b3";
    ctx.fillText(`${points.length} GPS point${points.length === 1 ? "" : "s"}`, 16, 46);
  }

  function setMessage(element, text, type = "") {
    if (!element) {
      return;
    }

    element.textContent = text;
    element.className = `message ${type}`.trim();
  }

  function render(rows, container, charts, messageElement, options = {}) {
    if (!window.Chart) {
      setMessage(messageElement, "Chart.js is not loaded. Add Site/assets/vendor/chart.umd.min.js for offline use.", "error");
      return;
    }

    container.dataset.ready = "1";

    const labels = rows.map(labelFor);
    let rendered = 0;
    const showRaw = Boolean(options.showRaw);

    groups.forEach((group) => {
      if (group.raw && !showRaw) {
        const existing = charts[group.id];
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
      let block = document.getElementById(`chart-${group.id}`);

      if (!canvas) {
        block = document.createElement("section");
        block.className = "chart-block";
        block.id = `chart-${group.id}`;

        const title = document.createElement("h2");
        title.textContent = group.title;

        const unit = document.createElement("span");
        unit.className = "chart-unit";
        unit.textContent = group.unit || "value";

        const meta = document.createElement("div");
        meta.className = "chart-meta";
        meta.appendChild(unit);

        canvas = document.createElement("canvas");
        canvas.id = `chart-${group.id}-canvas`;

        block.append(title, meta, canvas);
        container.appendChild(block);
      }

      renderChartStats(block, rows, activeSeries, group);

      const datasets = activeSeries.map(([key, label, color]) => ({
        label,
        data: rows.map((row) => numericValue(row, key)),
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2,
        pointRadius: 1.5,
        pointHoverRadius: 4,
        tension: 0,
        spanGaps: true
      }));

      if (existing) {
        existing.data.labels = labels;
        existing.data.datasets = datasets;
        existing.options.plugins.tooltip.callbacks.title = (items) => tooltipTitle(rows, items);
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
                boxHeight: 10,
                boxWidth: 22,
                color: "#edf2f7"
              }
            },
            tooltip: {
              callbacks: {
                title: (items) => tooltipTitle(rows, items)
              }
            }
          },
          scales: {
            x: {
              ticks: { color: "#98a4b3", maxRotation: 0, maxTicksLimit: 10 },
              grid: { color: "rgba(48, 56, 70, 0.64)" },
              title: { display: true, text: "Time", color: "#98a4b3" }
            },
            y: {
              ticks: { color: "#98a4b3" },
              grid: { color: "rgba(48, 56, 70, 0.72)" },
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

  return { render, renderSummary, renderGpsMap, setMessage, timeOnly, shortTime };
})();
