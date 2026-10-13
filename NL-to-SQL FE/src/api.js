/* DataPilot AI API client — multilingual, projects, editing, and paginated datasets. */
import { LANGUAGE_OPTIONS } from "./i18n";

const RAW_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
export const API_BASE_URL = String(RAW_BASE).replace(/\/+$/, "");
const DEFAULT_TIMEOUT_MS = 30_000;
const LONG_TIMEOUT_MS = 120_000;
const UPLOAD_TIMEOUT_MS = 600_000;
export const MAX_FILE_SIZE_MB = 200;
export const DATASET_PAGE_SIZE = 200;
export const MAX_DATASET_PAGE_SIZE = 500;
export const SUPPORTED_LANGUAGES = LANGUAGE_OPTIONS.map((item) => item.code);
export const DEFAULT_LANGUAGE = "en";

export function normalizeLanguage(language = DEFAULT_LANGUAGE) {
  return SUPPORTED_LANGUAGES.includes(language) ? language : DEFAULT_LANGUAGE;
}

async function request(endpoint, options = {}, timeout = DEFAULT_TIMEOUT_MS) {
  const { signal: externalSignal, ...fetchOptions } = options;
  const controller = new AbortController();
  let timedOut = false;
  const onAbort = () => controller.abort();
  if (externalSignal?.aborted) controller.abort();
  else externalSignal?.addEventListener("abort", onAbort, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...fetchOptions,
      signal: controller.signal,
    });
  } catch (err) {
    if (err?.name === "AbortError") {
      if (timedOut) throw new Error("The request took too long. Please try again.");
      throw err;
    }
    throw new Error("Cannot reach the DataPilot server. Make sure the backend is running.");
  } finally {
    clearTimeout(timer);
    externalSignal?.removeEventListener("abort", onAbort);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) {
        message = body.detail.map((detail) => detail.msg || "Validation failed").join(", ");
      } else if (body.detail) message = JSON.stringify(body.detail);
    } catch {
      // Keep the default message if the server does not return JSON.
    }
    if (response.status >= 500 && message.startsWith("Request failed")) {
      message = "Something went wrong on the server. Please try again.";
    }
    throw new Error(message);
  }
  return response;
}

async function json(endpoint, options, timeout) {
  const response = await request(endpoint, options, timeout);
  return response.json();
}

function jsonPost(endpoint, payload, timeout) {
  return json(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }, timeout);
}

export function checkBackend() {
  return json("/health", undefined, 8_000);
}

export function validateFile(file) {
  if (!file) throw new Error("Please select a file.");
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!["csv", "xlsx"].includes(extension)) {
    throw new Error("Only CSV and XLSX files are supported.");
  }
  if (file.size === 0) throw new Error("This file is empty.");
  if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
    throw new Error(`Maximum file size is ${MAX_FILE_SIZE_MB} MB.`);
  }
}

export function uploadFile(file) {
  validateFile(file);
  const formData = new FormData();
  formData.append("file", file);
  return json("/upload", { method: "POST", body: formData }, UPLOAD_TIMEOUT_MS);
}

export function createNewProject(projectName, columns) {
  if (typeof projectName !== "string" || !projectName.trim()) {
    throw new Error("Please enter a project name.");
  }
  if (projectName.trim().length > 100) {
    throw new Error("Project name cannot exceed 100 characters.");
  }
  if (!Array.isArray(columns) || columns.length === 0) {
    throw new Error("Please add at least one column.");
  }
  if (columns.length > 100) {
    throw new Error("A project can have a maximum of 100 columns.");
  }
  const supportedTypes = new Set([
    "text", "string", "str", "integer", "int", "decimal", "float",
    "number", "boolean", "bool", "date", "datetime",
  ]);
  const normalizedColumns = columns.map((column, index) => {
    const name = typeof column?.name === "string" ? column.name.trim() : "";
    const type = typeof column?.type === "string"
      ? column.type.trim().toLowerCase() : "text";
    if (!name) throw new Error(`Column ${index + 1} requires a name.`);
    if (name.length > 128) throw new Error(`Column "${name}" exceeds 128 characters.`);
    if (!supportedTypes.has(type)) {
      throw new Error(`Unsupported type "${type}" for column "${name}".`);
    }
    return { name, type };
  });
  const names = normalizedColumns.map((column) => column.name.replace(/ /g, "_").toLowerCase());
  if (new Set(names).size !== names.length) {
    throw new Error("Duplicate column names are not allowed.");
  }
  return jsonPost("/projects/new", {
    project_name: projectName.trim(),
    columns: normalizedColumns,
  }, LONG_TIMEOUT_MS);
}

