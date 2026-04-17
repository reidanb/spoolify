let dashboardData = null;
let charts = {};

const loadingState = document.getElementById("loading-state");
const tabButtons = document.querySelectorAll(".tab-btn");
const tabSections = document.querySelectorAll(".dashboard-tab");
const btnWrapped = document.getElementById("btn-wrapped");
const btnImport = document.getElementById("btn-import");
const headerNarrative = document.getElementById("header-narrative");
const profileBreakdown = document.getElementById("profile-breakdown");

const PROFILE_ORDER = ["afternoon", "evening", "morning", "night"];
const PROFILE_COLORS = {
  afternoon: "#6d28d9",
  evening: "#ec4899",
  morning: "#8b5cf6",
  night: "#c4b5fd",
};

document.addEventListener("DOMContentLoaded", () => {
  initializeTabs();
  setupEventListeners();
  loadDashboard();
});

function initializeTabs() {
  tabButtons.forEach((button) => {
    button.addEventListener("click", () => {
      switchTab(button.dataset.tab);
    });
  });
}

function switchTab(tabName) {
  tabButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });

  tabSections.forEach((section) => {
    section.classList.toggle("active", section.id === `${tabName}-tab`);
  });

  if (tabName === "overview") {
    refreshOverviewCharts();
  }
}

function setupEventListeners() {
  if (btnWrapped) {
    btnWrapped.addEventListener("click", () => {
      window.open("/wrapped", "_blank");
    });
  }

  if (btnImport) {
    btnImport.addEventListener("click", () => {
      window.location.href = "/";
    });
  }
}

async function loadDashboard() {
  try {
    const [summaryRes, monthlyRes, hourlyRes, yearlyRes, topArtistsRes, topTracksRes] = await Promise.all([
      fetch("/dashboard-summary"),
      fetch("/monthly"),
      fetch("/hourly"),
      fetch("/yearly"),
      fetch("/top-artists?limit=25"),
      fetch("/top-tracks?limit=25"),
    ]);

    const responses = [summaryRes, monthlyRes, hourlyRes, yearlyRes, topArtistsRes, topTracksRes];
    const failedResponse = responses.find((response) => !response.ok);
    if (failedResponse) {
      throw new Error(`API error: ${failedResponse.status}`);
    }

    const [summary, monthly, hourly, yearly, topArtists, topTracks] = await Promise.all(
      responses.map((response) => response.json())
    );

    dashboardData = {
      summary: summary.data || summary,
      monthly: monthly.data || [],
      hourly: hourly.data || [],
      yearly: yearly.data || [],
      topArtists: topArtists.data || [],
      topTracks: topTracks.data || [],
    };

    renderOverviewTab();
    showLoading(false);
  } catch (error) {
    console.error("Failed to load dashboard:", error);
    showLoading(false);
    showError("Failed to load dashboard data. Please refresh the page.");
  }
}

function showLoading(show) {
  if (loadingState) {
    loadingState.style.display = show ? "flex" : "none";
  }
}

function showError(message) {
  console.error(message);
  if (headerNarrative) {
    headerNarrative.textContent = message;
  }
}

function renderOverviewTab() {
  if (!dashboardData) {
    return;
  }

  updateNarrative();
  updateMetrics();
  renderProfileBreakdown();
  renderInsights();
  createCharts();
  renderTopArtistsTable();
  renderTopTracksTable();
}

function updateNarrative() {
  if (!headerNarrative) {
    return;
  }

  const summary = dashboardData.summary || {};
  const totals = summary.totals || {};
  const profile = summary.profile || {};
  const peaks = summary.peaks || {};
  const dateRange = totals.date_range || {};
  const startYear = dateRange.start ? new Date(dateRange.start).getFullYear() : null;
  const plays = formatInteger(totals.total_plays || 0);
  const dominantPeriod = formatPeriod(profile.primary).toLowerCase();
  const peakYear = peaks.peak_year ? String(peaks.peak_year) : "your strongest year";

  if (startYear) {
    headerNarrative.textContent = `Since ${startYear}, you've logged ${plays} plays locally - mostly in the ${dominantPeriod}, peaking in ${peakYear}.`;
    return;
  }

  headerNarrative.textContent = `${plays} plays logged locally, with listening centered around the ${dominantPeriod}.`;
}

