let dashboardData = null;
let charts = {};
let filteredData = null;

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

  // Theme toggle listener
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    // Initialize theme from localStorage or system preference
    initializeTheme();
    
    themeToggle.addEventListener("click", () => {
      toggleTheme();
    });
  }

  // Date range slider listeners
  const sliderStart = document.getElementById("date-range-slider-start");
  const sliderEnd = document.getElementById("date-range-slider-end");
  const updateBtn = document.getElementById("update-date-filter");
  const resetBtn = document.getElementById("reset-date-filter");

  if (sliderStart && sliderEnd && updateBtn) {
    // Track the current applied state
    let appliedStart = Number(sliderStart.value);
    let appliedEnd = Number(sliderEnd.value);

    const checkForChanges = () => {
      const currentStart = Number(sliderStart.value);
      const currentEnd = Number(sliderEnd.value);
      
      // Show update button if values differ from applied state
      if (currentStart !== appliedStart || currentEnd !== appliedEnd) {
        updateBtn.style.display = "block";
      } else {
        updateBtn.style.display = "none";
      }
      
      // Always update labels for preview
      updateDateRangeLabels();
      updateDateRangeFill();
    };

    sliderStart.addEventListener("input", () => {
      if (Number(sliderStart.value) > Number(sliderEnd.value)) {
        sliderStart.value = sliderEnd.value;
      }
      checkForChanges();
    });

    sliderEnd.addEventListener("input", () => {
      if (Number(sliderEnd.value) < Number(sliderStart.value)) {
        sliderEnd.value = sliderStart.value;
      }
      checkForChanges();
    });

    // Apply filter on button click
    updateBtn.addEventListener("click", async () => {
      appliedStart = Number(sliderStart.value);
      appliedEnd = Number(sliderEnd.value);
      await updateDateRangeFilter();
      updateBtn.style.display = "none";
    });

    // Reset filter
    if (resetBtn) {
      resetBtn.addEventListener("click", () => {
        const monthCount = dashboardData?.monthly?.length || 100;
        sliderStart.value = 0;
        sliderEnd.value = monthCount - 1;
        appliedStart = 0;
        appliedEnd = monthCount - 1;
        updateBtn.style.display = "none";
        updateDateRangeLabels();
        updateDateRangeFill();

        filteredData = null;
        updateOverviewContent();
      });
    }
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

    filteredData = null;
    initializeDateRangeSlider();
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

  updateOverviewContent();
}

function getActiveOverviewData() {
  return filteredData || dashboardData;
}

function updateOverviewContent() {
  const overview = getActiveOverviewData();
  if (!overview) {
    return;
  }

  updateNarrative(overview.summary || {});
  updateMetrics(overview.summary || {});
  renderProfileBreakdown(overview.summary?.profile || {});
  renderInsights(overview.summary || {});
  updateOverviewCharts(overview);
  renderTopArtistsTable(overview.topArtists || []);
  renderTopTracksTable(overview.topTracks || []);
}

