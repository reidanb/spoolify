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

const modeInput = document.getElementById("import-mode");
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

let currentStep = 1;
let validationPassed = false;
let validationRequestId = 0;

function formatMode(mode) {
  const labels = {
    historical_backfill: "Historical backfill",
    ongoing_sync_prep: "Ongoing sync prep",
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

function createIssueSection(title, values) {
  const section = document.createElement("section");
  section.className = "result-section";

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
  messageNode.textContent = state.message;
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
      { label: "Recommended mode", value: formatMode(payload.recommended_mode) },
      { label: "Why", value: payload.reason || "No recommendation available." },
      { label: "Current DB rows", value: String(dbState.total_rows ?? "n/a") },
      { label: "Latest DB play", value: formatDateTime(dbState.latest_ts) },
    ])
  );

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
      doneMessage: "This import finished successfully, but it did not add new rows because the same playback history was already stored locally.",
    };
  }

  if ((totals.inserted ?? 0) > 0 && (totals.skipped_missing_track_uri ?? 0) > 0) {
    return {
      tone: "warning",
      label: "Partial",
      title: "Import completed with skipped records",
      message: "New listening history was added, but some rows were skipped because they had no Spotify track URI.",
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
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "error",
        label: "Blocked",
        title: "Validation failed",
        message: data.detail || "The archive could not be validated.",
      });
      renderValidationResults({ issues: [data.detail || "Validation failed."] });
      return;
    }

    if (data.recommended_mode) {
      modeInput.value = data.recommended_mode;
    }

    renderValidationResults(data);

    if (data.detected_export_type === "account_info_export") {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "warning",
        label: "Blocked",
        title: "Wrong Spotify export type",
        message: "This ZIP looks like an account-info export. Spoolify imports only Extended Streaming History JSON files.",
      });
      return;
    }

    if (Array.isArray(data.issues) && data.issues.length > 0) {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "warning",
        label: "Review",
        title: "Validation completed with issues",
        message: "The archive was read, but you should review the flagged issues before importing.",
      });
    } else {
      setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
        tone: "success",
        label: "Ready",
        title: "Archive looks ready",
        message: "Validation completed successfully. Review the recommendation, then continue to import.",
      });
    }

    validationPassed = true;
    reviewImportBtn.disabled = false;
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "neutral",
      label: "Ready",
      title: "Validation complete",
      message: "The recommended import mode has been preselected. Adjust it only if you know this archive should be treated differently.",
    });
  } catch (error) {
    if (requestId !== validationRequestId) {
      return;
    }
    setStatusBanner(validationStatus, validationPill, validationTitle, validationMessage, {
      tone: "error",
      label: "Error",
      title: "Validation error",
      message: `Unable to validate the ZIP archive: ${error}`,
    });
    renderValidationResults({ issues: [`ZIP validation error: ${error}`] });
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
  stepTwoContinueBtn.disabled = true;
  zipInput.value = "";
  zipSelected.textContent = "No ZIP selected.";
  modeInput.value = "historical_backfill";
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
    message: "Choose the recommended mode or adjust it if you know this archive should be imported differently.",
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
  formData.append("mode", modeInput.value);

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
        title: "Import failed",
        message: data.detail || "ZIP import failed.",
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
    setStep(5);
  } catch (error) {
    setStatusBanner(importStatus, importPill, importTitle, importMessage, {
      tone: "error",
      label: "Error",
      title: "Import error",
      message: `ZIP import error: ${error}`,
    });
  }
});

resetFlow();
