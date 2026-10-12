import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  checkBackend,
  uploadFile,
  getDataset,
  queryData,
  previewEdit,
  confirmEdit,
  cancelEdit,
  downloadDataset,
} from "./api";

import "./App.css";

const API_BASE_URL = "http://127.0.0.1:8000";

const MAX_PREVIEW_ROWS = 20;
const HEALTH_CHECK_MS = 30_000;
const NOTIFICATION_MS = 5_000;

const LOGO_SRC = `${import.meta.env.BASE_URL}logo.png`;

const EXPLORER_SUGGESTIONS = [
  "How many rows are in this dataset?",
  "Show the first 10 records",
  "Which columns have missing values?",
];

const ASSISTANT_SUGGESTIONS = [
  "Remove duplicate rows",
  "Add a new record using the existing column names",
  "Update a value where a column matches a condition",
];

const PAGE_TITLES = {
  dashboard: {
    title: "Dashboard",
    text: "Your intelligent data workspace.",
  },
  dataset: {
    title: "Dataset",
    text: "Browse your data and check its structure.",
  },
  explorer: {
    title: "Data Explorer",
    text: "Explore datasets through natural language.",
  },
  assistant: {
    title: "AI Assistant",
    text: "Make controlled changes to Excel and CSV data.",
  },
};

/* ================================
   HELPERS
================================ */

function validateFile(file) {
  if (!file || !/\.(csv|xlsx)$/i.test(file.name)) {
    throw new Error("Please select a CSV or XLSX file.");
  }

  if (file.size === 0) {
    throw new Error("This file is empty.");
  }

  if (file.size > 200 * 1024 * 1024) {
    throw new Error("Maximum file size is 200 MB.");
  }
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString();
}

function formatValue(value) {
  if (value === null || value === undefined) return "—";

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function makeId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createMessage(role, content, extra = {}) {
  return {
    id: makeId(),
    role,
    content,
    ...extra,
  };
}

/* ================================
   LOGO
================================ */

function Logo({ className = "", fallback = "✦" }) {
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <span className={`dp-logo-fallback ${className}`}>
        {fallback}
      </span>
    );
  }

  return (
    <img
      className={`dp-logo-img ${className}`}
      src={LOGO_SRC}
      alt="DataPilot AI logo"
      onError={() => setFailed(true)}
    />
  );
}

/* ================================
   DATA TABLE
================================ */

