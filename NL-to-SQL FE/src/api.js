
/* =========================================
   DataPilot AI — API Client
   ========================================= */

// Production:
// Set VITE_API_BASE_URL in .env.production
// Example: https://api.yourdomain.com

const RAW_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  "http://127.0.0.1:8000";

export const API_BASE_URL = RAW_BASE.replace(/\/+$/, "");

const DEFAULT_TIMEOUT_MS = 30_000;

// Large files may take longer to upload and process.
const UPLOAD_TIMEOUT_MS = 600_000;

// AI analysis and editing operations.
const LONG_TIMEOUT_MS = 120_000;

// Maximum upload size: 200 MB.
export const MAX_FILE_SIZE_MB = 200;

async function request(
  endpoint,
  options = {},
  timeout = DEFAULT_TIMEOUT_MS
) {
  const controller = new AbortController();

  const timer = setTimeout(
    () => controller.abort(),
    timeout
  );

  let response;

  try {
    response = await fetch(
      `${API_BASE_URL}${endpoint}`,
      {
        ...options,
        signal: controller.signal,
      }
    );
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error(
        "The request took too long. Please try again."
      );
    }

    throw new Error(
      "Cannot reach the DataPilot server. Make sure the backend is running."
    );
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;

    try {
      const body = await response.json();

      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail
          .map((detail) => detail.msg)
          .join(", ");
      } else if (body.detail) {
        message = JSON.stringify(body.detail);
      }
    } catch {
      // Keep the default error message.
    }

    if (
      response.status >= 500 &&
      message.startsWith("Request failed")
    ) {
      message =
        "Something went wrong on the server. Please try again.";
    }

    throw new Error(message);
  }

  return response;
}

async function json(endpoint, options, timeout) {
  const response = await request(
    endpoint,
    options,
    timeout
  );

  return response.json();
}

function jsonPost(endpoint, payload, timeout) {
  return json(
    endpoint,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    },
    timeout
  );
}

/* =========================================
   Backend Health
   ========================================= */

export function checkBackend() {
  return json("/health", undefined, 8_000);
}

/* =========================================
   File Validation
   ========================================= */

export function validateFile(file) {
  if (!file) {
    throw new Error("Please select a file.");
  }

  const extension = file.name
    .split(".")
    .pop()
    ?.toLowerCase();

  if (!["csv", "xlsx"].includes(extension)) {
    throw new Error(
      "Only CSV and XLSX files are supported."
    );
  }

  if (file.size === 0) {
    throw new Error("This file is empty.");
  }

  if (
    file.size >
    MAX_FILE_SIZE_MB * 1024 * 1024
  ) {
    throw new Error(
      `Maximum file size is ${MAX_FILE_SIZE_MB} MB.`
    );
  }
}

/* =========================================
   Upload Dataset
   ========================================= */

export function uploadFile(file) {
  validateFile(file);

  const formData = new FormData();

  formData.append("file", file);

  return json(
    "/upload",
    {
      method: "POST",
      body: formData,
    },
    UPLOAD_TIMEOUT_MS
  );
}

/* =========================================
   Get Dataset
   ========================================= */

export function getDataset(datasetId) {
  return json(
    `/datasets/${encodeURIComponent(datasetId)}`
  );
}

/* =========================================
   Data Explorer
   ========================================= */

export function queryData(datasetId, question) {
  return jsonPost(
    "/query",
    {
      dataset_id: datasetId,
      question: question.trim(),
    },
    LONG_TIMEOUT_MS
  );
}

/* =========================================
   AI Assistant — Preview Edit
   ========================================= */

export function previewEdit(datasetId, instruction) {
  return jsonPost(
    "/edit/preview",
    {
      dataset_id: datasetId,
      instruction: instruction.trim(),
    },
    LONG_TIMEOUT_MS
  );
}

/* =========================================
   AI Assistant — Confirm Edit
   ========================================= */

export function confirmEdit(datasetId, editId) {
  return jsonPost(
    "/edit/confirm",
    {
      dataset_id: datasetId,
      edit_id: editId,
    },
    UPLOAD_TIMEOUT_MS
  );
}

/* =========================================
   AI Assistant — Cancel Edit
   ========================================= */

export function cancelEdit(datasetId, editId) {
  return jsonPost(
    "/edit/cancel",
    {
      dataset_id: datasetId,
      edit_id: editId,
    }
  );
}

/* =========================================
   Download Updated Dataset
   ========================================= */

export async function downloadDataset(
  datasetId,
  fallbackName = "updated_data.xlsx"
) {
  const response = await request(
    `/datasets/${encodeURIComponent(datasetId)}/download`,
    {},
    UPLOAD_TIMEOUT_MS
  );

  const disposition =
    response.headers.get("Content-Disposition") || "";

  const match = disposition.match(
    /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i
  );

  let filename = fallbackName;

  if (match) {
    try {
      filename = decodeURIComponent(match[1]);
    } catch {
      filename = match[1];
    }
  }

  const blob = await response.blob();

  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");

  link.href = url;
  link.download = filename;

  document.body.appendChild(link);

  link.click();

  link.remove();

  setTimeout(() => {
    URL.revokeObjectURL(url);
  }, 1000);
}