export function getDataset(datasetId) {
  return json(`/datasets/${encodeURIComponent(datasetId)}`);
}

/** Fetch only a slice of the dataset. Full data remains on the server.
 * Returns the backend pagination response, typically including rows, total_rows,
 * offset, limit, and revision. The UI will consume this in the next step.
 */
export function getDatasetRows(datasetId, offset = 0, limit = DATASET_PAGE_SIZE, options = {}) {
  if (!datasetId) throw new Error("Dataset ID is required.");
  if (!Number.isSafeInteger(offset) || offset < 0) {
    throw new Error("Offset must be a non-negative integer.");
  }
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_DATASET_PAGE_SIZE) {
    throw new Error(`Page size must be between 1 and ${MAX_DATASET_PAGE_SIZE}.`);
  }
  const params = new URLSearchParams({ offset: String(offset), limit: String(limit) });
  return json(
    `/datasets/${encodeURIComponent(datasetId)}/rows?${params.toString()}`,
    { signal: options.signal },
    LONG_TIMEOUT_MS
  );
}

export function queryData(datasetId, question, language = DEFAULT_LANGUAGE) {
  return jsonPost("/query", {
    dataset_id: datasetId,
    question: question.trim(),
    language: normalizeLanguage(language),
  }, LONG_TIMEOUT_MS);
}

export function previewEdit(datasetId, instruction, language = DEFAULT_LANGUAGE) {
  return jsonPost("/edit/preview", {
    dataset_id: datasetId,
    instruction: instruction.trim(),
    language: normalizeLanguage(language),
  }, LONG_TIMEOUT_MS);
}

export function confirmEdit(datasetId, editId) {
  return jsonPost("/edit/confirm", {
    dataset_id: datasetId,
    edit_id: editId,
  }, UPLOAD_TIMEOUT_MS);
}

export function cancelEdit(datasetId, editId) {
  return jsonPost("/edit/cancel", {
    dataset_id: datasetId,
    edit_id: editId,
  });
}

function getDownloadFilename(disposition, fallbackName) {
  if (!disposition) return fallbackName;
  const encodedMatch = disposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (encodedMatch) {
    try {
      return decodeURIComponent(encodedMatch[1].trim().replace(/^["']|["']$/g, ""));
    } catch {
      // Fall through to regular filename.
    }
  }
  const normalMatch = disposition.match(/filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/i);
  if (normalMatch) return (normalMatch[1] || normalMatch[2] || fallbackName).trim();
  return fallbackName;
}

async function saveResponseFile(response, fallbackName) {
  const disposition = response.headers.get("Content-Disposition") || "";
  const filename = getDownloadFilename(disposition, fallbackName);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

export async function downloadDataset(datasetId, fallbackName = "updated_data.xlsx") {
  const response = await request(
    `/datasets/${encodeURIComponent(datasetId)}/download`, {}, UPLOAD_TIMEOUT_MS
  );
  await saveResponseFile(response, fallbackName);
}

/** Export the complete validated SQL query result, not the 1,000-row UI preview. */
export async function downloadQueryResult(
  datasetId,
  generatedSql,
  datasetRevision,
  format = "xlsx"
) {
  if (!datasetId) throw new Error("Dataset ID is required.");
  if (typeof generatedSql !== "string" || !generatedSql.trim()) {
    throw new Error("Generated SQL is required to export query results.");
  }
  if (!Number.isSafeInteger(datasetRevision) || datasetRevision < 0) {
    throw new Error("Valid dataset revision is required. Run the query again.");
  }
  if (!["xlsx", "csv"].includes(format)) {
    throw new Error("Export format must be xlsx or csv.");
  }
  const response = await request("/query/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      dataset_id: datasetId,
      generated_sql: generatedSql.trim(),
      dataset_revision: datasetRevision,
      format,
    }),
  }, UPLOAD_TIMEOUT_MS);
  await saveResponseFile(response, `datapilot_query_result.${format}`);
}
