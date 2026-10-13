"""DataPilot AI local development API.
Supports uploaded CSV/XLSX datasets and new empty projects.
Datasets are stored in process memory. This service is
intended for local development, not multi-user production.
"""
import io
import inspect
import json
import re
import uuid
from pathlib import Path
from threading import Lock
from typing import Literal
import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from ai_engine import AIEngine
from data_engine import DataEngine
from excel_editor import ExcelEditor
from file_agent import FileAgent
from sql_validator import execute_safe_query
# =========================================
# LANGUAGES
# =========================================
SupportedLanguage = Literal[
    "en", "de", "fr", "es", "it",
    "pt", "ar", "ur", "roman_ur", "hi",
    "zh", "ja", "ko", "tr", "ru",
    "nl", "sv", "pl", "id", "bn",
]
DEFAULT_LANGUAGE = "en"
# =========================================
# FASTAPI CONFIGURATION
# =========================================
app = FastAPI(
    title="DataPilot AI API",
    description="CSV/Excel analysis, editing and project creation",
    version="1.5.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
# =========================================
# APPLICATION LIMITS
# =========================================
MAX_FILE_SIZE = 200 * 1024 * 1024
MAX_DATASETS = 10
MAX_ROWS = 100_000
MAX_COLUMNS = 100
EDIT_PREVIEW_LIMIT = 20
QUERY_RETURN_LIMIT = 1_000
EXPORT_BATCH_SIZE = 500
MAX_QUERY_EXPORT_ROWS = 100_000
# =========================================
# APPLICATION STATE
# =========================================
datasets = {}
datasets_lock = Lock()
ai_lock = Lock()
excel_editor = ExcelEditor()
ai_engine = None
file_agent = None
# =========================================
# REQUEST MODELS
# =========================================
class QueryRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=1, max_length=2000)
    language: SupportedLanguage = DEFAULT_LANGUAGE
class QueryExportRequest(BaseModel):
    dataset_id: str
    generated_sql: str = Field(min_length=1, max_length=20_000)
    dataset_revision: int = Field(ge=0)
    format: Literal["xlsx", "csv"] = "xlsx"


class EditPreviewRequest(BaseModel):
    dataset_id: str
    instruction: str = Field(min_length=1, max_length=2000)
    language: SupportedLanguage = DEFAULT_LANGUAGE
class EditDecisionRequest(BaseModel):
    dataset_id: str
    edit_id: str
class ProjectColumn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: Literal[
        "text", "string", "str",
        "integer", "int",
        "decimal", "float", "number",
        "boolean", "bool",
        "date", "datetime",
    ] = "text"
class NewProjectRequest(BaseModel):
    project_name: str = Field(min_length=1, max_length=100)
    columns: list[ProjectColumn] = Field(
        min_length=1,
        max_length=MAX_COLUMNS,
    )
# =========================================
# HELPER FUNCTIONS
# =========================================
def records(df, limit=10):
    """Convert DataFrame rows into JSON-safe records."""
    return json.loads(
        df.head(limit).to_json(
            orient="records",
            date_format="iso",
        )
    )
def find_dataset(dataset_id):
    with datasets_lock:
        dataset = datasets.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Please create or upload it again.",
        )
    return dataset
def get_ai():
    global ai_engine
    with ai_lock:
        if ai_engine is None:
            ai_engine = AIEngine()
        return ai_engine
def get_file_agent():
    global file_agent
    with ai_lock:
        if file_agent is None:
            file_agent = FileAgent()
        return file_agent
def call_ai_method(method, *args, language=DEFAULT_LANGUAGE):
    """Forward language when the AI implementation supports it."""
    parameters = inspect.signature(method).parameters
    supports_language = (
        "language" in parameters
        or any(
            p.kind == inspect.Parameter.VAR_KEYWORD
            for p in parameters.values()
        )
    )
    if supports_language:
        return method(*args, language=language)
    return method(*args)
def dataset_response(dataset_id, dataset, preview_limit=50):
    """Return a consistent dataset response shape."""
    df = dataset["dataframe"]
    return {
        "success": True,
        "dataset_id": dataset_id,
        "filename": dataset["filename"],
        "project_name": dataset.get("project_name"),
        "source": dataset.get("source", "upload"),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "columns": [
            {
                "name": str(column),
                "type": str(df[column].dtype),
            }
            for column in df.columns
        ],
        "schema": dataset["schema"],
        "revision": dataset["revision"],
        "preview": records(df, preview_limit),
    }
