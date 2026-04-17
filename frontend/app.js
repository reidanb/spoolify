const startBtn = document.getElementById("start-btn");
const restartBtn = document.getElementById("restart-btn");
const stepTwoBackBtn = document.getElementById("to-step-1");
const stepThreeBackBtn = document.getElementById("to-step-2");
const stepFourBackBtn = document.getElementById("to-step-3b");
const stepTwoContinueBtn = document.getElementById("to-step-3");
const reviewImportBtn = document.getElementById("to-step-4");
const validateZipBtn = document.getElementById("validate-zip-btn");
const importZipBtn = document.getElementById("import-zip-btn");

const steps = Array.from(document.querySelectorAll("[data-step]"));
const indicators = Array.from(document.querySelectorAll("[data-step-indicator]"));

const zipInput = document.getElementById("archive-zip");
const zipSelected = document.getElementById("zip-selected");
const validationStatus = document.getElementById("validation-status");
const validationPill = document.getElementById("validation-pill");
const validationTitle = document.getElementById("validation-title");
const validationMessage = document.getElementById("validation-message");
const validationResults = document.getElementById("validation-results");
const validationDetails = document.getElementById("validation-details");
const validationTechnical = document.getElementById("validation-technical");
const importStatus = document.getElementById("import-status");
const importPill = document.getElementById("import-pill");
const importTitle = document.getElementById("import-title");
const importMessage = document.getElementById("import-message");
const importResults = document.getElementById("import-results");
const importDetails = document.getElementById("import-details");
const importTechnical = document.getElementById("import-technical");
const doneMessage = document.getElementById("done-message");
const doneStatus = document.getElementById("done-status");
const donePill = document.getElementById("done-pill");
const doneTitle = document.getElementById("done-title");
const doneStatusMessage = document.getElementById("done-status-message");
const doneResults = document.getElementById("done-results");
const donePanel = document.getElementById("done-panel");
const continueHint = document.getElementById("continue-hint");

let currentStep = 1;
let validationPassed = false;
let validationRequestId = 0;
let selectedImportMode = "historical_backfill";

const VALIDATION_FAILURES = [
  {
    test: (s) => /no \.json files|no json files/i.test(s),
    title: "Validation failed — import is blocked",
    message: "No Spotify streaming history files were found in this archive.",
    steps: [
      "Make sure you uploaded the Spotify Extended Streaming History export, not an account-info export.",
      "The archive should contain files named like Streaming_History_Audio_*.json.",
      "If Spotify is still preparing your export, wait and try again later.",
    ],
  },
  {
    test: (s) => /codec can.t decode|utf-?8.*decode|decode.*byte/i.test(s),
    title: "Validation failed — archive may be corrupted",
    message: "One or more files in the archive could not be read.",
    steps: [
      "Re-download your Spotify export and try the fresh ZIP.",
      "Use the original ZIP without re-saving or extracting and re-compressing files inside it.",
      "Avoid opening the JSON files in spreadsheet editors or text editors before import.",
    ],
  },
  {
    test: (s) => /no valid entries|no usable|no importable/i.test(s),
    title: "Validation failed — no usable history found",
    message: "The archive was read but contained no importable playback history.",
    steps: [
      "The uploaded archive may not contain Extended Streaming History data.",
      "Try a different or fresher Spotify export ZIP.",
      "Re-run validation after downloading a fresh export.",
    ],
  },
  {
    test: (s) => /too large|exceeds.*limit|size limit|zip bomb/i.test(s),
    title: "Validation failed — archive rejected",
    message: "The ZIP archive was too large or exceeded entry limits and was not processed.",
    steps: [
      "Check that the ZIP is a standard Spotify export and not an unrelated archive.",
      "If the export is very large, contact support or use the directory import option.",
    ],
  },
];

function classifyValidationError(detail) {
  const text = String(detail || "");
  for (const failure of VALIDATION_FAILURES) {
    if (failure.test(text)) {
      return failure;
    }
  }
  return {
    title: "Validation failed — import is blocked",
    message: detail || "The archive could not be validated.",
    steps: [
      "Check that the file is a Spotify Extended Streaming History export ZIP.",
      "Re-download the export and try again.",
    ],
  };
}

function setContinueHint(text) {
  if (!continueHint) return;
  if (text) {
    continueHint.textContent = text;
    continueHint.classList.remove("hidden");
  } else {
    continueHint.textContent = "";
    continueHint.classList.add("hidden");
  }
}

