const startBtn = document.getElementById("start-btn");
const restartBtn = document.getElementById("restart-btn");
const stepTwoBackBtn = document.getElementById("to-step-1");
const stepThreeBackBtn = document.getElementById("to-step-2");
const stepFourBackBtn = document.getElementById("to-step-3b");
const stepTwoContinueBtn = document.getElementById("to-step-3");
const stepThreeContinueBtn = document.getElementById("to-step-4");
const validateZipBtn = document.getElementById("validate-zip-btn");
const importZipBtn = document.getElementById("import-zip-btn");

const steps = Array.from(document.querySelectorAll("[data-step]"));
const indicators = Array.from(document.querySelectorAll("[data-step-indicator]"));

const modeInput = document.getElementById("import-mode");
const validateOutput = document.getElementById("validate-output");
const importOutput = document.getElementById("import-output");
const doneOutput = document.getElementById("done-output");
const zipInput = document.getElementById("archive-zip");
const zipSelected = document.getElementById("zip-selected");

let currentStep = 1;
let validationPassed = false;

function renderValidationSummary(payload) {
  const lines = [];
  lines.push(`Detected type: ${payload.detected_export_type || "unknown"}`);
  lines.push(`JSON files found: ${payload.json_files_found ?? "n/a"}`);
  lines.push(`Files sampled: ${payload.json_files_sampled ?? "n/a"}`);
  lines.push(`Entries sampled: ${payload.sampled_entries ?? "n/a"}`);

  const span = payload.archive_timespan || {};
  if (span.start || span.end) {
    lines.push(`Archive timespan: ${span.start || "unknown"} -> ${span.end || "unknown"}`);
  }

  if (payload.recommended_mode) {
    lines.push(`Recommended mode: ${payload.recommended_mode}`);
  }
  if (payload.reason) {
    lines.push(`Reason: ${payload.reason}`);
  }

  const markers = payload.account_export_markers_found || [];
  if (markers.length > 0) {
    lines.push("");
    lines.push("Account-info export markers found:");
    lines.push(markers.join(", "));
    lines.push("");
    lines.push("Spoolify currently imports only Extended Streaming History JSON.");
  }

  if (Array.isArray(payload.issues) && payload.issues.length > 0) {
    lines.push("");
    lines.push("Issues:");
    payload.issues.forEach((issue) => lines.push(`- ${issue}`));
  }

  return lines.join("\n");
}

function renderImportSummary(payload) {
  const totals = payload.totals || {};
  const lines = [];
  lines.push(`Import mode: ${payload.mode || "unknown"}`);
  lines.push(`Files processed: ${payload.files_processed ?? "n/a"}`);
  lines.push(`Inserted: ${totals.inserted ?? 0}`);
  lines.push(`Duplicates: ${totals.duplicates ?? 0}`);
  lines.push(`Attempted: ${totals.attempted ?? 0}`);
  lines.push(`Skipped missing track URI: ${totals.skipped_missing_track_uri ?? 0}`);
  lines.push(`Total rows in DB: ${totals.total_rows ?? "n/a"}`);
  return lines.join("\n");
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
    indicatorNode.classList.toggle("active", index <= stepNumber);
  });
}

function resetFlow() {
  validationPassed = false;
  stepThreeContinueBtn.disabled = true;
  validateOutput.textContent = "Validation not started.";
  importOutput.textContent = "Import not started.";
  doneOutput.textContent = "Awaiting import summary.";
  setStep(1);
}

zipInput.addEventListener("change", () => {
  const file = getSelectedZip();
  if (!file) {
    zipSelected.textContent = "No ZIP selected.";
    stepTwoContinueBtn.disabled = true;
    return;
  }
  zipSelected.textContent = `Selected: ${file.name}`;
  stepTwoContinueBtn.disabled = false;
  validationPassed = false;
  stepThreeContinueBtn.disabled = true;
});

startBtn.addEventListener("click", () => setStep(2));
restartBtn.addEventListener("click", () => resetFlow());
stepTwoBackBtn.addEventListener("click", () => setStep(1));
stepThreeBackBtn.addEventListener("click", () => setStep(2));
stepFourBackBtn.addEventListener("click", () => setStep(3));
stepTwoContinueBtn.addEventListener("click", () => setStep(3));
stepThreeContinueBtn.addEventListener("click", () => {
  if (validationPassed) {
    setStep(4);
  }
});

validateZipBtn.addEventListener("click", async () => {
  const file = getSelectedZip();
  if (!file) {
    validateOutput.textContent = "Choose a ZIP file first.";
    return;
  }

  validateOutput.textContent = "Validating ZIP archive...";
  validationPassed = false;
  stepThreeContinueBtn.disabled = true;

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("/onboarding/validate-archive-zip", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    console.log("Validate ZIP response", data);
    if (!response.ok) {
      validateOutput.textContent = data.detail || "ZIP validation failed.";
      return;
    }

    if (data.recommended_mode) {
      modeInput.value = data.recommended_mode;
    }

    if (data.detected_export_type === "account_info_export") {
      alert("Detected Spotify account-info export in ZIP. Spoolify currently imports only Extended Streaming History JSON files.");
      validateOutput.textContent = renderValidationSummary(data);
      return;
    }

    validateOutput.textContent = renderValidationSummary(data);
    validationPassed = true;
    stepThreeContinueBtn.disabled = false;
  } catch (error) {
    validateOutput.textContent = `ZIP validation error: ${error}`;
  }
});

importZipBtn.addEventListener("click", async () => {
  const file = getSelectedZip();
  if (!file) {
    importOutput.textContent = "Choose a ZIP file first.";
    return;
  }

  if (!validationPassed) {
    importOutput.textContent = "Run validation successfully before importing.";
    return;
  }

  importOutput.textContent = "Importing ZIP archive... this can take a while for large files.";
  const formData = new FormData();
  formData.append("file", file);
  formData.append("mode", modeInput.value);

  try {
    const response = await fetch("/onboarding/import-zip", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();
    console.log("Import ZIP response", data);
    if (!response.ok) {
      importOutput.textContent = data.detail || "ZIP import failed.";
      return;
    }

    const summary = renderImportSummary(data);
    importOutput.textContent = summary;
    doneOutput.textContent = summary;
    setStep(5);
  } catch (error) {
    importOutput.textContent = `ZIP import error: ${error}`;
  }
});

resetFlow();