def register_dataset(
    *,
    engine,
    dataframe,
    filename,
    project_name=None,
    source="upload",
):
    """Register a prepared DataFrame and its DuckDB engine."""
    dataset_id = uuid.uuid4().hex
    entry = {
        "filename": filename,
        "project_name": project_name,
        "source": source,
        "dataframe": dataframe.copy(deep=True),
        "engine": engine,
        "schema": engine.get_schema(),
        "revision": 0,
        "pending_edit": None,
        "lock": Lock(),
    }
    with datasets_lock:
        if len(datasets) >= MAX_DATASETS:
            raise HTTPException(
                status_code=429,
                detail="Local dataset limit reached.",
            )
        datasets[dataset_id] = entry
    return dataset_id, entry
# =========================================
# EDIT PREVIEW DETAILS
# =========================================
def preview_changes(original, updated, action):
    """Describe actual modified records."""
    kind = action["action"]
    if kind in {"delete", "update"}:
        mask = excel_editor.get_filter_mask(original, action)
        selected = original.loc[mask]
        if kind == "delete":
            return {
                "affected_rows": int(mask.sum()),
                "matched_rows": int(mask.sum()),
                "affected_preview": records(
                    selected, EDIT_PREVIEW_LIMIT
                ),
                "changed_columns": list(original.columns),
                "changes_preview": [],
            }
        column = action["column"]
        old_values = (
            original.loc[mask, column]
            .reset_index(drop=True)
        )
        new_values = (
            updated.loc[mask, column]
            .reset_index(drop=True)
        )
        same = (
            old_values.eq(new_values).fillna(False)
            | (old_values.isna() & new_values.isna())
        )
        changed_positions = (~same).to_numpy(dtype=bool)
        before = selected.iloc[changed_positions]
        after = updated.loc[mask].iloc[changed_positions]
        row_numbers = (
            original.index.get_indexer(before.index) + 1
        ).tolist()
        changes = []
        for i in range(min(len(before), EDIT_PREVIEW_LIMIT)):
            changes.append({
                "row_number": int(row_numbers[i]),
                "before": records(before.iloc[[i]], 1)[0],
                "after": records(after.iloc[[i]], 1)[0],
            })
        return {
            "affected_rows": int(len(before)),
            "matched_rows": int(mask.sum()),
            "affected_preview": records(
                before, EDIT_PREVIEW_LIMIT
            ),
            "changed_columns": [column],
            "changes_preview": changes,
            "before_after_preview": changes,
        }
    if kind in {"add", "add_rows"}:
        appended = updated.iloc[len(original):]
        return {
            "affected_rows": int(len(appended)),
            "affected_preview": records(
                appended, EDIT_PREVIEW_LIMIT
            ),
            "changed_columns": (
                list(action["data"].keys())
                if kind == "add"
                else [
                    column for column in original.columns
                    if any(column in row for row in action["rows"])
                ]
            ),
            "changes_preview": [],
        }
    if kind == "remove_duplicates":
        duplicate_rows = original.loc[
            original.duplicated(keep="first")
        ]
        return {
            "affected_rows": int(len(duplicate_rows)),
            "affected_preview": records(
                duplicate_rows, EDIT_PREVIEW_LIMIT
            ),
            "changed_columns": list(original.columns),
            "changes_preview": [],
        }
    raise ValueError(f"Unsupported action: {kind}")
# =========================================
# HOME & HEALTH
# =========================================
@app.get("/")
def home():
    return {
        "application": "DataPilot AI",
        "status": "running",
        "version": "1.5.0",
    }
@app.get("/health")
def health():
    return {"status": "healthy"}