function DataTable({
  rows = [],
  emptyText = "No data available.",
}) {
  const columns = useMemo(() => {
    if (!Array.isArray(rows)) return [];

    return [
      ...new Set(
        rows.flatMap((row) => Object.keys(row))
      ),
    ];
  }, [rows]);

  if (!Array.isArray(rows) || rows.length === 0) {
    return (
      <div className="dp-empty-table">
        {emptyText}
      </div>
    );
  }

  return (
    <div className="dp-table-wrap" tabIndex={0}>
      <table className="dp-table">
        <thead>
          <tr>
            <th scope="col">#</th>

            {columns.map((column) => (
              <th key={column} scope="col">
                {column}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {rows
            .slice(0, MAX_PREVIEW_ROWS)
            .map((row, index) => (
              <tr key={index}>
                <td>{index + 1}</td>

                {columns.map((column) => (
                  <td
                    key={column}
                    title={formatValue(row[column])}
                  >
                    {formatValue(row[column])}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}

/* ================================
   COPY SQL BUTTON
================================ */

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 1500);
    } catch {
      // Clipboard may be unavailable.
    }
  }

  return (
    <button
      type="button"
      className="dp-copy-btn"
      onClick={copy}
    >
      {copied ? "Copied" : "Copy SQL"}
    </button>
  );
}

/* ================================
   MAIN APP
================================ */

function App() {
  const fileInputRef = useRef(null);
  const explorerEndRef = useRef(null);
  const assistantEndRef = useRef(null);
  const notificationTimer = useRef(null);

  const [activePage, setActivePage] = useState("dashboard");

  const [backendOnline, setBackendOnline] = useState(false);
  const [dragging, setDragging] = useState(false);

  const [dataset, setDataset] = useState(null);
  const [datasetView, setDatasetView] = useState("preview");

  const [explorerMessages, setExplorerMessages] = useState([]);
  const [assistantMessages, setAssistantMessages] = useState([]);

  const [explorerInput, setExplorerInput] = useState("");
  const [assistantInput, setAssistantInput] = useState("");

  const [pendingEdit, setPendingEdit] = useState(null);

  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notification, setNotification] = useState("");

  const busy = Boolean(loading);
  const dataReady = Boolean(dataset);

  /* ================================
     BACKEND CONNECTION
  ================================ */

  useEffect(() => {
    let mounted = true;

    async function testConnection() {
      try {
        await checkBackend();

        if (mounted) {
          setBackendOnline(true);
        }
      } catch {
        if (mounted) {
          setBackendOnline(false);
        }
      }
    }

    testConnection();

    const interval = setInterval(
      testConnection,
      HEALTH_CHECK_MS
    );

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  /* ================================
     DOCUMENT TITLE
  ================================ */

  useEffect(() => {
    document.title = `${PAGE_TITLES[activePage].title} · DataPilot AI`;
  }, [activePage]);

  /* ================================
     CHAT AUTO SCROLL
  ================================ */

  useEffect(() => {
    explorerEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [explorerMessages, loading]);

  useEffect(() => {
    assistantEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [assistantMessages, pendingEdit, loading]);



/* ================================
   PAGE & CHAT SCROLL MANAGEMENT
================================ */

// Open the website from the top.
useEffect(() => {
  const previousRestoration = window.history.scrollRestoration;

  window.history.scrollRestoration = "manual";
  window.scrollTo(0, 0);

  return () => {
    window.history.scrollRestoration = previousRestoration;
  };
}, []);

// Return to the top when switching pages.
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [activePage]);

  // Auto-scroll only inside Data Explorer chat.
  useEffect(() => {
    if (
      activePage !== "explorer" ||
      explorerMessages.length === 0
    ) {
      return;
    }

    const container = explorerEndRef.current?.closest(
      ".dp-chat-messages"
    );

    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [explorerMessages, activePage]);

// Auto-scroll only inside AI Assistant chat.
  useEffect(() => {
    if (
      activePage !== "assistant" ||
      (assistantMessages.length === 0 && !pendingEdit)
    ) {
      return;
    }

    const container = assistantEndRef.current?.closest(
      ".dp-chat-messages"
    );

    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [assistantMessages, pendingEdit, activePage]);






  /* ================================
     UNSAVED EDIT WARNING
  ================================ */

  useEffect(() => {
    if (!pendingEdit) return undefined;

    function handler(event) {
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handler);

    return () => {
      window.removeEventListener("beforeunload", handler);
    };
  }, [pendingEdit]);

  /* ================================
     NOTIFICATIONS
  ================================ */

  const notify = useCallback((message) => {
    setNotification(message);

    clearTimeout(notificationTimer.current);

    notificationTimer.current = setTimeout(() => {
      setNotification("");
    }, NOTIFICATION_MS);
  }, []);

  useEffect(() => {
    return () => {
      clearTimeout(notificationTimer.current);
    };
  }, []);

  function navigate(page) {
    setActivePage(page);
    setError("");
  }

  function clearAlerts() {
    setError("");
    setNotification("");
  }

  /* ================================
     FILE UPLOAD
  ================================ */

  async function processFile(file) {
    if (!file || busy || pendingEdit) return;

    clearAlerts();

    try {
      validateFile(file);
    } catch (err) {
      setError(err.message);
      return;
    }

    setLoading("Uploading and processing your dataset. Large files may take a few minutes...");

    try {
      const response = await uploadFile(file);

      setDataset({
        ...response,
        revision: response.revision ?? 0,
      });

      setExplorerMessages([]);
      setAssistantMessages([]);

      setPendingEdit(null);
      setDatasetView("preview");

      notify(`${file.name} uploaded successfully.`);

      setActivePage("explorer");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  async function handleUpload(event) {
    const file = event.target.files?.[0];

    event.target.value = "";

    await processFile(file);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);

    processFile(event.dataTransfer.files?.[0]);
  }

  /* ================================
     REFRESH DATASET
  ================================ */

  async function refreshDataset() {
    if (!dataset) return;

    const updated = await getDataset(dataset.dataset_id);

    setDataset((previous) => ({
      ...previous,
      ...updated,
    }));
  }

  /* ================================
     DATA EXPLORER
  ================================ */

  async function sendExplorerQuestion(text) {
    const question = text.trim();

    if (!question || !dataset || busy) return;

    clearAlerts();

    setExplorerInput("");

    setExplorerMessages((prev) => [
      ...prev,
      createMessage("user", question),
    ]);

    setLoading("Generating SQL and analyzing data...");

    try {
      const result = await queryData(
        dataset.dataset_id,
        question
      );

      setExplorerMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          result.answer || "Analysis completed.",
          {
            type: "query",
            sql: result.generated_sql,
            rows: result.data || [],
            returnedRows: result.returned_rows,
            revision: dataset.revision,
          }
        ),
      ]);
    } catch (err) {
      setExplorerMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          err.message,
          { type: "error" }
        ),
      ]);
    } finally {
      setLoading("");
    }
  }

  /* ================================
     AI ASSISTANT
  ================================ */

  async function sendAssistantInstruction(text) {
    const instruction = text.trim();

    if (
      !instruction ||
      !dataset ||
      busy ||
      pendingEdit
    ) {
      return;
    }

    clearAlerts();
    setAssistantInput("");

    setAssistantMessages((prev) => [
      ...prev,
      createMessage("user", instruction),
    ]);

    setLoading("Reviewing requested spreadsheet changes...");

    try {
      const result = await previewEdit(
        dataset.dataset_id,
        instruction
      );

      setPendingEdit(result);

      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          "I've prepared an edit preview. Please review the affected records before applying changes.",
          { type: "edit-preview" }
        ),
      ]);
    } catch (err) {
      const notAnEdit = /unsupported|ambiguous/i.test(
        err.message || ""
      );

      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          notAnEdit
            ? `${err.message}\n\nThe AI Assistant only changes data (for example: "Delete rows where Country is China" or "Change Car_Color from Red to Blue"). To view or filter records, use the Data Explorer.`
            : err.message,
          notAnEdit
            ? {
                type: "error",
                action: "explorer",
                prefill: instruction,
              }
            : { type: "error" }
        ),
      ]);
    } finally {
      setLoading("");
    }
  }

  /* ================================
     CONFIRM EDIT
  ================================ */

  async function handleConfirmEdit() {
    if (!dataset || !pendingEdit || busy) return;

    clearAlerts();
    setLoading("Applying approved changes...");

    try {
      const result = await confirmEdit(
        dataset.dataset_id,
        pendingEdit.edit_id
      );

      setPendingEdit(null);

      setDataset((previous) => ({
        ...previous,
        total_rows: result.total_rows,
        revision: result.revision,
        preview: result.preview || previous.preview,
      }));

      try {
        await refreshDataset();
      } catch (refreshError) {
        setError(
          `Edit was saved, but dataset preview refresh failed: ${refreshError.message}. Reopen the Dataset tab or upload again if needed.`
        );
      }

      setExplorerMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          `Dataset updated (revision ${result.revision}). Ask a new question to analyze the latest ${formatNumber(
            result.total_rows
          )} rows. Previous results are historical.`,
          { type: "success" }
        ),
      ]);

      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          `Changes applied successfully. Your dataset now contains ${formatNumber(
            result.total_rows
          )} rows.`,
          { type: "success" }
        ),
      ]);

      notify("Dataset updated successfully.");
    } catch (err) {
      setError(
        `${err.message} If confirmation already succeeded, refresh the dataset before retrying.`
      );
    } finally {
      setLoading("");
    }
  }

  /* ================================
     CANCEL EDIT
  ================================ */

  async function handleCancelEdit() {
    if (!dataset || !pendingEdit || busy) return;

    clearAlerts();
    setLoading("Cancelling proposed changes...");

    try {
      await cancelEdit(
        dataset.dataset_id,
        pendingEdit.edit_id
      );

      setPendingEdit(null);

      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          "Edit cancelled. Your dataset remains unchanged.",
          { type: "success" }
        ),
      ]);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  /* ================================
     DOWNLOAD EXCEL
  ================================ */

  async function handleDownload() {
    if (!dataset || busy) return;

    clearAlerts();
    setLoading("Preparing Excel file...");

    try {
      await downloadDataset(dataset.dataset_id);

      notify("Your Excel download has started.");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading("");
    }
  }

  /* ================================
     RESET / REMOVE CURRENT FILE
  ================================ */

  function handleReset() {
    if (busy || pendingEdit) return;

    setDataset(null);
    setExplorerMessages([]);
    setAssistantMessages([]);
    setExplorerInput("");
    setAssistantInput("");
    setDatasetView("preview");
    setActivePage("dashboard");

    clearAlerts();
    notify("File removed. Upload a new file to continue.");
  }

  /* ================================
     NAVIGATION
  ================================ */

  const navigation = [
    {
      id: "dashboard",
      icon: "◫",
      label: "Dashboard",
    },
    {
      id: "dataset",
      icon: "▦",
      label: "Dataset",
    },
    {
      id: "explorer",
      icon: "⌕",
      label: "Data Explorer",
    },
    {
      id: "assistant",
      icon: "✦",
      label: "AI Assistant",
    },
  ];

  /* ================================
     UPLOAD BUTTON
  ================================ */

  function renderUploadButton(
    label = "Upload Dataset"
  ) {
    return (
      <button
        type="button"
        className="dp-btn dp-btn-primary"
        onClick={() => fileInputRef.current?.click()}
        disabled={busy || Boolean(pendingEdit)}
      >
        <span aria-hidden="true">＋</span>
        {" "}
        {label}
      </button>
    );
  }

  /* ================================
     DATASET METRICS
  ================================ */

  function renderDatasetOverview() {
    if (!dataset) return null;

    return (
      <div className="dp-metrics">
        <div className="dp-metric">
          <span>Total Records</span>

          <strong>
            {formatNumber(dataset.total_rows)}
          </strong>

          <small>Rows in uploaded dataset</small>
        </div>

        <div className="dp-metric">
          <span>Data Columns</span>

          <strong>
            {formatNumber(dataset.total_columns)}
          </strong>

          <small>Automatically detected</small>
        </div>

        <div className="dp-metric">
          <span>Dataset Revision</span>

          <strong>
            {formatNumber(dataset.revision)}
          </strong>

          <small>Confirmed edits</small>
        </div>
      </div>
    );
  }

  /* ================================
     DATASET PANEL
  ================================ */

  function renderDatasetPanel() {
    if (!dataset) return null;

    return (
      <div className="dp-panel dp-dataset-panel">
        <div className="dp-panel-head">
          <div>
            <h3>Dataset Overview</h3>
            <p>{dataset.filename}</p>
          </div>

          <button
            className="dp-btn dp-btn-outline"
            type="button"
            onClick={handleDownload}
            disabled={busy}
          >
            ↓ Download Excel
          </button>
        </div>

        <div className="dp-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={datasetView === "preview"}
            className={
              datasetView === "preview"
                ? "active"
                : ""
            }
            onClick={() => setDatasetView("preview")}
          >
            Data Preview
          </button>

          <button
            type="button"
            role="tab"
            aria-selected={datasetView === "schema"}
            className={
              datasetView === "schema"
                ? "active"
                : ""
            }
            onClick={() => setDatasetView("schema")}
          >
            Schema
          </button>
        </div>

        {datasetView === "preview" ? (
          <>
            <DataTable
              rows={dataset.preview || []}
            />

            <div className="dp-table-footer">
              Showing first{" "}
              {Math.min(
                dataset.preview?.length || 0,
                MAX_PREVIEW_ROWS
              )}{" "}
              of{" "}
              {formatNumber(dataset.total_rows)}{" "}
              rows
            </div>
          </>
        ) : (
          <pre className="dp-schema">
            {dataset.schema}
          </pre>
        )}
      </div>
    );
  }

  /* ================================
     CHAT MESSAGES

     DEFAULT STATES (query results):
     Result Table  = OPEN
     Generated SQL = CLOSED
     AI Response   = CLOSED
  ================================ */

  function renderChatMessages(messages, mode) {
    if (messages.length === 0) {
      return (
        <div className="dp-chat-empty">
          <div
            className="dp-chat-empty-icon"
            aria-hidden="true"
          >
            {mode === "explorer" ? "⌕" : "✦"}
          </div>

          <h3>
            {mode === "explorer"
              ? "Ask anything about your data"
              : "What would you like to change?"}
          </h3>

          <p>
            {mode === "explorer"
              ? "Generate SQL queries, explore records and get AI-powered answers. Try a suggestion from the right panel."
              : "Describe the changes you need. You'll review them before they're applied."}
          </p>
        </div>
      );
    }

    return messages.map((message) => (
      <div
        key={message.id}
        className={`dp-message dp-message-${message.role} ${
          message.type === "error"
            ? "dp-message-error"
            : ""
        }`}
      >
        {message.type === "query" && (
          <div className="dp-query-output">
            {Number.isInteger(message.revision) &&
              message.revision !== dataset?.revision && (
                <p className="dp-chat-note">
                  Earlier result · dataset revision{" "}
                  {message.revision}. Run the question
                  again for current data.
                </p>
              )}

            {/* RESULT TABLE — OPEN BY DEFAULT */}
            <details open>
              <summary>
                View Result Table (
                {formatNumber(message.returnedRows)}{" "}
                rows)
              </summary>

              <DataTable rows={message.rows} />
            </details>

            {/* GENERATED SQL — CLOSED BY DEFAULT */}
            <details>
              <summary>
                View Generated SQL
              </summary>

              <pre className="dp-code">
                {message.sql}
              </pre>

              <CopyButton
                text={message.sql || ""}
              />
            </details>

            {/* AI RESPONSE — CLOSED BY DEFAULT */}
            <details>
              <summary>
                View AI Response
              </summary>

              <div className="dp-message-body">
                {message.content}
              </div>
            </details>
          </div>
        )}

        {/* Normal messages (user, errors, success, previews) */}
        {message.type !== "query" && (
          <>
            <div className="dp-message-label">
              {message.role === "user"
                ? "YOU"
                : "DATAPILOT AI"}
            </div>

            <div className="dp-message-body">
              {message.content}
            </div>
          </>
        )}

        {message.action === "explorer" && (
          <button
            type="button"
            className="dp-btn dp-btn-primary"
            style={{ marginTop: 12 }}
            onClick={() => {
              setExplorerInput(
                message.prefill || ""
              );

              navigate("explorer");
            }}
          >
            Ask this in Data Explorer ⌕
          </button>
        )}
      </div>
    ));
  }

  /* ================================
     EDIT REVIEW PANEL
  ================================ */

  function renderEditReview() {
    if (!pendingEdit) return null;

    return (
      <div className="dp-edit-review">
        <div className="dp-review-header">
          <div>
            <h3>Review Proposed Changes</h3>
            <p>No changes have been applied yet.</p>
          </div>

          <span className="dp-review-badge">
            Confirmation Required
          </span>
        </div>

        <div className="dp-review-metrics">
          <div>
            <span>Affected Rows</span>
            <strong>
              {formatNumber(pendingEdit.affected_rows)}
            </strong>
          </div>

          <div>
            <span>Current Rows</span>
            <strong>
              {formatNumber(pendingEdit.before_rows)}
            </strong>
          </div>

          <div>
            <span>After Changes</span>
            <strong>
              {formatNumber(pendingEdit.after_rows)}
            </strong>
          </div>
        </div>

        <details className="dp-action-details">
          <summary>
            View AI Proposed Action
          </summary>

          <pre className="dp-code">
            {JSON.stringify(
              pendingEdit.action,
              null,
              2
            )}
          </pre>
        </details>

        <h4>Affected Records Preview</h4>

        <DataTable
          rows={pendingEdit.affected_preview || []}
        />

        {pendingEdit.preview_truncated && (
          <p className="dp-warning">
            This preview is limited. Additional
            matching rows will also be affected.
          </p>
        )}

        {pendingEdit.before_after_preview?.length > 0 && (
          <details className="dp-action-details">
            <summary>
              Before / After Comparison
            </summary>

            <pre className="dp-code">
              {JSON.stringify(
                pendingEdit.before_after_preview,
                null,
                2
              )}
            </pre>
          </details>
        )}

        <div className="dp-review-actions">
          <button
            type="button"
            className="dp-btn dp-btn-outline"
            onClick={handleCancelEdit}
            disabled={busy}
          >
            Cancel Changes
          </button>

          <button
            type="button"
            className="dp-btn dp-btn-danger"
            onClick={handleConfirmEdit}
            disabled={busy}
          >
            Confirm Changes
          </button>
        </div>
      </div>
    );
  }

  /* ================================
     CHAT SIDE PANEL
  ================================ */

  function renderChatSide(mode) {
    const isExplorer = mode === "explorer";

    const suggestions = isExplorer
      ? EXPLORER_SUGGESTIONS
      : ASSISTANT_SUGGESTIONS;

    const send = isExplorer
      ? sendExplorerQuestion
      : sendAssistantInstruction;

    const locked =
      !isExplorer && Boolean(pendingEdit);

    return (
      <aside className="dp-side">
        <div className="dp-side-card">
          <h4>ACTIVE DATASET</h4>

          <div className="dp-side-stats">
            <div>
              <span>Rows</span>

              <strong>
                {formatNumber(dataset.total_rows)}
              </strong>
            </div>

            <div>
              <span>Columns</span>

              <strong>
                {formatNumber(dataset.total_columns)}
              </strong>
            </div>
          </div>
        </div>

        <div className="dp-side-card">
          <h4>TRY ASKING</h4>

          <div className="dp-chip-row">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                className="dp-chip"
                disabled={busy || locked}
                onClick={() => send(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        {dataset.schema && (
          <div className="dp-side-card dp-side-card--schema">
            <h4>SCHEMA</h4>

            <pre className="dp-side-schema">
              {dataset.schema}
            </pre>
          </div>
        )}
      </aside>
    );
  }

  /* ================================
     CHAT PANEL
  ================================ */

  function renderChat(mode) {
    const isExplorer = mode === "explorer";

    const messages = isExplorer
      ? explorerMessages
      : assistantMessages;

    const input = isExplorer
      ? explorerInput
      : assistantInput;

    const setInput = isExplorer
      ? setExplorerInput
      : setAssistantInput;

    const send = isExplorer
      ? sendExplorerQuestion
      : sendAssistantInstruction;

    const locked =
      !isExplorer && Boolean(pendingEdit);

    return (
      <div className="dp-panel dp-chat-panel">
        <div className="dp-panel-head dp-chat-head">
          <div>
            <h3>
              {isExplorer
                ? "⌕ Data Explorer"
                : "✦ AI Assistant"}
            </h3>

            <p>
              {isExplorer
                ? "Natural Language to SQL Analysis"
                : "AI-Powered Excel & CSV Editing"}
            </p>
          </div>
        </div>

        <div
          className="dp-chat-messages"
          role="log"
          aria-live="polite"
          aria-label={
            isExplorer
              ? "Explorer conversation"
              : "Assistant conversation"
          }
        >
          {renderChatMessages(
            messages,
            mode
          )}

          {!isExplorer && renderEditReview()}

          {busy && (
            <div className="dp-message dp-message-assistant dp-typing">
              <div className="dp-message-label">
                DATAPILOT AI
              </div>

              <div className="dp-message-body">
                <span className="dp-loading-spinner" />
                {loading}
              </div>
            </div>
          )}

          <div
            ref={
              isExplorer
                ? explorerEndRef
                : assistantEndRef
            }
          />
        </div>

        <form
          className="dp-chat-form"
          onSubmit={(event) => {
            event.preventDefault();
            send(input);
          }}
        >
          <div className="dp-chat-input">
            <textarea
              value={input}
              onChange={(event) => {
                setInput(event.target.value);
              }}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();

                  event.currentTarget.form?.requestSubmit();
                }
              }}
              placeholder={
                isExplorer
                  ? "Ask a question about your dataset..."
                  : "Describe the changes you want to make..."
              }
              aria-label={
                isExplorer
                  ? "Question"
                  : "Edit instruction"
              }
              maxLength={2000}
              rows={2}
              disabled={busy || locked}
            />

            <button
              className="dp-btn dp-btn-primary"
              type="submit"
              disabled={
                busy ||
                !input.trim() ||
                locked
              }
            >
              Send ↗
            </button>
          </div>

          <p className="dp-chat-note">
            {isExplorer
              ? "AI-generated SQL and answers should be verified for important decisions."
              : pendingEdit
                ? "Review, confirm or cancel your pending edit."
                : "Spreadsheet changes require your confirmation."}
          </p>
        </form>
      </div>
    );
  }

  /* ================================
     MAIN LAYOUT
  ================================ */

  const heading = PAGE_TITLES[activePage];

  return (
    <div className="dp-app">
      <a
        className="dp-skip-link"
        href="#dp-main-content"
      >
        Skip to content
      </a>

      {/* TOP NAVBAR */}

      <header className="dp-nav">
        <div className="dp-nav-inner">
          <div className="dp-brand">
            <div className="dp-brand-mark">
              <Logo />
            </div>

            <div>
              <strong>DataPilot AI</strong>
              <small>
                Intelligent Data Workspace
              </small>
            </div>
          </div>

          <nav
            className="dp-navigation"
            aria-label="Main navigation"
          >
            {navigation.map((item) => (
              <button
                key={item.id}
                type="button"
                aria-current={
                  activePage === item.id
                    ? "page"
                    : undefined
                }
                className={`dp-nav-item ${
                  activePage === item.id
                    ? "dp-nav-active"
                    : ""
                }`}
                onClick={() => navigate(item.id)}
              >
                <span
                  className="dp-nav-icon"
                  aria-hidden="true"
                >
                  {item.icon}
                </span>

                {item.label}
              </button>
            ))}
          </nav>

          <div className="dp-nav-actions">
            {dataReady ? (
              <div
                className="dp-active-file"
                title={dataset.filename}
              >
                <span
                  className="dp-active-file-icon"
                  aria-hidden="true"
                >
                  ▦
                </span>

                <span className="dp-active-file-name">
                  {dataset.filename}
                </span>

                <button
                  type="button"
                  className="dp-active-file-remove"
                  aria-label="Remove current file"
                  title="Remove file"
                  onClick={handleReset}
                  disabled={busy || Boolean(pendingEdit)}
                >
                  ×
                </button>
              </div>
            ) : (
              <span
                className={`dp-status-pill ${
                  backendOnline
                    ? ""
                    : "is-offline"
                }`}
                title={
                  import.meta.env.DEV
                    ? API_BASE_URL
                    : undefined
                }
              >
                <i />
                {backendOnline
                  ? "Connected"
                  : "Offline"}
              </span>
            )}

            {dataReady && (
              <button
                type="button"
                className="dp-btn dp-btn-outline"
                onClick={handleDownload}
                disabled={busy}
              >
                ↓ Download
              </button>
            )}

            {renderUploadButton("Upload")}
          </div>
        </div>
      </header>

      {/* PAGE BANNER */}

      {dataReady && (
        <section className="dp-banner">
          <div className="dp-banner-inner">
            <div>
              <span className="dp-eyebrow">
                DATAPILOT AI / WORKSPACE
              </span>

              <h1>{heading.title}</h1>
              <p>{heading.text}</p>
            </div>
          </div>
        </section>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx"
        hidden
        onChange={handleUpload}
      />

      <main
        className={`dp-main ${
          dataReady ? "has-banner" : ""
        }`}
        id="dp-main-content"
      >
        {!backendOnline && (
          <div
            className="dp-alert dp-alert-warning"
            role="status"
          >
            <span>
              The server is not reachable right
              now. We'll keep retrying automatically.
            </span>
          </div>
        )}

        {error && (
          <div
            className="dp-alert dp-alert-error"
            role="alert"
          >
            <span>{error}</span>

            <button
              type="button"
              aria-label="Dismiss error"
              onClick={() => setError("")}
            >
              ×
            </button>
          </div>
        )}

        {notification && (
          <div
            className="dp-alert dp-alert-success"
            role="status"
          >
            <span>{notification}</span>

            <button
              type="button"
              aria-label="Dismiss message"
              onClick={() => setNotification("")}
            >
              ×
            </button>
          </div>
        )}

        {loading &&
          !(
            dataReady &&
            (
              activePage === "explorer" ||
              activePage === "assistant"
            )
          ) && (
            <div
              className="dp-loading-bar"
              role="status"
              aria-live="polite"
            >
              <span className="dp-loading-spinner" />
              {loading}
            </div>
          )}

        {/* HERO — NO DATASET */}

        {!dataReady && (
          <section
            className={`dp-hero dp-animate-in ${
              dragging
                ? "dp-hero-dragging"
                : ""
            }`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => {
              setDragging(false);
            }}
            onDrop={handleDrop}
          >
            <div className="dp-hero-top">
              <div className="dp-hero-copy">
                <h2>
                  Ask your spreadsheet questions.
                  Get answers in seconds.
                </h2>

                <p>
                  Upload a CSV or Excel file, ask
                  in plain English, and review
                  every change before it is applied.
                </p>

                <div className="dp-dropzone">
                  <div
                    className="dp-dropzone-icon"
                    aria-hidden="true"
                  >
                    ↑
                  </div>

                  <div className="dp-dropzone-text">
                    <strong>
                      {dragging
                        ? "Drop to upload"
                        : "Drop your file here"}
                    </strong>

                    <span>
                      CSV or XLSX, up to 200 MB
                    </span>
                  </div>

                  {renderUploadButton("Choose file")}
                </div>
              </div>

              <div
                className="dp-hero-preview"
                aria-hidden="true"
              >
                <div className="dp-pv-card dp-pv-main">
                  <div className="dp-pv-bar">
                    <i />
                    <i />
                    <i />

                    <span>
                      Example: Data Explorer
                    </span>
                  </div>

                  <div className="dp-pv-question">
                    Which region had the highest
                    sales in Q3?
                  </div>

                  <pre className="dp-pv-sql">
{`SELECT region, SUM(sales) AS total
FROM data
WHERE quarter = 'Q3'
GROUP BY region
ORDER BY total DESC;`}
                  </pre>

                  <table className="dp-pv-table">
                    <thead>
                      <tr>
                        <th>region</th>
                        <th>total</th>
                      </tr>
                    </thead>

                    <tbody>
                      <tr>
                        <td>North</td>
                        <td>482,300</td>
                      </tr>

                      <tr>
                        <td>West</td>
                        <td>391,750</td>
                      </tr>

                      <tr>
                        <td>South</td>
                        <td>276,040</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <div className="dp-pv-card dp-pv-edit">
                  <span className="dp-review-badge">
                    Confirmation required
                  </span>

                  <strong>
                    Remove duplicate rows
                  </strong>

                  <small>
                    12 rows will be affected.
                    Nothing changes until you confirm.
                  </small>

                  <div className="dp-pv-actions">
                    <span className="dp-pv-btn">
                      Cancel
                    </span>

                    <span className="dp-pv-btn dp-pv-btn-primary">
                      Confirm
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="dp-hero-section-title">
              How it works
            </div>

            <ol className="dp-steps">
              <li>
                <span className="dp-step-num">
                  1
                </span>

                <strong>
                  Upload your file
                </strong>

                <p>
                  Add a CSV or Excel file.
                  Columns and types are detected
                  for you.
                </p>
              </li>

              <li>
                <span className="dp-step-num">
                  2
                </span>

                <strong>
                  Ask or describe a change
                </strong>

                <p>
                  Type a question to analyze data,
                  or an instruction to edit it.
                </p>
              </li>

              <li>
                <span className="dp-step-num">
                  3
                </span>

                <strong>
                  Review and download
                </strong>

                <p>
                  Check the affected rows, confirm,
                  then download the updated Excel file.
                </p>
              </li>
            </ol>

            <div className="dp-hero-features">
              <div>
                <strong>
                  ⌕ Data Explorer
                </strong>

                <p>
                  Get answers from your data with
                  generated SQL and result tables.
                </p>

                <em>
                  "Show the top 10 customers by revenue"
                </em>
              </div>

              <div>
                <strong>
                  ✦ AI Assistant
                </strong>

                <p>
                  Add, update or delete records.
                  You approve every change.
                </p>

                <em>
                  "Delete rows where status is cancelled"
                </em>
              </div>
            </div>
          </section>
        )}

        {/* DASHBOARD */}

        {dataReady &&
          activePage === "dashboard" && (
            <div className="dp-animate-in">
              {renderDatasetOverview()}

              <div className="dp-dashboard-grid">
                <button
                  type="button"
                  className="dp-feature-card"
                  onClick={() => navigate("dataset")}
                >
                  <div className="dp-feature-icon">
                    ▦
                  </div>

                  <h2>Dataset</h2>

                  <p>
                    Browse your rows, check the
                    schema and download the latest
                    Excel file.
                  </p>

                  <span>
                    Open Dataset →
                  </span>
                </button>

                <button
                  type="button"
                  className="dp-feature-card"
                  onClick={() => navigate("explorer")}
                >
                  <div className="dp-feature-icon">
                    ⌕
                  </div>

                  <h2>Data Explorer</h2>

                  <p>
                    Analyze uploaded datasets using
                    natural language, SQL queries
                    and structured results.
                  </p>

                  <span>
                    Open Data Explorer →
                  </span>
                </button>

                <button
                  type="button"
                  className="dp-feature-card"
                  onClick={() => navigate("assistant")}
                >
                  <div className="dp-feature-icon">
                    ✦
                  </div>

                  <h2>AI Assistant</h2>

                  <p>
                    Add, update or delete spreadsheet
                    records with a review and
                    confirmation workflow.
                  </p>

                  <span>
                    Open AI Assistant →
                  </span>
                </button>
              </div>
            </div>
          )}

        {/* DATASET PAGE */}

        {dataReady &&
          activePage === "dataset" && (
            <div className="dp-animate-in">
              {renderDatasetOverview()}
              {renderDatasetPanel()}
            </div>
          )}

        {/* EXPLORER / AI ASSISTANT */}

        {dataReady &&
          (
            activePage === "explorer" ||
            activePage === "assistant"
          ) && (
            <div className="dp-chat-page dp-animate-in">
              {renderChat(activePage)}
              {renderChatSide(activePage)}
            </div>
          )}
      </main>

      {/* FOOTER */}

      <footer className="dp-footer">
        <div className="dp-footer-inner">
          <span>
            © {new Date().getFullYear()}{" "}
            <strong>DataPilot AI</strong>
          </span>

          <span>
            Intelligent Data Analysis &
            Spreadsheet Editing
          </span>
        </div>
      </footer>
    </div>
  );
}

export default App;