function formatMode(mode) {
  const labels = {
    historical_backfill: "Historical backfill",
    ongoing_sync_prep: "Recent ZIP top-up",
  };
  return labels[mode] || mode || "Unknown";
}

function formatExportType(type) {
  if (type === "extended_streaming_history_archive") {
    return "Extended Streaming History archive";
  }
  if (type === "account_info_export") {
    return "Account-info export";
  }
  return type || "Unknown";
}

function formatDateTime(value) {
  if (!value) {
    return "Unknown";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function createEmptyState(message) {
  const empty = document.createElement("section");
  empty.className = "result-section result-empty";

  const text = document.createElement("p");
  text.textContent = message;
  empty.appendChild(text);
  return empty;
}

function createResultSection(title, items) {
  const section = document.createElement("section");
  section.className = "result-section";

  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);

  const list = document.createElement("dl");
  list.className = "result-list";

  items.forEach(({ label, value }) => {
    const row = document.createElement("div");
    row.className = "result-row";

    const dt = document.createElement("dt");
    dt.textContent = label;

    const dd = document.createElement("dd");
    dd.textContent = value;

    row.append(dt, dd);
    list.appendChild(row);
  });

  section.appendChild(list);
  return section;
}

function createIssueSection(title, values, fullWidth = false) {
  const section = document.createElement("section");
  section.className = "result-section";
  if (fullWidth) {
    section.classList.add("result-section-full-width");
  }

  const heading = document.createElement("h3");
  heading.textContent = title;
  section.appendChild(heading);

  const list = document.createElement("ul");
  list.className = "result-bullets";
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.appendChild(item);
  });

  section.appendChild(list);
  return section;
}

function setStatusBanner(container, pill, titleNode, messageNode, state) {
  container.className = `status-banner ${state.tone}`;
  pill.textContent = state.label;
  pill.classList.toggle("is-loading", state.loading === true);
  titleNode.textContent = state.title;
  clearNode(messageNode);
  if (state.message) {
    const p = document.createElement("p");
    p.textContent = state.message;
    messageNode.appendChild(p);
  }
  if (Array.isArray(state.steps) && state.steps.length > 0) {
    const stepsList = document.createElement("ul");
    stepsList.className = "status-steps";
    state.steps.forEach((step) => {
      const li = document.createElement("li");
      li.textContent = step;
      stepsList.appendChild(li);
    });
    messageNode.appendChild(stepsList);
  }
}

function clearNode(node) {
  node.replaceChildren();
}

function renderValidationResults(payload) {
  clearNode(validationResults);

  if (!payload) {
    validationResults.appendChild(createEmptyState("Validation results will appear here after a ZIP is selected."));
    validationDetails.classList.add("hidden");
    validationTechnical.textContent = "";
    return;
  }

  const span = payload.archive_timespan || {};
  const dbState = payload.db_state || {};

  validationResults.appendChild(
    createResultSection("Archive Summary", [
      { label: "Detected type", value: formatExportType(payload.detected_export_type) },
      { label: "JSON files found", value: String(payload.json_files_found ?? "n/a") },
      { label: "Files sampled", value: String(payload.json_files_sampled ?? "n/a") },
      { label: "Entries sampled", value: String(payload.sampled_entries ?? "n/a") },
    ])
  );

  validationResults.appendChild(
    createResultSection("Timespan", [
      { label: "Earliest timestamp", value: formatDateTime(span.start) },
      { label: "Latest timestamp", value: formatDateTime(span.end) },
    ])
  );

  validationResults.appendChild(
    createResultSection("Import Recommendation", [
      { label: "Recommended approach", value: formatMode(payload.recommended_mode) },
      { label: "Why", value: payload.reason || "No recommendation available." },
      { label: "Current DB rows", value: String(dbState.total_rows ?? "n/a") },
      { label: "Latest DB play", value: formatDateTime(dbState.latest_ts) },
    ])
  );

  const MODE_CONSEQUENCES = {
    historical_backfill: [
      "All entries in the archive will be processed; exact duplicates are silently skipped.",
      "Suitable for a first-time full import or re-importing the same archive.",
    ],
    ongoing_sync_prep: [
      "Only plays not already in the database will be added; older duplicates are skipped.",
      "Use this to top up your database with a newer Spotify export.",
    ],
  };
  const modeConsequences = MODE_CONSEQUENCES[payload.recommended_mode] || [];
  if (modeConsequences.length > 0) {
    validationResults.appendChild(createIssueSection("What this means", modeConsequences, true));
  }

  if (Array.isArray(payload.account_export_markers_found) && payload.account_export_markers_found.length > 0) {
    validationResults.appendChild(
      createIssueSection("Archive markers", payload.account_export_markers_found)
    );
  }

  if (Array.isArray(payload.issues) && payload.issues.length > 0) {
    validationResults.appendChild(createIssueSection("Issues", payload.issues));
  }

  validationTechnical.textContent = JSON.stringify(payload, null, 2);
  validationDetails.classList.remove("hidden");
}