function updateMetrics() {
  const summary = dashboardData.summary || {};
  const totals = summary.totals || {};
  const profile = summary.profile || {};
  const dateRange = totals.date_range || {};

  setText("metric-plays", formatInteger(totals.total_plays || 0));
  setText("metric-hours", formatInteger(Math.round(totals.total_hours || 0)));
  setText("metric-hours-detail", "hours listened");
  setText("metric-artists", formatInteger(totals.unique_artists || 0));
  setText("metric-tracks", formatInteger(totals.unique_tracks || 0));
  setText("metric-date-range", formatDateRangeValue(dateRange.start, dateRange.end));
  setText("metric-date-range-detail", formatDateRangeDetail(dateRange.start, dateRange.end));
  setText("metric-peak-hour", formatPeakHour(profile.peak_hour));
  setText("metric-primary-period", formatPeriod(profile.primary));
  setText(
    "metric-primary-pct",
    profile.primary_pct ? `${Math.round(profile.primary_pct)}% of listening time` : "No dominant period yet"
  );
}

function renderProfileBreakdown() {
  if (!profileBreakdown) {
    return;
  }

  const bucketPct = dashboardData.summary?.profile?.bucket_pct || {};
  profileBreakdown.innerHTML = "";

  PROFILE_ORDER.forEach((key) => {
    const row = document.createElement("div");
    row.className = "profile-row";
    row.innerHTML = `
      <span class="profile-label">
        <span class="profile-swatch" style="background:${PROFILE_COLORS[key]}"></span>
        ${escapeHtml(formatPeriod(key))}
      </span>
      <span class="profile-value">${Math.round(bucketPct[key] || 0)}%</span>
    `;
    profileBreakdown.appendChild(row);
  });
}

function renderInsights() {
  const container = document.getElementById("insights-container");
  if (!container) {
    return;
  }

  const items = buildNarrativeInsights(dashboardData.summary || {});
  container.innerHTML = "";

  items.forEach((insight) => {
    const card = document.createElement("article");
    card.className = "insight-card";
    card.innerHTML = `
      <div class="insight-kicker">${escapeHtml(insight.kicker)}</div>
      <h4 class="insight-title">${escapeHtml(insight.title)}</h4>
      <p class="insight-body">${escapeHtml(insight.body)}</p>
    `;
    container.appendChild(card);
  });
}

function buildNarrativeInsights(summary) {
  const profile = summary.profile || {};
  const peaks = summary.peaks || {};
  const trends = summary.trends || {};
  const backendInsights = Array.isArray(summary.insights) ? summary.insights : [];
  const items = [];

  if (profile.primary) {
    items.push({
      kicker: "Dominant Behavior",
      title: `${formatPeriod(profile.primary)} listener`,
      body: `${Math.round(profile.primary_pct || 0)}% of your listening time falls in the ${formatPeriod(profile.primary).toLowerCase()}.`,
    });
  }

  if (peaks.peak_year || peaks.peak_month) {
    const peakBody = [];
    if (peaks.peak_year) {
      peakBody.push(`Your biggest year on record was ${peaks.peak_year}.`);
    }
    if (peaks.peak_month) {
      peakBody.push(`${formatMonthLabel(peaks.peak_month)} stands out as your strongest month.`);
    }
    items.push({
      kicker: "Peak",
      title: "High-water mark",
      body: peakBody.join(" "),
    });
  }

  if (trends.segments?.decline) {
    items.push({
      kicker: "Decline",
      title: "A noticeable dip",
      body: `Your archive shows a decline phase during ${trends.segments.decline}.`,
    });
  }

  if (trends.segments?.recovery) {
    items.push({
      kicker: "Recovery",
      title: "Listening picks back up",
      body: `The recovery phase begins in ${trends.segments.recovery}, showing momentum returning after the dip.`,
    });
  }

  for (const insight of backendInsights) {
    if (items.length >= 5) {
      break;
    }
    items.push({
      kicker: "Additional Context",
      title: "Archive note",
      body: insight,
    });
  }

  if (items.length === 0) {
    items.push({
      kicker: "Overview",
      title: "Your archive is ready",
      body: "As more history lands in Spoolify, this space will turn it into a cleaner story.",
    });
  }

  return items.slice(0, 5);
}

