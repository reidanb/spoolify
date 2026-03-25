const validateForm = document.getElementById("validate-form");
const importForm = document.getElementById("import-form");
const archivePathInput = document.getElementById("archive-path");
const modeInput = document.getElementById("import-mode");
const validateOutput = document.getElementById("validate-output");
const importOutput = document.getElementById("import-output");
const zipInput = document.getElementById("archive-zip");
const zipValidateBtn = document.getElementById("zip-validate-btn");
const zipImportBtn = document.getElementById("zip-import-btn");
const zipOutput = document.getElementById("zip-output");

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

validateForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = archivePathInput.value.trim();
  if (!path) {
    validateOutput.textContent = "Please enter a file or directory path.";
    return;
  }

  validateOutput.textContent = "Validating archive...";

  try {
    const response = await fetch("/onboarding/validate-archive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });

    const data = await response.json();
    console.log("Validate archive response", data);
    if (!response.ok) {
      validateOutput.textContent = data.detail || "Validation failed.";
      return;
    }

    if (data.recommended_mode) {
      modeInput.value = data.recommended_mode;
    }

    if (data.detected_export_type === "account_info_export") {
      alert("Detected Spotify account-info export. Spoolify currently imports only Extended Streaming History JSON files.");
    }

    validateOutput.textContent = renderValidationSummary(data);
  } catch (error) {
    validateOutput.textContent = `Validation error: ${error}`;
  }
});

importForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = archivePathInput.value.trim();
  const mode = modeInput.value;

  if (!path) {
    importOutput.textContent = "Set archive path before importing.";
    return;
  }

  importOutput.textContent = "Importing... this can take a while for large archives.";

  try {
    const response = await fetch("/onboarding/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, mode }),
    });

    const data = await response.json();
    console.log("Import archive response", data);
    if (!response.ok) {
      importOutput.textContent = data.detail || "Import failed.";
      return;
    }

    importOutput.textContent = renderImportSummary(data);
  } catch (error) {
    importOutput.textContent = `Import error: ${error}`;
  }
});

function getSelectedZip() {
  if (!zipInput || !zipInput.files || zipInput.files.length === 0) {
    return null;
  }
  return zipInput.files[0];
}

zipValidateBtn.addEventListener("click", async () => {
  const file = getSelectedZip();
  if (!file) {
    zipOutput.textContent = "Choose a ZIP file first.";
    return;
  }

  zipOutput.textContent = "Validating ZIP archive...";
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
      zipOutput.textContent = data.detail || "ZIP validation failed.";
      return;
    }

    if (data.recommended_mode) {
      modeInput.value = data.recommended_mode;
    }

    if (data.detected_export_type === "account_info_export") {
      alert("Detected Spotify account-info export in ZIP. Spoolify currently imports only Extended Streaming History JSON files.");
    }

    zipOutput.textContent = renderValidationSummary(data);
  } catch (error) {
    zipOutput.textContent = `ZIP validation error: ${error}`;
  }
});

zipImportBtn.addEventListener("click", async () => {
  const file = getSelectedZip();
  if (!file) {
    zipOutput.textContent = "Choose a ZIP file first.";
    return;
  }

  zipOutput.textContent = "Importing ZIP archive... this can take a while for large files.";
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
      zipOutput.textContent = data.detail || "ZIP import failed.";
      return;
    }

    zipOutput.textContent = renderImportSummary(data);
  } catch (error) {
    zipOutput.textContent = `ZIP import error: ${error}`;
  }
});
