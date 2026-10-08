document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("certForm");
  const certDateInput = document.getElementById("certDate");
  const submitBtn = document.getElementById("submitBtn");
  const errorAlert = document.getElementById("errorAlert");
  const statusContainer = document.getElementById("statusContainer");

  const manualInputBlock = document.getElementById("manualInputBlock");
  const fileUploadBlock = document.getElementById("fileUploadBlock");
  const excelFileInput = document.getElementById("excelFile");
  const modeRadios = document.querySelectorAll('input[name="inputMode"]');

  const jobIdEl = document.getElementById("jobId");
  const jobStatusEl = document.getElementById("jobStatus");
  const jobProgressEl = document.getElementById("jobProgress");
  const jobSuccessEl = document.getElementById("jobSuccess");
  const jobFailedEl = document.getElementById("jobFailed");
  const progressBarEl = document.getElementById("progressBar");
  const certificatesListEl = document.getElementById("certificatesList");

  // Set default date to today YYYY-MM-DD
  const today = new Date().toISOString().split("T")[0];
  certDateInput.value = today;

  let pollInterval = null;

  // Toggle input mode between Textarea and File Upload
  modeRadios.forEach(radio => {
    radio.addEventListener("change", (e) => {
      if (e.target.value === "file") {
        manualInputBlock.style.display = "none";
        fileUploadBlock.style.display = "block";
      } else {
        manualInputBlock.style.display = "block";
        fileUploadBlock.style.display = "none";
      }
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    hideError();

    const eventName = document.getElementById("eventName").value.trim();
    const certificateDate = certDateInput.value;
    const selectedMode = document.querySelector('input[name="inputMode"]:checked').value;

    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting Job...";

    if (selectedMode === "file") {
      // File Upload Mode
      const file = excelFileInput.files[0];
      if (!file) {
        showError("Please select an Excel (.xlsx) or CSV file to upload.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Certificates";
        return;
      }

      const formData = new FormData();
      formData.append("event_name", eventName);
      formData.append("certificate_date", certificateDate);
      formData.append("file", file);

      try {
        const response = await fetch("/api/v1/certificates/jobs/upload", {
          method: "POST",
          body: formData
        });

        let data;
        try {
          data = await response.json();
        } catch (jsonErr) {
          showError(`Server error (${response.status}): Server returned non-JSON response.`);
          submitBtn.disabled = false;
          submitBtn.textContent = "Generate Certificates";
          return;
        }

        if (!response.ok) {
          const errorMsg = data?.error?.message || "Failed to submit certificate job.";
          const details = data?.error?.details ? `\n• ${data.error.details.join("\n• ")}` : "";
          showError(errorMsg + details);
          submitBtn.disabled = false;
          submitBtn.textContent = "Generate Certificates";
          return;
        }

        const jobId = data.job_id;
        showStatusContainer(jobId);
        startPolling(jobId);

      } catch (err) {
        showError(`Network error: ${err.message}`);
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Certificates";
      }

    } else {
      // Manual Textarea Entry Mode
      const recipientsText = document.getElementById("recipients").value.trim();
      const lines = recipientsText.split("\n").map(l => l.trim()).filter(l => l.length > 0);
      const recipients = [];

      for (const line of lines) {
        const parts = line.split(",");
        if (parts.length < 2) {
          showError(`Invalid recipient format line: "${line}". Expected "Name,email@example.com"`);
          submitBtn.disabled = false;
          submitBtn.textContent = "Generate Certificates";
          return;
        }
        const name = parts.slice(0, -1).join(",").trim();
        const email = parts[parts.length - 1].trim();
        recipients.push({ name, email });
      }

      if (recipients.length === 0) {
        showError("Please enter at least one recipient.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Certificates";
        return;
      }

      const payload = {
        event_name: eventName,
        certificate_date: certificateDate,
        recipients: recipients
      };

      try {
        const response = await fetch("/api/v1/certificates/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });

        let data;
        try {
          data = await response.json();
        } catch (jsonErr) {
          showError(`Server error (${response.status}): Server returned non-JSON response.`);
          submitBtn.disabled = false;
          submitBtn.textContent = "Generate Certificates";
          return;
        }

        if (!response.ok) {
          const errorMsg = data?.error?.message || "Failed to submit certificate job.";
          const details = data?.error?.details ? `\n• ${data.error.details.join("\n• ")}` : "";
          showError(errorMsg + details);
          submitBtn.disabled = false;
          submitBtn.textContent = "Generate Certificates";
          return;
        }

        const jobId = data.job_id;
        showStatusContainer(jobId);
        startPolling(jobId);

      } catch (err) {
        showError(`Network error: ${err.message}`);
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Certificates";
      }
    }
  });

  function startPolling(jobId) {
    if (pollInterval) clearInterval(pollInterval);
    fetchJobStatus(jobId);
    pollInterval = setInterval(() => fetchJobStatus(jobId), 1000);
  }

  async function fetchJobStatus(jobId) {
    try {
      const response = await fetch(`/api/v1/certificates/jobs/${jobId}`);
      if (!response.ok) return;

      const data = await response.json();
      updateUI(data);

      const terminalStatuses = ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"];
      if (terminalStatuses.includes(data.status)) {
        clearInterval(pollInterval);
        submitBtn.disabled = false;
        submitBtn.textContent = "Generate Certificates";
      }
    } catch (err) {
      console.error("Error polling job status:", err);
    }
  }

  function updateUI(job) {
    jobIdEl.textContent = job.job_id;
    jobStatusEl.textContent = job.status;
    jobProgressEl.textContent = `${job.completed} / ${job.total}`;
    jobSuccessEl.textContent = job.successful;
    jobFailedEl.textContent = job.failed;

    progressBarEl.style.width = `${job.progress_percentage}%`;

    certificatesListEl.innerHTML = "<h3>Generated Certificates</h3>";

    if (job.certificates && job.certificates.length > 0) {
      job.certificates.forEach(cert => {
        const item = document.createElement("div");
        item.className = "cert-item";

        let statusText = `<span class="badge">${cert.status}</span>`;
        let action = "";

        if (cert.status === "COMPLETED") {
          statusText = `<span class="cert-status-success">✓ Ready</span>`;
          action = `<a href="/api/v1/certificates/${cert.certificate_id}" target="_blank" class="download-link">Download PDF</a>`;
        } else if (cert.status === "FAILED") {
          const reason = cert.error || "Certificate generation failed";
          statusText = `
            <span class="cert-status-failed">✗ Failed</span>
            <div class="fail-reason"><strong>Reason:</strong> ${escapeHtml(reason)}</div>
          `;
        } else {
          statusText = `<span class="badge">${cert.status}...</span>`;
        }

        item.innerHTML = `
          <div class="cert-info">
            <strong>${escapeHtml(cert.recipient_name)}</strong> ${cert.recipient_email ? `(${escapeHtml(cert.recipient_email)})` : ""}<br>
            <small>${statusText}</small>
          </div>
          <div>${action}</div>
        `;
        certificatesListEl.appendChild(item);
      });
    }
  }


  function showStatusContainer(jobId) {
    jobIdEl.textContent = jobId;
    jobStatusEl.textContent = "PENDING";
    jobProgressEl.textContent = "0";
    jobSuccessEl.textContent = "0";
    jobFailedEl.textContent = "0";
    progressBarEl.style.width = "0%";
    certificatesListEl.innerHTML = "";
    statusContainer.style.display = "block";
  }

  function showError(msg) {
    errorAlert.textContent = msg;
    errorAlert.style.display = "block";
  }

  function hideError() {
    errorAlert.style.display = "none";
    errorAlert.textContent = "";
  }

  function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
});