function updateNarrative(summary) {
  if (!headerNarrative) {
    return;
  }

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

function updateMetrics(summary) {
  const activeSummary = summary || getActiveOverviewData()?.summary || {};
  const totals = activeSummary.totals || {};
  const profile = activeSummary.profile || {};
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

function renderProfileBreakdown(profile) {
  if (!profileBreakdown) {
    return;
  }

  const bucketPct = profile?.bucket_pct || {};
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

function renderInsights(summary) {
  const container = document.getElementById("insights-container");
  if (!container) {
    return;
  }

  const items = buildNarrativeInsights(summary || {});
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

function createMonthlyChart(data) {
  const ctx = document.getElementById("chart-monthly")?.getContext("2d");
  if (!ctx) {
    return;
  }

  if (charts.monthly) {
    charts.monthly.destroy();
  }

  // Format month labels as "Mon YY" (e.g., "Jan '20", "Feb '20")
  const formattedLabels = data.map((entry) => {
    try {
      const date = new Date(entry.month + "-01");
      return new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(date);
    } catch {
      return entry.month;
    }
  });

  // Custom x-axis callback to show month labels at regular intervals
  const xTickCallback = (value) => {
    const idx = Number(value);
    if (idx >= 0 && idx < formattedLabels.length) {
      return formattedLabels[idx];
    }
    return "";
  };

  const monthlyOptions = baseChartOptions({ xTickLimit: 12, xTickCallback, yTitle: "Minutes" });
  monthlyOptions.interaction = { mode: "index", intersect: false };
  monthlyOptions.plugins = monthlyOptions.plugins || {};
  monthlyOptions.plugins.tooltip = {
    ...(monthlyOptions.plugins.tooltip || {}),
    intersect: false,
    callbacks: {
      title: (items) => items?.[0]?.label || "",
      label: (context) => `${formatInteger(Math.round(context.parsed?.y || 0))} minutes`,
    },
  };

  charts.monthly = new Chart(ctx, {
    type: "line",
    data: {
      labels: formattedLabels,
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
    options: monthlyOptions,
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

function createProfileChart(profile) {
  const ctx = document.getElementById("chart-profile")?.getContext("2d");
  if (!ctx) {
    return;
  }

  const bucketPct = profile?.bucket_pct || {};
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

function renderTopArtistsTable(data) {
  const tbody = document.getElementById("tbody-artists");
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";
  (data || []).forEach((artist, index) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td class="rank">${index + 1}</td>
      <td class="name" title="${escapeAttribute(artist.name)}">${escapeHtml(artist.name)}</td>
      <td class="minutes">${formatInteger(Math.round(artist.minutes))}</td>
    `;
    tbody.appendChild(row);
  });
}

function renderTopTracksTable(data) {
  const tbody = document.getElementById("tbody-tracks");
  if (!tbody) {
    return;
  }

  tbody.innerHTML = "";
  (data || []).forEach((track, index) => {
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

function initializeDateRangeSlider() {
  if (!dashboardData || !dashboardData.monthly || dashboardData.monthly.length === 0) {
    return;
  }

  const sliderStart = document.getElementById("date-range-slider-start");
  const sliderEnd = document.getElementById("date-range-slider-end");

  if (!sliderStart || !sliderEnd) {
    return;
  }

  // Initialize slider to full range
  sliderStart.max = dashboardData.monthly.length - 1;
  sliderEnd.max = dashboardData.monthly.length - 1;
  sliderEnd.value = dashboardData.monthly.length - 1;

  updateDateRangeLabels();
  updateDateRangeFill();
}

function updateDateRangeFill() {
  if (!dashboardData || !dashboardData.monthly) {
    return;
  }

  const fill = document.querySelector(".date-range-fill");
  const sliderStart = document.getElementById("date-range-slider-start");
  const sliderEnd = document.getElementById("date-range-slider-end");

  if (!fill || !sliderStart || !sliderEnd) {
    return;
  }

  const startIdx = Number(sliderStart.value);
  const endIdx = Number(sliderEnd.value);

  // Update fill position
  const fillStart = (startIdx / dashboardData.monthly.length) * 100;
  const fillEnd = ((endIdx + 1) / dashboardData.monthly.length) * 100;
  fill.style.left = fillStart + "%";
  fill.style.right = (100 - fillEnd) + "%";
}

async function updateDateRangeFilter() {
  if (!dashboardData || !dashboardData.monthly) {
    return;
  }

  const sliderStart = document.getElementById("date-range-slider-start");
  const sliderEnd = document.getElementById("date-range-slider-end");
  const updateBtn = document.getElementById("update-date-filter");
  const resetBtn = document.getElementById("reset-date-filter");

  if (!sliderStart || !sliderEnd) {
    return;
  }

  const startIdx = Number(sliderStart.value);
  const endIdx = Number(sliderEnd.value);

  // Get month values
  const startMonth = dashboardData.monthly[startIdx]?.month;
  const endMonth = dashboardData.monthly[endIdx]?.month;

  // Disable controls while loading
  sliderStart.disabled = true;
  sliderEnd.disabled = true;
  if (updateBtn) updateBtn.disabled = true;
  if (resetBtn) resetBtn.disabled = true;

  // Fetch filtered data from API
  try {
    filteredData = await fetchFilteredDashboardData(startMonth, endMonth);
    updateOverviewContent();
  } catch (error) {
    console.error("Failed to fetch filtered data:", error);
    showError("Failed to load filtered data");
  } finally {
    // Re-enable slider and button
    sliderStart.disabled = false;
    sliderEnd.disabled = false;
    if (updateBtn) updateBtn.disabled = false;
    if (resetBtn) resetBtn.disabled = false;
  }
}

async function fetchFilteredDashboardData(startMonth, endMonth) {
  const params = new URLSearchParams();
  if (startMonth) params.append("start", startMonth);
  if (endMonth) params.append("end", endMonth);

  const response = await fetch(`/dashboard-summary-filtered?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }

  const payload = (await response.json()).data || {};

  // Backward-compatibility for a still-running older API process that only
  // returns the filtered summary shape without filtered chart/table payloads.
  if (payload.totals || payload.profile) {
    const startIdx = dashboardData?.monthly?.findIndex((entry) => entry.month === startMonth) ?? -1;
    const endIdx = dashboardData?.monthly?.findIndex((entry) => entry.month === endMonth) ?? -1;
    const hasValidSlice = startIdx >= 0 && endIdx >= startIdx;

    return {
      summary: payload,
      monthly: hasValidSlice ? dashboardData.monthly.slice(startIdx, endIdx + 1) : (dashboardData?.monthly || []),
      hourly: dashboardData?.hourly || [],
      yearly: dashboardData?.yearly || [],
      topArtists: dashboardData?.topArtists || [],
      topTracks: dashboardData?.topTracks || [],
    };
  }

  return {
    summary: payload.summary || {},
    monthly: payload.monthly || [],
    hourly: payload.hourly || [],
    yearly: payload.yearly || [],
    topArtists: payload.top_artists || [],
    topTracks: payload.top_tracks || [],
  };
}

function updateDateRangeLabels() {
  const startLabel = document.getElementById("date-range-start-label");
  const endLabel = document.getElementById("date-range-end-label");

  if (!dashboardData || !dashboardData.monthly || !startLabel || !endLabel) {
    return;
  }

  const sliderStart = document.getElementById("date-range-slider-start");
  const sliderEnd = document.getElementById("date-range-slider-end");

  if (!sliderStart || !sliderEnd) {
    return;
  }

  const startIdx = Number(sliderStart.value);
  const endIdx = Number(sliderEnd.value);

  const startMonth = dashboardData.monthly[startIdx]?.month;
  const endMonth = dashboardData.monthly[endIdx]?.month;

  if (startMonth) {
    const startDate = new Date(startMonth + "-01");
    startLabel.textContent = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(startDate);
  }

  if (endMonth) {
    const endDate = new Date(endMonth + "-01");
    endLabel.textContent = new Intl.DateTimeFormat("en-US", { month: "short", year: "numeric" }).format(endDate);
  }
}

function updateOverviewCharts(overview) {
  const data = overview || getActiveOverviewData();
  createMonthlyChart(data.monthly || []);
  createHourlyChart(data.hourly || []);
  createYearlyChart(data.yearly || []);
  createProfileChart(data.summary?.profile || {});
  createTopArtistsChart((data.topArtists || []).slice(0, 10));
  createTopTracksChart((data.topTracks || []).slice(0, 10));
}

function refreshOverviewCharts() {
  Object.values(charts).forEach((chart) => {
    if (chart && chart.resize) {
      chart.resize();
    }
  });
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

// Theme Toggle Functions
function initializeTheme() {
  const savedTheme = localStorage.getItem("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  const isDark = savedTheme ? savedTheme === "dark" : prefersDark;

  if (isDark) {
    document.body.classList.add("dark-mode");
    updateThemeToggleButton(true);
  } else {
    document.body.classList.remove("dark-mode");
    updateThemeToggleButton(false);
  }
}

function toggleTheme() {
  const isDark = document.body.classList.contains("dark-mode");
  
  if (isDark) {
    document.body.classList.remove("dark-mode");
    localStorage.setItem("theme", "light");
    updateThemeToggleButton(false);
  } else {
    document.body.classList.add("dark-mode");
    localStorage.setItem("theme", "dark");
    updateThemeToggleButton(true);
  }
}

function updateThemeToggleButton(isDark) {
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.textContent = isDark ? "☀️" : "🌙";
    themeToggle.title = isDark ? "Switch to light mode" : "Switch to dark mode";
  }
}