# =========================================
# START NEW PROJECT
# =========================================
@app.post("/projects/new", status_code=201)
def create_new_project(request: NewProjectRequest):
    """
    Create a zero-row dataset with user-defined columns.
    No CSV or Excel upload is required.
    The returned dataset_id works with the existing:
      GET  /datasets/{dataset_id}
      POST /query
      POST /edit/preview
      POST /edit/confirm
      POST /edit/cancel
      GET  /datasets/{dataset_id}/download
    """
    project_name = request.project_name.strip()
    if not project_name:
        raise HTTPException(
            status_code=422,
            detail="Project name cannot be empty.",
        )
    with datasets_lock:
        if len(datasets) >= MAX_DATASETS:
            raise HTTPException(
                status_code=429,
                detail="Local dataset limit reached.",
            )
    # File name is separate from the display name.
    safe_filename = re.sub(
        r'[\\/:*?"<>|\x00-\x1f]',
        "_",
        project_name,
    ).strip(" .")
    if not safe_filename:
        safe_filename = "new_project"
    filename = f"{safe_filename}.xlsx"
    columns = [
        {
            "name": column.name,
            "type": column.type,
        }
        for column in request.columns
    ]
    engine = None
    registered = False
    try:
        engine = DataEngine()
        # Implemented in updated data_engine.py.
        df = engine.create_empty_dataset(columns)
        if len(df.columns) > MAX_COLUMNS:
            raise ValueError(
                "Dataset exceeds the column limit."
            )
        dataset_id, entry = register_dataset(
            engine=engine,
            dataframe=df,
            filename=filename,
            project_name=project_name,
            source="new_project",
        )
        registered = True
        return {
            **dataset_response(dataset_id, entry),
            "message": "Project created successfully.",
        }
    except HTTPException:
        raise
    except (ValueError, TypeError) as error:
        raise HTTPException(
            status_code=400,
            detail=f"Project creation failed: {error}",
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Project creation failed: {error}",
        ) from error
    finally:
        if engine is not None and not registered:
            engine.close()
# =========================================
# UPLOAD DATASET
# =========================================
@app.post("/upload")
def upload_dataset(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    if Path(filename).suffix.lower() not in {
        ".csv", ".xlsx"
    }:
        raise HTTPException(
            400,
            "Only CSV and XLSX files are supported.",
        )
    content = file.file.read(MAX_FILE_SIZE + 1)
    if not content:
        raise HTTPException(
            400,
            "Uploaded file is empty.",
        )
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            413,
            "File exceeds the 200 MB limit.",
        )
    with datasets_lock:
        if len(datasets) >= MAX_DATASETS:
            raise HTTPException(
                429,
                "Local dataset limit reached.",
            )
    engine = None
    registered = False
    try:
        stream = io.BytesIO(content)
        stream.name = filename
        engine = DataEngine()
        df = engine.load_file(stream)
        if df is None or df.empty:
            raise ValueError(
                "Dataset contains no data rows."
            )
        if (
            len(df) > MAX_ROWS
            or len(df.columns) > MAX_COLUMNS
        ):
            raise ValueError(
                "Dataset exceeds row or column limit."
            )
        dataset_id, entry = register_dataset(
            engine=engine,
            dataframe=df,
            filename=filename,
            source="upload",
        )
        registered = True
        return dataset_response(dataset_id, entry)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            400,
            f"Upload failed: {error}",
        ) from error
    finally:
        if engine is not None and not registered:
            engine.close()
# =========================================
# GET DATASET
# =========================================
@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    dataset = find_dataset(dataset_id)
    with dataset["lock"]:
        return dataset_response(dataset_id, dataset)
# =========================================
# DATA EXPLORER — MULTILINGUAL QUERY
# =========================================
@app.get("/datasets/{dataset_id}/rows")
def get_dataset_rows(dataset_id: str, offset: int = 0, limit: int = 200):
    """Fetch any page of the dataset without returning all rows at once."""
    if offset < 0:
        raise HTTPException(status_code=422, detail="offset must be >= 0.")
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=422, detail="limit must be between 1 and 500.")
    dataset = find_dataset(dataset_id)
    with dataset["lock"]:
        df = dataset["dataframe"]
        total = len(df)
        page = df.iloc[offset:offset + limit]
        return {
            "success": True,
            "dataset_id": dataset_id,
            "revision": dataset["revision"],
            "offset": offset,
            "limit": limit,
            "total_rows": total,
            "returned_rows": len(page),
            "has_more": offset + len(page) < total,
            "columns": [str(column) for column in df.columns],
            "rows": records(page, limit),
        }


