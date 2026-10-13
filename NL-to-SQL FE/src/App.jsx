import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  API_BASE_URL,
  checkBackend,
  uploadFile,
  createNewProject,
  getDataset,
  getDatasetRows,
  queryData,
  previewEdit,
  confirmEdit,
  cancelEdit,
  downloadDataset,
  downloadQueryResult,
} from "./api";
import "./App.css";
import { useTranslation } from "react-i18next";
import { LANGUAGE_OPTIONS, setAppLanguage } from "./i18n";
const MAX_PREVIEW_ROWS = 1_000;
const HEALTH_CHECK_MS = 30_000;
const NOTIFICATION_MS = 5_000;
const LOGO_SRC = `${import.meta.env.BASE_URL}logo.png`;
const EXPLORER_SUGGESTION_KEYS = ["countRows", "firstRecords", "missingValues"];
const ASSISTANT_SUGGESTION_KEYS = ["removeDuplicates", "addRecord", "updateValue"];
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
    if (value === null || value === undefined) {
      return "—";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    const text = String(value);
    // Show date only when time is midnight.
    // Preserve non-midnight timestamps.
    const midnightDate = text.match(
      /^(\d{4}-\d{2}-\d{2})[ T]00:00:00(?:\.0+)?(?:Z)?$/
    );
    if (midnightDate) {
      return midnightDate[1];
    }
    return text;
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
  emptyText,
}) {
  const { t } = useTranslation();
  const emptyMessage = emptyText ?? t("dataset.noData");
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
          {emptyMessage}
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
/* Virtual dataset viewer: paginated fetch, bounded DOM, every row accessible. */
const VIRTUAL_ROW_HEIGHT = 40;
const VIRTUAL_PAGE_SIZE = 200;
const VIRTUAL_OVERSCAN = 8;
const VIRTUAL_VIEW_HEIGHT = 520;
function VirtualDatasetTable({ dataset }) {
  const { t } = useTranslation();
  const scrollRef = useRef(null);
  const cache = useRef(new Map());
  const inflight = useRef(new Map());
  const mounted = useRef(false);
  const [scrollTop, setScrollTop] = useState(0);
  const [version, setVersion] = useState(0);
  const [loadError, setLoadError] = useState("");
  const [jumpTo, setJumpTo] = useState("");
  const count = dataset.total_rows || 0;
  const columns = (dataset.columns || []).map((col) => typeof col === "string" ? col : col.name);
  const firstVisible = Math.min(Math.max(0, Math.floor(scrollTop / VIRTUAL_ROW_HEIGHT)), Math.max(0, count - 1));
  const start = Math.max(0, firstVisible - VIRTUAL_OVERSCAN);
  const end = Math.min(count, firstVisible + Math.ceil(VIRTUAL_VIEW_HEIGHT / VIRTUAL_ROW_HEIGHT) + VIRTUAL_OVERSCAN);
  const firstPage = Math.floor(start / VIRTUAL_PAGE_SIZE);
  const lastPage = Math.floor(Math.max(start, end - 1) / VIRTUAL_PAGE_SIZE);
  useEffect(() => {
    mounted.current = true;
    cache.current.clear();
    inflight.current.clear();
    setScrollTop(0);
    setLoadError("");
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
    return () => {
      mounted.current = false;
      for (const controller of inflight.current.values()) controller.abort();
      inflight.current.clear();
      cache.current.clear();
    };
  }, [dataset.dataset_id, dataset.revision]);
  useEffect(() => {
    if (!count) return;
    for (let page = firstPage; page <= lastPage; page += 1) {
      if (cache.current.has(page) || inflight.current.has(page)) continue;
      const controller = new AbortController();
      inflight.current.set(page, controller);
      getDatasetRows(dataset.dataset_id, page * VIRTUAL_PAGE_SIZE, VIRTUAL_PAGE_SIZE, { signal: controller.signal })
        .then((result) => {
          if (!mounted.current) return;
          if (result.revision !== dataset.revision) {
            setLoadError("The dataset changed. Please reopen this tab to refresh the rows.");
            return;
          }
          cache.current.set(page, result.rows || []);
          // Keep memory bounded even when scrolling a very large dataset.
          if (cache.current.size > 40) {
            for (const key of cache.current.keys()) {
              if (Math.abs(key - page) > 15) cache.current.delete(key);
              if (cache.current.size <= 30) break;
            }
          }
          setLoadError("");
          setVersion((previous) => previous + 1);
        })
        .catch((error) => {
          if (mounted.current && error?.name !== "AbortError") setLoadError(error.message || "Could not load dataset rows.");
        })
        .finally(() => inflight.current.delete(page));
    }
  }, [dataset.dataset_id, dataset.revision, count, firstPage, lastPage]);
  function goToRow(event) {
    event.preventDefault();
    const row = Number(jumpTo);
    if (!Number.isInteger(row) || row < 1 || row > count) return;
    if (scrollRef.current) scrollRef.current.scrollTop = (row - 1) * VIRTUAL_ROW_HEIGHT;
    setScrollTop((row - 1) * VIRTUAL_ROW_HEIGHT);
  }
  if (count === 0) return <div className="dp-empty-table">{t("dataset.noData")}</div>;
  const visibleRows = [];
  for (let index = start; index < end; index += 1) {
    const page = Math.floor(index / VIRTUAL_PAGE_SIZE);
    const row = cache.current.get(page)?.[index % VIRTUAL_PAGE_SIZE];
    visibleRows.push(
      <tr key={index} style={{ height: VIRTUAL_ROW_HEIGHT }}>
        <td style={{ whiteSpace: "nowrap" }}>{index + 1}</td>
        {columns.map((column) => (
          <td key={column} title={row ? formatValue(row[column]) : "Loading..."} style={{ whiteSpace: "nowrap", maxWidth: 340, overflow: "hidden", textOverflow: "ellipsis" }}>
            {row ? formatValue(row[column]) : "…"}
          </td>
        ))}
      </tr>
    );
  }
  // Read current cache on every completed fetch, without creating all 100k DOM rows.
  void version;
  return (
    <div className="dp-virtual-dataset">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap", marginBottom: 10 }}>
        <span>{formatNumber(count)} total rows · Scroll to view all records</span>
        <form onSubmit={goToRow} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input type="number" min="1" max={count} value={jumpTo} onChange={(event) => setJumpTo(event.target.value)} placeholder="Row number" aria-label="Jump to row number" style={{ width: 120, padding: "7px 9px", border: "1px solid #cdd6e8", borderRadius: 8 }} />
          <button type="submit" className="dp-btn dp-btn-outline" disabled={!jumpTo}>Go to row</button>
        </form>
      </div>
      {loadError && <p role="alert" className="dp-warning">{loadError}</p>}
      <div ref={scrollRef} className="dp-table-wrap dp-virtual-scroll" tabIndex={0} onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)} style={{ height: VIRTUAL_VIEW_HEIGHT, maxHeight: "65vh", overflow: "auto", overscrollBehavior: "contain" }}>
        <table className="dp-table" style={{ tableLayout: "auto", minWidth: "100%", borderCollapse: "separate", borderSpacing: 0 }}>
          <thead style={{ position: "sticky", top: 0, zIndex: 2 }}>
            <tr><th scope="col">#</th>{columns.map((column) => <th scope="col" key={column}>{column}</th>)}</tr>
          </thead>
          <tbody>
            {start > 0 && <tr aria-hidden="true"><td colSpan={columns.length + 1} style={{ padding: 0, height: start * VIRTUAL_ROW_HEIGHT, border: 0 }} /></tr>}
            {visibleRows}
            {end < count && <tr aria-hidden="true"><td colSpan={columns.length + 1} style={{ padding: 0, height: (count - end) * VIRTUAL_ROW_HEIGHT, border: 0 }} /></tr>}
          </tbody>
        </table>
      </div>
      <div className="dp-table-footer">Rows {formatNumber(start + 1)}–{formatNumber(end)} of {formatNumber(count)}</div>
    </div>
  );
}
/* ================================
   COPY SQL BUTTON
================================ */
function CopyButton({ text }) {
  const { t } = useTranslation();
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
      {copied ? t("chat.copied") : t("chat.copySql")}
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
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language || "en";
  const [languageOpen, setLanguageOpen] = useState(false);
  const [languageSearch, setLanguageSearch] = useState("");
  const languageSearchRef = useRef(null);
  const languageDialogRef = useRef(null);
  const languageChoices = LANGUAGE_OPTIONS.filter((item) =>
    `${item.name} ${item.nativeName} ${item.code}`.toLocaleLowerCase().includes(languageSearch.trim().toLocaleLowerCase())
  );
  useEffect(() => {
    if (!languageOpen) return;
    const previousFocus = document.activeElement;
    languageSearchRef.current?.focus();
    function onEscape(event) {
      if (event.key === "Escape") setLanguageOpen(false);
    }
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("keydown", onEscape);
      previousFocus?.focus?.();
    };
  }, [languageOpen]);
  async function chooseLanguage(code) {
    const applied = await setAppLanguage(code);
    if (applied) {
      setLanguageOpen(false);
      setLanguageSearch("");
    }
  }
  const [backendOnline, setBackendOnline] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [dataset, setDataset] = useState(null);
  const [projectOpen, setProjectOpen] = useState(false);
  const [projectName, setProjectName] = useState("");
  const [projectColumns, setProjectColumns] = useState([
    { id: makeId(), name: "", type: "text" },
  ]);
  const [projectError, setProjectError] = useState("");
  const projectNameRef = useRef(null);
  const [datasetView, setDatasetView] = useState("preview");
  const [explorerMessages, setExplorerMessages] = useState([]);
  const [assistantMessages, setAssistantMessages] = useState([]);
  const [explorerInput, setExplorerInput] = useState("");
  const [assistantInput, setAssistantInput] = useState("");
  const [pendingEdit, setPendingEdit] = useState(null);
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const [notification, setNotification] = useState("");
  const [exportingResult, setExportingResult] = useState("");
  const [exportErrors, setExportErrors] = useState({});
  function localizeError(message) {
    if (message === "Please select a CSV or XLSX file.") return t("validation.selectFile");
    if (message === "This file is empty.") return t("validation.emptyFile");
    if (message === "Maximum file size is 200 MB.") return t("validation.fileTooLarge", { size: 200 });
    return message;
  }
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
    document.title = `${t(`page.${activePage}.title`)} · DataPilot AI`;
  }, [activePage, t]);
  /* ================================
     PAGE & CHAT SCROLL MANAGEMENT
  ================================ */
  // Keep outer page at the top on initial load and navigation.
  useEffect(() => {
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    window.scrollTo(0, 0);
    return () => {
      window.history.scrollRestoration = previous;
    };
  }, []);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [activePage]);
  // Scroll only the chat area, never the whole webpage.
  useEffect(() => {
    if (activePage !== "explorer" || explorerMessages.length === 0) return;
    const container = explorerEndRef.current?.closest(".dp-chat-messages");
    if (container) container.scrollTop = container.scrollHeight;
  }, [explorerMessages, activePage]);
  useEffect(() => {
    if (activePage !== "assistant" || (assistantMessages.length === 0 && !pendingEdit)) return;
    const container = assistantEndRef.current?.closest(".dp-chat-messages");
    if (container) container.scrollTop = container.scrollHeight;
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
     START NEW PROJECT
  ================================ */
  function openNewProject() {
    if (busy || pendingEdit) return;
    setProjectName("");
    setProjectColumns([{ id: makeId(), name: "", type: "text" }]);
    setProjectError("");
    setProjectOpen(true);
  }
  useEffect(() => {
    if (!projectOpen) return;
    const previousFocus = document.activeElement;
    projectNameRef.current?.focus();
    const onEscape = (event) => {
      if (event.key === "Escape" && !loading) setProjectOpen(false);
    };
    document.addEventListener("keydown", onEscape);
    return () => {
      document.removeEventListener("keydown", onEscape);
      previousFocus?.focus?.();
    };
  }, [projectOpen, loading]);
  function editProjectColumn(id, field, value) {
    setProjectColumns((previous) => previous.map((column) =>
      column.id === id ? { ...column, [field]: value } : column
    ));
    setProjectError("");
  }
  async function handleCreateProject(event) {
    event.preventDefault();
    if (busy || pendingEdit) return;
    setProjectError("");
    try {
      const name = projectName.trim();
      const columns = projectColumns.map(({ name: columnName, type }) => ({
        name: columnName.trim(),
        type,
      }));
      if (!name) throw new Error(t("project.nameRequired", { defaultValue: "Enter a project name." }));
      if (!columns.length || columns.some((column) => !column.name)) {
        throw new Error(t("project.columnsRequired", { defaultValue: "Enter a name for every column." }));
      }
      const normalized = columns.map((column) => column.name.replace(/ /g, "_").toLocaleLowerCase());
      if (new Set(normalized).size !== normalized.length) {
        throw new Error(t("project.duplicateColumns", { defaultValue: "Column names must be unique." }));
      }
      setLoading(t("project.creating", { defaultValue: "Creating project..." }));
      const response = await createNewProject(name, columns);
      setDataset({ ...response, revision: response.revision ?? 0 });
      setExplorerMessages([]);
      setExportErrors({});
      setAssistantMessages([]);
      setExplorerInput("");
      setAssistantInput("");
      setPendingEdit(null);
      setDatasetView("preview");
      setProjectOpen(false);
      clearAlerts();
      notify(t("project.created", { defaultValue: "Project created. Use AI Assistant to add your first record." }));
      setActivePage("assistant");
    } catch (error) {
      setProjectError(error.message || "Could not create project.");
    } finally {
      setLoading("");
    }
  }
  function renderNewProjectButton() {
    return (
      <button
        type="button"
        className="dp-btn dp-btn-primary dp-btn-new-project"
        onClick={openNewProject}
        disabled={busy || Boolean(pendingEdit)}
        title={t("project.start", { defaultValue: "Start New Project" })}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 8,
          whiteSpace: "nowrap",
          background: "#10B981",
          color: "#ffffff",
          border: "1px solid #10B981",
        }}
      >
        <span aria-hidden="true">＋</span>
        {t("project.start", { defaultValue: "Start New Project" })}
      </button>
    );
  }
  function renderNewProjectDialog() {
    if (!projectOpen) return null;
    const label = (key, fallback) => t(`project.${key}`, { defaultValue: fallback });
    return (
      <div
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && !busy) setProjectOpen(false);
        }}
        style={{ position: "fixed", inset: 0, zIndex: 10020, background: "rgba(9,16,42,.62)", display: "grid", placeItems: "center", padding: 16 }}
      >
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="dp-new-project-title"
          style={{ width: "min(100%,620px)", maxHeight: "90vh", overflowY: "auto", background: "#fff", color: "#172044", borderRadius: 18, padding: "clamp(18px,3vw,30px)", boxShadow: "0 25px 80px rgba(0,0,0,.26)" }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", gap: 12 }}>
            <div>
              <h2 id="dp-new-project-title" style={{ margin: 0, fontSize: 24 }}>{label("start", "Start New Project")}</h2>
              <p style={{ margin: "7px 0 20px", color: "#64708b" }}>{label("description", "Create a dataset from scratch, then add records using AI Assistant.")}</p>
            </div>
            <button type="button" onClick={() => setProjectOpen(false)} disabled={busy} aria-label={t("common.close")} style={{ border: 0, background: "transparent", fontSize: 28, color: "#172044", cursor: "pointer" }}>×</button>
          </div>
          <form onSubmit={handleCreateProject}>
            <label htmlFor="dp-project-name" style={{ display: "block", fontWeight: 600, marginBottom: 7 }}>{label("name", "Project name")}</label>
            <input
              id="dp-project-name"
              ref={projectNameRef}
              value={projectName}
              onChange={(event) => { setProjectName(event.target.value); setProjectError(""); }}
              maxLength={100}
              required
              disabled={busy}
              placeholder={label("namePlaceholder", "e.g. Employee Management")}
              style={{ width: "100%", padding: 12, border: "1px solid #cdd6e8", borderRadius: 10, marginBottom: 20, boxSizing: "border-box" }}
            />
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
              <strong>{label("columns", "Dataset columns")}</strong>
              <small style={{ color: "#64708b" }}>{projectColumns.length}/100</small>
            </div>
            <div style={{ display: "grid", gap: 10 }}>
              {projectColumns.map((column, index) => (
                <div key={column.id} style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) minmax(110px,150px) auto", gap: 9, alignItems: "center" }}>
                  <input
                    value={column.name}
                    onChange={(event) => editProjectColumn(column.id, "name", event.target.value)}
                    maxLength={128}
                    required
                    disabled={busy}
                    aria-label={`${label("columnName", "Column name")} ${index + 1}`}
                    placeholder={`${label("columnName", "Column name")} ${index + 1}`}
                    style={{ minWidth: 0, width: "100%", boxSizing: "border-box", padding: 11, border: "1px solid #cdd6e8", borderRadius: 9 }}
                  />
                  <select
                    value={column.type}
                    onChange={(event) => editProjectColumn(column.id, "type", event.target.value)}
                    disabled={busy}
                    aria-label={`${label("dataType", "Data type")} ${index + 1}`}
                    style={{ width: "100%", minWidth: 0, padding: 11, border: "1px solid #cdd6e8", borderRadius: 9 }}
                  >
                    <option value="text">{label("text", "Text")}</option>
                    <option value="integer">{label("integer", "Integer")}</option>
                    <option value="decimal">{label("decimal", "Decimal")}</option>
                    <option value="boolean">{label("boolean", "Boolean")}</option>
                    <option value="date">{label("date", "Date")}</option>
                  </select>
                  <button
                    type="button"
                    onClick={() => setProjectColumns((previous) => previous.filter((item) => item.id !== column.id))}
                    disabled={busy || projectColumns.length === 1}
                    aria-label={`${label("removeColumn", "Remove column")} ${index + 1}`}
                    title={label("removeColumn", "Remove column")}
                    style={{ padding: "8px 12px", border: "1px solid #d6ddec", borderRadius: 9, background: "#fff", color: "#a12f40", cursor: "pointer" }}
                  >×</button>
                </div>
              ))}
            </div>
            <button
              type="button"
              className="dp-btn dp-btn-outline"
              style={{ marginTop: 14 }}
              disabled={busy || projectColumns.length >= 100}
              onClick={() => setProjectColumns((previous) => [...previous, { id: makeId(), name: "", type: "text" }])}
            >＋ {label("addColumn", "Add column")}</button>
            {projectError && <p role="alert" style={{ color: "#ad2843", marginTop: 12 }}>{projectError}</p>}
            <div style={{ display: "flex", justifyContent: "end", gap: 10, marginTop: 24, flexWrap: "wrap" }}>
              <button type="button" className="dp-btn dp-btn-outline" onClick={() => setProjectOpen(false)} disabled={busy}>{t("common.cancel")}</button>
              <button type="submit" className="dp-btn dp-btn-primary" disabled={busy || !projectName.trim()}>
                {busy ? label("creating", "Creating project...") : label("create", "Create Project")}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
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
      setError(localizeError(err.message));
      return;
    }
    setLoading(t("messages.loadingUpload"));
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
      notify(t("messages.uploadSuccess", { filename: file.name }));
      setActivePage("explorer");
    } catch (err) {
      setError(localizeError(err.message));
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
    setLoading(t("messages.loadingQuery"));
    try {
      const result = await queryData(
        dataset.dataset_id,
        question,
        language
      );
      setExplorerMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          result.answer || t("messages.analysisCompleted"),
          {
            type: "query",
            sql: result.generated_sql,
            rows: result.data || [],
            returnedRows: result.returned_rows,
            revision: result.dataset_revision ?? dataset.revision,
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
  async function handleQueryExport(message, format) {
    if (!dataset || exportingResult) return;
    const exportKey = `${message.id}:${format}`;
    setExportErrors((previous) => ({ ...previous, [message.id]: "" }));
    if (message.revision !== dataset.revision) {
      setExportErrors((previous) => ({
        ...previous,
        [message.id]: "Dataset has changed. Run the query again before exporting.",
      }));
      return;
    }
    setExportingResult(exportKey);
    try {
      await downloadQueryResult(
        dataset.dataset_id,
        message.sql,
        message.revision,
        format
      );
    } catch (error) {
      setExportErrors((previous) => ({
        ...previous,
        [message.id]: error.message || "Could not export the query result.",
      }));
    } finally {
      setExportingResult("");
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
    setLoading(t("messages.loadingEdit"));
    try {
      const result = await previewEdit(
        dataset.dataset_id,
        instruction,
        language
      );
      setPendingEdit(result);
      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          t("messages.editPreviewReady"),
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
            ? `${err.message}\n\n${t("messages.editOnlyInstruction")}`
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
    setLoading(t("messages.loadingConfirm"));
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
          t("messages.editRefreshFailed", { error: refreshError.message })
        );
      }
      setExplorerMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          t("messages.editRevision", { revision: result.revision, count: formatNumber(result.total_rows) }),
          { type: "success" }
        ),
      ]);
      setAssistantMessages((prev) => [
        ...prev,
        createMessage(
          "assistant",
          t("messages.editApplied", { count: formatNumber(result.total_rows) }),
          { type: "success" }
        ),
      ]);
      notify(t("messages.datasetUpdated"));
    } catch (err) {
      setError(
        t("messages.editConfirmError", { error: err.message })
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
    setLoading(t("messages.loadingCancel"));
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
          t("messages.editCancelled"),
          { type: "success" }
        ),
      ]);
    } catch (err) {
      setError(localizeError(err.message));
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
    setLoading(t("messages.loadingDownload"));
    try {
      await downloadDataset(dataset.dataset_id);
      notify(t("messages.downloadStarted"));
    } catch (err) {
      setError(localizeError(err.message));
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
    notify(t("messages.fileRemoved"));
  }
  /* ================================
     NAVIGATION
  ================================ */
  const navigation = [
    {
      id: "dashboard",
      icon: "◫",
      label: t("nav.dashboard"),
    },
    {
      id: "dataset",
      icon: "▦",
      label: t("nav.dataset"),
    },
    {
      id: "explorer",
      icon: "⌕",
      label: t("nav.explorer"),
    },
    {
      id: "assistant",
      icon: "✦",
      label: t("nav.assistant"),
    },
  ];
  /* ================================
     UPLOAD BUTTON
  ================================ */
  function renderUploadButton(
    label = t("nav.upload")
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
          <span>{t("metrics.totalRecords")}</span>
          <strong>
            {formatNumber(dataset.total_rows)}
          </strong>
          <small>{t("metrics.rowsDescription")}</small>
        </div>
        <div className="dp-metric">
          <span>{t("metrics.dataColumns")}</span>
          <strong>
            {formatNumber(dataset.total_columns)}
          </strong>
          <small>{t("metrics.columnsDescription")}</small>
        </div>
        <div className="dp-metric">
          <span>{t("metrics.revision")}</span>
          <strong>
            {formatNumber(dataset.revision)}
          </strong>
          <small>{t("metrics.confirmedEdits")}</small>
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
            <h3>{t("dataset.overview")}</h3>
            <p>{dataset.filename}</p>
          </div>
          <button
            className="dp-btn dp-btn-outline"
            type="button"
            onClick={handleDownload}
            disabled={busy}
          >{t("dataset.downloadExcel")}</button>
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
          >{t("dataset.preview")}</button>
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
          >{t("dataset.schema")}</button>
        </div>
        {datasetView === "preview" ? (
          <>
            <VirtualDatasetTable key={`${dataset.dataset_id}:${dataset.revision}`} dataset={dataset} />
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
              ? t("chat.askAboutData")
              : t("chat.changeData")}
          </h3>
          <p>
            {mode === "explorer"
              ? t("chat.explorerEmptyDescription")
              : t("chat.assistantEmptyDescription")}
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
                  {t("chat.historicalResult", { revision: message.revision })}
                </p>
              )}
            {/* RESULT TABLE — OPEN BY DEFAULT */}
            <details open className="dp-query-result-details" style={{ position: "relative" }}>
              <summary style={{ minHeight: 45, display: "list-item", paddingRight: 320 }}>
                {t("chat.resultTable", { count: formatNumber(message.returnedRows) })}
              </summary>
              <style>{`@media (max-width: 700px) {
                .dp-query-result-details > summary { padding-right: 0 !important; }
                .dp-query-result-details > .dp-query-export-actions {
                  position: static !important;
                  justify-content: flex-end !important;
                  margin: 8px 0 12px !important;
                }
              }`}</style>
              <div className="dp-query-export-actions" style={{
                position: "absolute", top: 3, right: 10, display: "flex",
                alignItems: "center", justifyContent: "flex-end", gap: 10,
                flexWrap: "wrap", margin: 0
              }}>
                <button
                  type="button"
                  className="dp-btn dp-btn-primary"
                  style={{ background: "#10B981", borderColor: "#10B981", color: "#ffffff" }}
                  onClick={() => handleQueryExport(message, "xlsx")}
                  disabled={Boolean(exportingResult) || message.revision !== dataset?.revision}
                >
                  {exportingResult === `${message.id}:xlsx` ? "Exporting..." : "↓ Download Excel"}
                </button>
                <button
                  type="button"
                  className="dp-btn dp-btn-outline"
                  style={{ borderColor: "#10B981", color: "#047857" }}
                  onClick={() => handleQueryExport(message, "csv")}
                  disabled={Boolean(exportingResult) || message.revision !== dataset?.revision}
                >
                  {exportingResult === `${message.id}:csv` ? "Exporting..." : "↓ Download CSV"}
                </button>
              </div>
              {exportErrors[message.id] && (
                <p role="alert" className="dp-warning">{exportErrors[message.id]}</p>
              )}
              <DataTable rows={message.rows} />
            </details>
            {/* GENERATED SQL — CLOSED BY DEFAULT */}
            <details>
              <summary>{t("chat.generatedSql")}</summary>
              <pre className="dp-code">
                {message.sql}
              </pre>
              <CopyButton
                text={message.sql || ""}
              />
            </details>
            {/* AI RESPONSE — CLOSED BY DEFAULT */}
            <details>
              <summary>{t("chat.aiResponse")}</summary>
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
                ? t("chat.you")
                : t("chat.ai")}
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
          >{t("chat.askInExplorer")}</button>
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
            <h3>{t("edit.reviewTitle")}</h3>
            <p>{t("edit.notApplied")}</p>
          </div>
          <span className="dp-review-badge">{t("edit.confirmationRequired")}</span>
        </div>
        <div className="dp-review-metrics">
          <div>
            <span>{t("edit.affectedRows")}</span>
            <strong>
              {formatNumber(pendingEdit.affected_rows)}
            </strong>
          </div>
          <div>
            <span>{t("edit.currentRows")}</span>
            <strong>
              {formatNumber(pendingEdit.before_rows)}
            </strong>
          </div>
          <div>
            <span>{t("edit.afterChanges")}</span>
            <strong>
              {formatNumber(pendingEdit.after_rows)}
            </strong>
          </div>
        </div>
        <details className="dp-action-details">
          <summary>{t("edit.proposedAction")}</summary>
          <pre className="dp-code">
            {JSON.stringify(
              pendingEdit.action,
              null,
              2
            )}
          </pre>
        </details>
        <h4>{t("edit.affectedPreview")}</h4>
        <DataTable
          rows={pendingEdit.affected_preview || []}
        />
        {pendingEdit.preview_truncated && (
          <p className="dp-warning">
            {t("edit.previewTruncated")}
          </p>
        )}
        {pendingEdit.before_after_preview?.length > 0 && (
          <details className="dp-action-details">
            <summary>{t("edit.beforeAfter")}</summary>
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
          >{t("edit.cancel")}</button>
          <button
            type="button"
            className="dp-btn dp-btn-danger"
            onClick={handleConfirmEdit}
            disabled={busy}
          >{t("edit.confirm")}</button>
        </div>
      </div>
    );
  }
  /* ================================
     CHAT SIDE PANEL
  ================================ */
  function renderChatSide(mode) {
    const isExplorer = mode === "explorer";
    const suggestions = (isExplorer ? EXPLORER_SUGGESTION_KEYS : ASSISTANT_SUGGESTION_KEYS).map((key) => t(`chat.suggestions.${key}`));
    const send = isExplorer
      ? sendExplorerQuestion
      : sendAssistantInstruction;
    const locked =
      !isExplorer && Boolean(pendingEdit);
    return (
      <aside className="dp-side">
        <div className="dp-side-card">
          <h4>{t("chat.activeDataset")}</h4>
          <div className="dp-side-stats">
            <div>
              <span>{t("metrics.rows")}</span>
              <strong>
                {formatNumber(dataset.total_rows)}
              </strong>
            </div>
            <div>
              <span>{t("metrics.columns")}</span>
              <strong>
                {formatNumber(dataset.total_columns)}
              </strong>
            </div>
          </div>
        </div>
        <div className="dp-side-card">
          <h4>{t("chat.tryAsking")}</h4>
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
            <h4>{t("dataset.schema")}</h4>
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
                ? `⌕ ${t("chat.explorerTitle")}`
                : `✦ ${t("chat.assistantTitle")}`}
            </h3>
            <p>
              {isExplorer
                ? t("chat.explorerDescription")
                : t("chat.assistantDescription")}
            </p>
          </div>
        </div>
        <div
          className="dp-chat-messages"
          role="log"
          aria-live="polite"
          aria-label={
            isExplorer
              ? t("chat.explorerTitle")
              : t("chat.assistantTitle")
          }
        >
          {renderChatMessages(
            messages,
            mode
          )}
          {!isExplorer && renderEditReview()}
          {busy && (
            <div className="dp-message dp-message-assistant dp-typing">
              <div className="dp-message-label">{t("chat.ai")}</div>
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
                  ? t("chat.explorerPlaceholder")
                  : t("chat.assistantPlaceholder")
              }
              aria-label={
                isExplorer
                  ? t("chat.explorerPlaceholder")
                  : t("chat.assistantPlaceholder")
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
            >{t("chat.send")}</button>
          </div>
          <p className="dp-chat-note">
            {isExplorer
              ? t("chat.explorerWarning")
              : pendingEdit
                ? t("chat.pendingWarning")
                : t("chat.assistantWarning")}
          </p>
        </form>
      </div>
    );
  }
  /* ================================
     MAIN LAYOUT
  ================================ */
  const heading = { title: t(`page.${activePage}.title`), text: t(`page.${activePage}.description`) };
  return (
    <div className="dp-app">
      <a
        className="dp-skip-link"
        href="#dp-main-content"
      >{t("app.skipToContent")}</a>
      {/* TOP NAVBAR */}
      <header className="dp-nav">
        <div className="dp-nav-inner">
          <div className="dp-brand">
            <div className="dp-brand-mark">
              <Logo />
            </div>
            <div>
              <strong>DataPilot AI</strong>
              <small>{t("app.tagline")}</small>
            </div>
          </div>
          <nav
            className="dp-navigation"
            aria-label={t("app.tagline")}
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
              <button type="button" className="dp-btn dp-btn-outline"
                onClick={() => { setLanguageSearch(""); setLanguageOpen(true); }}
                aria-haspopup="dialog" aria-expanded={languageOpen}
                title={t("language.select")}
              >
                🌐 {t("language.select")} · {LANGUAGE_OPTIONS.find((item) => item.code === language)?.nativeName || "English"}
              </button>
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
                  aria-label={t("nav.removeFile")}
                  title={t("nav.removeFile")}
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
                  ? t("nav.connected")
                  : t("nav.offline")}
              </span>
            )}
            {dataReady && (
              <button
                type="button"
                className="dp-btn dp-btn-outline"
                onClick={handleDownload}
                disabled={busy}
              >
                ↓ {t("nav.download")}
              </button>
            )}
            {renderNewProjectButton()}
            {renderUploadButton(t("nav.upload"))}
          </div>
        </div>
      </header>
        {languageOpen && (
          <div className="dp-language-overlay" role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setLanguageOpen(false);
            }}
            style={{ position: "fixed", inset: 0, zIndex: 10000, display: "grid", placeItems: "center", padding: 20, background: "rgba(9, 16, 42, .55)" }}
          >
            <div ref={languageDialogRef} role="dialog" aria-modal="true"
              aria-labelledby="dp-language-title" dir={LANGUAGE_OPTIONS.find(x => x.code === language)?.dir || "ltr"}
              style={{ width: "min(100%, 520px)", maxHeight: "min(86vh, 700px)", background: "#fff", color: "#172044", borderRadius: 20, boxShadow: "0 18px 65px rgba(0,0,0,.28)", display: "flex", flexDirection: "column", overflow: "hidden" }}
            >
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, padding: "20px 22px 12px" }}>
                <h2 id="dp-language-title" style={{ fontSize: 21, margin: 0 }}>{t("language.select")}</h2>
                <button type="button" aria-label={t("common.close")} onClick={() => setLanguageOpen(false)}
                  style={{ border: 0, background: "transparent", cursor: "pointer", fontSize: 26, padding: 4, color: "#172044" }}>×</button>
              </div>
              <div style={{ padding: "8px 22px 14px" }}>
                <input ref={languageSearchRef} type="search" value={languageSearch}
                  onChange={(event) => setLanguageSearch(event.target.value)}
                  placeholder={t("language.search")} aria-label={t("language.search")}
                  style={{ width: "100%", padding: "12px 14px", border: "1px solid #dce2f4", borderRadius: 12, fontSize: 15, boxSizing: "border-box" }}/>
              </div>
              <div style={{ overflowY: "auto", padding: "0 14px 18px", flex: 1 }}>
                {languageChoices.length ? languageChoices.map((item) => (
                  <button key={item.code} type="button" onClick={() => chooseLanguage(item.code)}
                    aria-pressed={language === item.code}
                    style={{ width: "100%", textAlign: "start", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, background: language === item.code ? "#eef2ff" : "transparent", color: "#172044", border: 0, borderRadius: 12, padding: "12px 14px", cursor: "pointer" }}
                  >
                    <span><strong style={{ display: "block", fontSize: 15 }}>{item.nativeName}</strong>
                      <small style={{ color: "#65708b" }}>{item.name}</small></span>
                    {language === item.code && <span aria-label={t("language.current")} style={{ color: "#2739b1", fontSize: 20 }}>✓</span>}
                  </button>
                )) : <p style={{ padding: 12 }}>{t("language.noResults")}</p>}
              </div>
            </div>
          </div>
        )}
      {renderNewProjectDialog()}
      {/* PAGE BANNER */}
      {dataReady && (
        <section className="dp-banner">
          <div className="dp-banner-inner">
            <div>
              <span className="dp-eyebrow">{t("app.workspace")}</span>
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
            <span>{t("messages.serverOffline")}</span>
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
              aria-label={t("common.close")}
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
              aria-label={t("common.close")}
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
                <h2>{t("hero.title")}</h2>
                <p>
                  {t("hero.description")}
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
                      {t("hero.fileSupport", { size: 200 })}
                    </span>
                  </div>
                  {renderUploadButton(t("hero.chooseFile"))}
                  {renderNewProjectButton()}
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
                    <span>{t("hero.exampleExplorer")}</span>
                  </div>
                  <div className="dp-pv-question">{t("hero.exampleQuestion")}</div>
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
                  <span className="dp-review-badge">{t("edit.confirmationRequired")}</span>
                  <strong>{t("chat.suggestions.removeDuplicates")}</strong>
                  <small>
                    12 rows · {t("edit.notApplied")}
                  </small>
                  <div className="dp-pv-actions">
                    <span className="dp-pv-btn">{t("common.cancel")}</span>
                    <span className="dp-pv-btn dp-pv-btn-primary">{t("common.confirm")}</span>
                  </div>
                </div>
              </div>
            </div>
            <div className="dp-hero-section-title">{t("hero.howItWorks")}</div>
            <ol className="dp-steps">
              <li>
                <span className="dp-step-num">
                  1
                </span>
                <strong>{t("hero.step1Title")}</strong>
                <p>{t("hero.step1Description")}</p>
              </li>
              <li>
                <span className="dp-step-num">
                  2
                </span>
                <strong>{t("hero.step2Title")}</strong>
                <p>{t("hero.step2Description")}</p>
              </li>
              <li>
                <span className="dp-step-num">
                  3
                </span>
                <strong>{t("hero.step3Title")}</strong>
                <p>{t("hero.step3Description")}</p>
              </li>
            </ol>
            <div className="dp-hero-features">
              <div>
                <strong>
                  ⌕ {t("nav.explorer")}
                </strong>
                <p>{t("hero.explorerFeature")}</p>
                <em>
                  “{t("hero.explorerExample")}”
                </em>
              </div>
              <div>
                <strong>
                  ✦ {t("nav.assistant")}
                </strong>
                <p>{t("hero.assistantFeature")}</p>
                <em>
                  “{t("hero.assistantExample")}”
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
                  <h2>{t("nav.dataset")}</h2>
                  <p>{t("dataset.datasetFeature")}</p>
                  <span>{t("dataset.openDataset")}</span>
                </button>
                <button
                  type="button"
                  className="dp-feature-card"
                  onClick={() => navigate("explorer")}
                >
                  <div className="dp-feature-icon">
                    ⌕
                  </div>
                  <h2>{t("nav.explorer")}</h2>
                  <p>{t("dataset.explorerFeature")}</p>
                  <span>{t("dataset.openExplorer")}</span>
                </button>
                <button
                  type="button"
                  className="dp-feature-card"
                  onClick={() => navigate("assistant")}
                >
                  <div className="dp-feature-icon">
                    ✦
                  </div>
                  <h2>{t("nav.assistant")}</h2>
                  <p>{t("dataset.assistantFeature")}</p>
                  <span>{t("dataset.openAssistant")}</span>
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
          <span>{t("app.tagline")}</span>
        </div>
      </footer>
    </div>
  );
}
export default App;