function classifyImport(payload) {
  const totals = payload.totals || {};

  if ((totals.inserted ?? 0) === 0 && (totals.duplicates ?? 0) > 0) {
    return {
      tone: "warning",
      label: "No-op",
      title: "Archive already imported",
      message: "No new rows were inserted because this archive is already present in the database.",
      steps: [
        "If you expected new data, make sure you uploaded the correct export.",
        "Try a newer Spotify export ZIP to add more recent listening history.",
      ],
      doneMessage: "This import finished successfully, but it did not add new rows because the same playback history was already stored locally.",
    };
  }

  if ((totals.inserted ?? 0) > 0 && (totals.skipped_missing_track_uri ?? 0) > 0) {
    return {
      tone: "warning",
      label: "Partial",
      title: "Import completed with skipped records",
      message: "New listening history was added, but some records were skipped.",
      steps: [
        "Skipped entries had no Spotify track URI and cannot be matched to a track.",
        "This is normal for some types of Spotify data (for example, podcast plays).",
        "No action is needed; your listening history is otherwise complete.",
      ],
      doneMessage: "Spoolify added new listening history and flagged a smaller set of records as unimportable.",
    };
  }

  if ((totals.inserted ?? 0) > 0) {
    return {
      tone: "success",
      label: "Success",
      title: "Import completed successfully",
      message: "New listening history was added to your local database.",
      doneMessage: "Your local database now includes the newly imported listening history.",
    };
  }

  return {
    tone: "neutral",
    label: "Complete",
    title: "Import finished",
    message: "The archive was processed successfully.",
    steps: [
      "If you expected new data, check that you uploaded the correct archive.",
    ],
    doneMessage: "The archive was processed and Spoolify is ready for the next step.",
  };
}

function renderImportResults(payload, targetNode) {
  clearNode(targetNode);
  const totals = payload.totals || {};

  targetNode.appendChild(
    createResultSection("Import Summary", [
      { label: "Import mode", value: formatMode(payload.mode) },
      { label: "Files processed", value: String(payload.files_processed ?? "n/a") },
      { label: "Rows attempted", value: String(totals.attempted ?? 0) },
      { label: "Total rows in DB", value: String(totals.total_rows ?? "n/a") },
    ])
  );

  targetNode.appendChild(
    createResultSection("Outcome", [
      { label: "Inserted", value: String(totals.inserted ?? 0) },
      { label: "Duplicates", value: String(totals.duplicates ?? 0) },
      { label: "Skipped missing track URI", value: String(totals.skipped_missing_track_uri ?? 0) },
    ])
  );
}

function resetImportPresentation() {
  clearNode(importResults);
  importResults.appendChild(createEmptyState("Import results will appear here after you start the import."));
  importTechnical.textContent = "";
  importDetails.classList.add("hidden");
  clearNode(doneResults);
}

function updateDoneState(payload) {
  const outcome = classifyImport(payload);
  if (donePanel) {
    donePanel.classList.remove("hidden");
  }
  doneMessage.textContent = outcome.doneMessage;
  setStatusBanner(doneStatus, donePill, doneTitle, doneStatusMessage, outcome);
  renderImportResults(payload, doneResults);
}