@app.post("/query")
def query_dataset(request: QueryRequest):
    dataset = find_dataset(request.dataset_id)
    try:
        ai = get_ai()
        with dataset["lock"]:
            schema = dataset["schema"]
        sql = call_ai_method(
            ai.generate_sql,
            request.question,
            schema,
            language=request.language,
        )
        # AI SQL must pass the separate SQL validator.
        with dataset["lock"]:
            result = execute_safe_query(
                dataset["engine"].connection,
                sql,
            )
            revision = dataset["revision"]
        if result.empty:
            answer = (
                "No matching records found "
                "in the current dataset."
            )
        else:
            answer = call_ai_method(
                ai.generate_answer,
                request.question,
                result.head(30).to_string(index=False),
                language=request.language,
            )
        truncated = bool(
            result.attrs.get("truncated", False)
        )
        return {
            "success": True,
            "dataset_id": request.dataset_id,
            "dataset_revision": revision,
            "question": request.question,
            "generated_sql": sql,
            "answer": answer,
            "returned_rows": len(result),
            "columns": list(result.columns),
            "data": records(result, QUERY_RETURN_LIMIT),
            "result_truncated": truncated,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            400,
            f"Query failed: {error}",
        ) from error
# =========================================
# EXPORT DATA EXPLORER QUERY RESULTS
# =========================================
@app.post("/query/export")
def export_query_result(request: QueryExportRequest):
    """Export the complete read-only SQL result, independent of UI preview limits."""
    dataset = find_dataset(request.dataset_id)
    sql = request.generated_sql.strip()
    try:
        with dataset["lock"]:
            if request.dataset_revision != dataset["revision"]:
                raise HTTPException(
                    status_code=409,
                    detail="Dataset changed since this query. Run the query again before exporting.",
                )
            connection = dataset["engine"].connection
            # Validate the original SQL before wrapping it for page-wise reading.
            execute_safe_query(connection, sql)
            inner_sql = sql.rstrip(";").strip()
            pages = []
            total = 0
            columns = None
            while total <= MAX_QUERY_EXPORT_ROWS:
                page_sql = (
                    f'SELECT * FROM ({inner_sql}) AS dp_export_result '
                    f'LIMIT {EXPORT_BATCH_SIZE} OFFSET {total}'
                )
                page = execute_safe_query(connection, page_sql)
                if columns is None:
                    columns = list(page.columns)
                if page.empty:
                    break
                pages.append(page)
                total += len(page)
                if total > MAX_QUERY_EXPORT_ROWS:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Query export exceeds {MAX_QUERY_EXPORT_ROWS:,} rows.",
                    )
                if len(page) < EXPORT_BATCH_SIZE:
                    break
            result = (
                pd.concat(pages, ignore_index=True)
                if pages else pd.DataFrame(columns=columns or [])
            )
        if request.format == "csv":
            content = result.to_csv(index=False).encode("utf-8-sig")
            media_type = "text/csv; charset=utf-8"
        else:
            exported = excel_editor.export_excel(result)
            content = exported.getvalue() if hasattr(exported, "getvalue") else bytes(exported)
            media_type = (
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        filename = f"datapilot_query_result.{request.format}"
        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Query export failed: {error}") from error


# =========================================
# AI ASSISTANT — MULTILINGUAL EDIT PREVIEW
# =========================================
@app.post("/edit/preview")
def preview_edit(request: EditPreviewRequest):
    dataset = find_dataset(request.dataset_id)
    with dataset["lock"]:
        if dataset["pending_edit"] is not None:
            raise HTTPException(
                409,
                "An edit is awaiting confirmation. "
                "Confirm or cancel it first.",
            )
        current_df = dataset["dataframe"].copy()
        current_revision = dataset["revision"]
    try:
        action = call_ai_method(
            get_file_agent().generate_action,
            request.instruction,
            list(current_df.columns),
            language=request.language,
        )
        if (
            not isinstance(action, dict)
            or action.get("action") not in {
                "delete",
                "update",
                "add",
                "add_rows",
                "remove_duplicates",
            }
        ):
            raise ValueError(
                "Unsupported editing action."
            )
        updated_df = excel_editor.execute_action(
            current_df.copy(),
            action,
        )
        if (
            updated_df is None
            or updated_df.equals(current_df)
        ):
            raise ValueError(
                "No changes detected. Check your instruction."
            )
        # A new project begins with zero rows.
        # ADD is valid because updated_df will then
        # contain its first record.
        #
        # Keep the existing restriction against
        # deleting every row from a populated dataset.
        if updated_df.empty:
            raise ValueError(
                "Deleting all rows is not supported "
                "in this version."
            )
        if (
            len(updated_df) > MAX_ROWS
            or len(updated_df.columns) > MAX_COLUMNS
        ):
            raise ValueError(
                "Updated dataset exceeds row or column limit."
            )
        details = preview_changes(
            current_df,
            updated_df,
            action,
        )
        if details["affected_rows"] == 0:
            raise ValueError(
                "No actual changes detected."
            )
        edit_id = uuid.uuid4().hex
        with dataset["lock"]:
            if dataset["revision"] != current_revision:
                raise HTTPException(
                    409,
                    "Dataset changed. Please request a new preview.",
                )
            if dataset["pending_edit"] is not None:
                raise HTTPException(
                    409,
                    "Another edit is awaiting confirmation.",
                )
            dataset["pending_edit"] = {
                "edit_id": edit_id,
                "action": action,
                "dataframe": updated_df.copy(),
                "revision": current_revision,
            }
        return {
            "success": True,
            "message": (
                "Preview generated. No changes applied yet."
            ),
            "dataset_id": request.dataset_id,
            "dataset_revision": current_revision,
            "edit_id": edit_id,
            "action": action,
            "before_rows": len(current_df),
            "after_rows": len(updated_df),
            **details,
            "preview_limit": EDIT_PREVIEW_LIMIT,
            "preview_truncated": (
                details["affected_rows"] > EDIT_PREVIEW_LIMIT
            ),
            "requires_confirmation": True,
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            400,
            f"Edit preview failed: {error}",
        ) from error
# =========================================
# CONFIRM EDIT
# =========================================
@app.post("/edit/confirm")
def confirm_edit(request: EditDecisionRequest):
    dataset = find_dataset(request.dataset_id)
    with dataset["lock"]:
        pending = dataset["pending_edit"]
        if (
            pending is None
            or pending["edit_id"] != request.edit_id
        ):
            raise HTTPException(
                404,
                "Pending edit not found.",
            )
        if pending["revision"] != dataset["revision"]:
            raise HTTPException(
                409,
                "Dataset changed. Generate a new preview.",
            )
        updated_df = pending["dataframe"].copy()
        try:
            dataset["engine"].reload_database(
                updated_df
            )
            schema = dataset["engine"].get_schema()
        except Exception as error:
            raise HTTPException(
                500,
                f"Database update failed: {error}",
            ) from error
        dataset["dataframe"] = updated_df
        dataset["schema"] = schema
        dataset["revision"] += 1
        dataset["pending_edit"] = None
        return {
            "success": True,
            "message": "Changes applied successfully.",
            "dataset_id": request.dataset_id,
            "revision": dataset["revision"],
            "total_rows": len(updated_df),
            "total_columns": len(updated_df.columns),
            "preview": records(updated_df),
        }
# =========================================
# CANCEL EDIT
# =========================================
@app.post("/edit/cancel")
def cancel_edit(request: EditDecisionRequest):
    dataset = find_dataset(request.dataset_id)
    with dataset["lock"]:
        pending = dataset["pending_edit"]
        if (
            pending is None
            or pending["edit_id"] != request.edit_id
        ):
            raise HTTPException(
                404,
                "Pending edit not found.",
            )
        dataset["pending_edit"] = None
    return {
        "success": True,
        "message": "Edit cancelled. Dataset unchanged.",
    }
# =========================================
# DOWNLOAD UPDATED EXCEL
# =========================================
@app.get("/datasets/{dataset_id}/download")
def download_dataset(dataset_id: str):
    dataset = find_dataset(dataset_id)
    with dataset["lock"]:
        df = dataset["dataframe"].copy()
    try:
        excel_data = excel_editor.export_excel(df)
        content = (
            excel_data.getvalue()
            if hasattr(excel_data, "getvalue")
            else bytes(excel_data)
        )
    except Exception as error:
        raise HTTPException(
            500,
            f"Excel export failed: {error}",
        ) from error
    return StreamingResponse(
        io.BytesIO(content),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="updated_data.xlsx"'
            )
        },
    )