function createCharts() {
  createMonthlyChart(dashboardData.monthly || []);
  createHourlyChart(dashboardData.hourly || []);
  createProfileChart();
  createYearlyChart(dashboardData.yearly || []);
  createTopArtistsChart((dashboardData.topArtists || []).slice(0, 10));
  createTopTracksChart((dashboardData.topTracks || []).slice(0, 10));
}

function refreshOverviewCharts() {
  Object.values(charts).forEach((chart) => {
    if (chart && chart.resize) {
      chart.resize();
    }
  });
}

function createMonthlyChart(data) {
  const ctx = document.getElementById("chart-monthly")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.monthly) {
    charts.monthly.destroy();
  }

  charts.monthly = new Chart(ctx, {
    type: "line",
    data: {
      labels: data.map((entry) => entry.month),
      datasets: [{
        label: "Listening time",
        data: data.map((entry) => entry.minutes),
        borderColor: "#6d28d9",
        backgroundColor: "rgba(109, 40, 217, 0.12)",
        borderWidth: 3,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 4,
      }],
    },
    options: baseChartOptions({ xTickLimit: 8, yTitle: "Minutes" }),
  });
}

function createHourlyChart(data) {
  const ctx = document.getElementById("chart-hourly")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.hourly) {
    charts.hourly.destroy();
  }

  charts.hourly = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((entry) => `${String(entry.hour).padStart(2, "0")}:00`),
      datasets: [{
        label: "Plays",
        data: data.map((entry) => entry.plays),
        backgroundColor: "rgba(139, 92, 246, 0.82)",
        borderRadius: 6,
        maxBarThickness: 18,
      }],
    },
    options: baseChartOptions({
      xTickCallback: (_, index) => (index % 3 === 0 ? `${String(index).padStart(2, "0")}:00` : ""),
      yTitle: "Plays",
    }),
  });
}

function createProfileChart() {
  const ctx = document.getElementById("chart-profile")?.getContext("2d");
  if (!ctx) {
    return;
  }

  const bucketPct = dashboardData.summary?.profile?.bucket_pct || {};
  if (charts.profile) {
    charts.profile.destroy();
  }

  charts.profile = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: PROFILE_ORDER.map((key) => formatPeriod(key)),
      datasets: [{
        data: PROFILE_ORDER.map((key) => bucketPct[key] || 0),
        backgroundColor: PROFILE_ORDER.map((key) => PROFILE_COLORS[key]),
        borderColor: "#ffffff",
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
      },
      cutout: "62%",
    },
  });
}

function createYearlyChart(data) {
  const ctx = document.getElementById("chart-yearly")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.yearly) {
    charts.yearly.destroy();
  }

  charts.yearly = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((entry) => entry.year),
      datasets: [{
        label: "Minutes",
        data: data.map((entry) => entry.minutes),
        backgroundColor: "rgba(124, 58, 237, 0.78)",
        borderRadius: 6,
      }],
    },
    options: baseChartOptions({ yTitle: "Minutes" }),
  });
}

function createTopArtistsChart(data) {
  const ctx = document.getElementById("chart-top-artists")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.topArtists) {
    charts.topArtists.destroy();
  }

  charts.topArtists = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((entry) => truncateLabel(entry.name, 24)),
      datasets: [{
        label: "Minutes",
        data: data.map((entry) => Math.round(entry.minutes)),
        backgroundColor: "rgba(109, 40, 217, 0.82)",
        borderRadius: 6,
      }],
    },
    options: horizontalChartOptions(),
  });
}