async function validateSelectedZip({ moveToValidation = false } = {}) {
  const file = getSelectedZip();
  if (!file) {
    setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
      tone: "neutral",
      label: "Idle",
      title: "Choose a ZIP to begin validation",
      message: "Spoolify will inspect the archive structure, timespan, and recommended import mode.",
    });
    renderValidationResults(null);
    return;
  }

  validationPassed = false;
  reviewImportBtn.disabled = true;
  const requestId = ++validationRequestId;

  if (moveToValidation) {
    setStep(3);
  }

  setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
    tone: "loading",
    label: "Validating",
    title: "Checking archive structure",
    message: `Inspecting ${file.name} to confirm that it contains importable Extended Streaming History data.`,
    loading: true,
  });
  renderValidationResults(null);

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/onboarding/validate-archive-zip", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (requestId !== validationRequestId) {
      return;
    }

    if (!response.ok) {
      const classified = classifyValidationError(data.detail);
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "error",
        label: "Blocked",
        title: classified.title,
        message: classified.message,
        steps: classified.steps,
      });
      validationTechnical.textContent = JSON.stringify(data, null, 2);
      validationDetails.classList.remove("hidden");
      renderValidationResults(null);
      setContinueHint("Resolve the issue above before continuing.");
      return;
    }

    selectedImportMode = data.recommended_mode || "historical_backfill";

    renderValidationResults(data);

    if (data.detected_export_type === "account_info_export") {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "warning",
        label: "Blocked",
        title: "Wrong Spotify export type — import is blocked",
        message: "This ZIP looks like an account-info export, not an Extended Streaming History export.",
        steps: [
          "Request an Extended Streaming History export from your Spotify privacy settings.",
          "The correct archive contains files named like Streaming_History_Audio_*.json.",
          "Account-info exports contain different files such as yourlibrary.json or playlists.json.",
        ],
      });
      setContinueHint("Upload an Extended Streaming History archive to continue.");
      return;
    }

    if (Array.isArray(data.issues) && data.issues.length > 0) {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "warning",
        label: "Review",
        title: "Validation completed with issues — safe to continue",
        message: "The archive was read successfully. Review the flagged issues below before importing.",
        steps: [
          "Missing track URIs are normal for some Spotify data and can be ignored.",
          "If many files are flagged, re-download the export and try again.",
          "You can continue to import; affected records will be skipped automatically.",
        ],
      });
    } else {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "success",
        label: "Ready",
        title: "Archive looks ready",
        message: "Validation completed successfully. Review the recommendation, then continue to import.",
      });
    }
    setContinueHint("");

    validationPassed = true;
    reviewImportBtn.disabled = false;
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "neutral",
      label: "Ready",
      title: "Validation complete",
      message: "The recommended import approach was selected automatically. Start import when ready.",
    });
  } catch (error) {
    if (requestId !== validationRequestId) {
      return;
    }
    setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
      tone: "error",
      label: "Error",
      title: "Validation error — import is blocked",
      message: "Spoolify could not reach the validation service.",
      steps: [
        "Check that the Spoolify server is still running.",
        "Reload the page and try again.",
        "If the problem persists, restart the server with: python entrypoint.py serve",
      ],
    });
    validationTechnical.textContent = String(error);
    validationDetails.classList.remove("hidden");
    renderValidationResults(null);
    setContinueHint("Fix the connection error above before continuing.");
  }
}

function getSelectedZip() {
  if (!zipInput || !zipInput.files || zipInput.files.length === 0) {
    return null;
  }
  return zipInput.files[0];
}

function setStep(stepNumber) {
  currentStep = stepNumber;
  steps.forEach((stepNode) => {
    const isCurrent = Number(stepNode.dataset.step) === stepNumber;
    stepNode.classList.toggle("hidden", !isCurrent);
  });
  indicators.forEach((indicatorNode) => {
    const index = Number(indicatorNode.dataset.stepIndicator);
    indicatorNode.classList.toggle("completed", index < stepNumber);
    indicatorNode.classList.toggle("current", index === stepNumber);
    indicatorNode.classList.toggle("upcoming", index > stepNumber);
  });

  const activeStep = steps.find((stepNode) => Number(stepNode.dataset.step) === stepNumber);
  const heading = activeStep?.querySelector("h2");
  if (heading instanceof HTMLElement) {
    window.requestAnimationFrame(() => {
      heading.focus();
    });
  }
}

function resetFlow() {
  validationPassed = false;
  validationRequestId += 1;
  reviewImportBtn.disabled = true;
  setContinueHint("");
  stepTwoContinueBtn.disabled = true;
  zipInput.value = "";
  zipSelected.textContent = "No ZIP selected.";
  selectedImportMode = "historical_backfill";
  if (donePanel) {
    donePanel.classList.add("hidden");
  }
  setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
    tone: "neutral",
    label: "Idle",
    title: "Choose a ZIP to begin validation",
    message: "Spoolify will inspect the archive structure, timespan, and recommended import mode.",
  });
  renderValidationResults(null);
  setStatusBanner(importStatus, importPill, importTitle, importMessage, {
    tone: "neutral",
    label: "Ready",
    title: "Validation complete",
    message: "Start import after validation. Spoolify applies the recommended approach automatically.",
  });
  resetImportPresentation();
  doneMessage.textContent = "Your listening history is ready to explore locally.";
  setStatusBanner(doneStatus, donePill, doneTitle, doneStatusMessage, {
    tone: "success",
    label: "Done",
    title: "Import finished",
    message: "Spoolify imported the archive and prepared your local analytics data.",
  });
  setStep(1);
}