function createTopTracksChart(data) {
  const ctx = document.getElementById("chart-top-tracks")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.topTracks) {
    charts.topTracks.destroy();
  }

  charts.topTracks = new Chart(ctx, {
    type: "bar",
    data: {
      labels: data.map((entry) => truncateLabel(`${entry.name} - ${entry.artist}`, 34)),
      datasets: [{
        label: "Minutes",
        data: data.map((entry) => Math.round(entry.minutes)),
        backgroundColor: "rgba(139, 92, 246, 0.72)",
        borderRadius: 6,
      }],
    },
    options: horizontalChartOptions(),
  });
}

function renderTopArtistsTable() {
  const tbody = document.getElementById("tbody-artists");
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";
  (dashboardData.topArtists || []).forEach((artist, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="rank">${index + 1}</td>
      <td class="name" title="${escapeAttribute(artist.name)}">${escapeHtml(artist.name)}</td>
      <td class="minutes">${formatInteger(Math.round(artist.minutes))}</td>
    `;
    tbody.appendChild(row);
  });
}

function renderTopTracksTable() {
  const tbody = document.getElementById("tbody-tracks");
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";
  (dashboardData.topTracks || []).forEach((track, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="rank">${index + 1}</td>
      <td class="name" title="${escapeAttribute(track.name)}">${escapeHtml(track.name)}</td>
      <td class="artist" title="${escapeAttribute(track.artist)}">${escapeHtml(track.artist)}</td>
      <td class="minutes">${formatInteger(Math.round(track.minutes))}</td>
    `;
    tbody.appendChild(row);
  });
}

function baseChartOptions({ xTickLimit, xTickCallback, yTitle } = {}) {
  return {
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1f1633",
        titleColor: "#ffffff",
        bodyColor: "#f3e8ff",
        padding: 12,
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        ticks: { color: "#6b7280" },
        grid: { color: "rgba(109, 40, 217, 0.08)" },
        title: yTitle ? { display: true, text: yTitle, color: "#6b7280" } : undefined,
      },
      x: {
        ticks: {
          color: "#6b7280",
          maxTicksLimit: xTickLimit,
          callback: xTickCallback,
        },
        grid: { display: false },
      },
    },
  };
}

function horizontalChartOptions() {
  return {
    indexAxis: "y",
    responsive: true,
    maintainAspectRatio: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1f1633",
        titleColor: "#ffffff",
        bodyColor: "#f3e8ff",
        padding: 12,
      },
    },
    scales: {
      x: {
        beginAtZero: true,
        ticks: { color: "#6b7280" },
        grid: { color: "rgba(109, 40, 217, 0.08)" },
      },
      y: {
        ticks: { color: "#6b7280" },
        grid: { display: false },
      },
    },
  };
}

function formatInteger(value) {
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value || 0);
}

function formatPeriod(value) {
  if (!value) {
    return "Unknown";
  }

  return String(value)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatPeakHour(hour) {
  if (hour === null || hour === undefined || Number.isNaN(Number(hour))) {
    return "-";
  }

  const numericHour = Number(hour);
  const suffix = numericHour >= 12 ? "PM" : "AM";
  const normalized = numericHour % 12 || 12;
  return `${normalized}${suffix} peak`;
}

function formatDateRangeValue(start, end) {
  if (!start || !end) {
    return "-";
  }

  return `${new Date(start).getFullYear()}-${new Date(end).getFullYear()}`;
}

function formatDateRangeDetail(start, end) {
  if (!start || !end) {
    return "No date range available";
  }

  return `${formatShortDate(start)} to ${formatShortDate(end)}`;
}

function formatShortDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    year: "numeric",
  }).format(date);
}

function formatMonthLabel(value) {
  if (!value) {
    return "Unknown month";
  }

  const [year, month] = String(value).split("-");
  const date = new Date(`${year}-${month}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(date);
}

function truncateLabel(value, maxLength) {
  if (!value || value.length <= maxLength) {
    return value;
  }

  return `${value.slice(0, maxLength - 1)}...`;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text ?? "";
  return div.innerHTML;
}

function escapeAttribute(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;");
}