zipInput.addEventListener("change", async () => {
  const file = getSelectedZip();
  if (!file) {
    zipSelected.textContent = "No ZIP selected.";
    stepTwoContinueBtn.disabled = true;
    return;
  }

  zipSelected.textContent = `Selected: ${file.name}`;
  stepTwoContinueBtn.disabled = false;
  validationPassed = false;
  reviewImportBtn.disabled = true;
  resetImportPresentation();
  await validateSelectedZip({ moveToValidation: true });
});

startBtn.addEventListener("click", () => setStep(2));
restartBtn.addEventListener("click", () => resetFlow());
stepTwoBackBtn.addEventListener("click", () => setStep(1));
stepThreeBackBtn.addEventListener("click", () => setStep(2));
stepFourBackBtn.addEventListener("click", () => setStep(3));
stepTwoContinueBtn.addEventListener("click", () => validateSelectedZip({ moveToValidation: true }));
reviewImportBtn.addEventListener("click", () => {
  if (validationPassed) {
    setStep(4);
  }
});
validateZipBtn.addEventListener("click", () => validateSelectedZip({ moveToValidation: false }));

importZipBtn.addEventListener("click", async () => {
  const file = getSelectedZip();
  if (!file) {
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "error",
      label: "Missing ZIP",
      title: "Choose a ZIP file first",
      message: "Return to the ZIP selection step and choose an archive before importing.",
    });
    return;
  }

  if (!validationPassed) {
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "warning",
      label: "Blocked",
      title: "Validation required",
      message: "Validation must complete successfully before the import can start.",
    });
    return;
  }

  setStatusBanner(importStatus, importPill, importTitle, importMessage, {
    tone: "loading",
    label: "Importing",
    title: "Processing archive",
    message: "Importing the ZIP archive now. Large history exports can take a while.",
    loading: true,
  });
  clearNode(importResults);
  importResults.appendChild(createEmptyState("Import is running. Results will appear here when processing finishes."));
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", selectedImportMode);

  try {
    const response = await fetch("/onboarding/import-zip", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    if (!response.ok) {
      setStatusBanner(importStatus, importPill, importTitle, importMessage, {
        tone: "error",
        label: "Error",
        title: "Import failed — archive could not be processed",
        message: data.detail || "One or more files in the archive could not be read.",
        steps: [
          "Re-download your Spotify export and try the fresh ZIP.",
          "Use the original ZIP without modifying or re-saving any files inside it.",
          "Re-run validation before importing again.",
        ],
      });
      importTechnical.textContent = JSON.stringify(data, null, 2);
      importDetails.classList.remove("hidden");
      return;
    }

    const outcome = classifyImport(data);
    setStatusBanner(importStatus, importPill, importTitle, importMessage, outcome);
    renderImportResults(data, importResults);
    importTechnical.textContent = JSON.stringify(data, null, 2);
    importDetails.classList.remove("hidden");
    updateDoneState(data);
    setStep(4);
    
    // Redirect to dashboard after 3 seconds for successful imports only
    if (outcome.tone === "success") {
      setTimeout(() => {
        window.location.href = "/dashboard";
      }, 3000);
    }
  } catch (error) {
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "error",
      label: "Error",
      title: "Import error — archive could not be processed",
      message: "Spoolify was unable to complete the import.",
      steps: [
        "Check that the Spoolify server is still running.",
        "Try re-running the import from the beginning.",
      ],
    });
    importTechnical.textContent = String(error);
    importDetails.classList.remove("hidden");
  }
});

// Check if database has data on page load; redirect to dashboard if it does
async function checkAndRedirectIfDataExists() {
  try {
    const response = await fetch("/stats");
    if (response.ok) {
      const data = await response.json();
      const stats = data.data || data;
      
      // If there's data in the database (overall stats with plays > 0), redirect to dashboard
      if (stats.overall && stats.overall.total_plays > 0) {
        window.location.href = "/dashboard";
        return;
      }
    }
  } catch (error) {
    // If stats endpoint fails or database is empty, stay on onboarding
    console.log("No existing data or error checking stats, showing onboarding");
  }
  
  // Show onboarding if no data exists
  resetFlow();
}

// Run on page load
checkAndRedirectIfDataExists();
