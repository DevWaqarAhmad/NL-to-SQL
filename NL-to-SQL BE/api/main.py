"""DataPilot AI local development API.



All datasets live in process memory. This is not a multi-user production service:

authentication, storage, query sandboxing and resource limits are still needed.

"""



import io
import inspect

import json

import uuid

from pathlib import Path

from threading import Lock
from typing import Literal



from fastapi import FastAPI, File, HTTPException, UploadFile

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import StreamingResponse

from pydantic import BaseModel, Field



from ai_engine import AIEngine

from data_engine import DataEngine

from excel_editor import ExcelEditor

from file_agent import FileAgent

from sql_validator import execute_safe_query



app = FastAPI(

    title="DataPilot AI API",

    description="Universal CSV/Excel data analysis and editing (local development)",

    version="1.4.0",

)



app.add_middleware(

    CORSMiddleware,

    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],

    allow_credentials=False,

    allow_methods=["GET", "POST"],

    allow_headers=["Content-Type"],

)



MAX_FILE_SIZE = 200 * 1024 * 1024

MAX_DATASETS = 10

MAX_ROWS = 100_000

MAX_COLUMNS = 100

EDIT_PREVIEW_LIMIT = 20

QUERY_RETURN_LIMIT = 1_000



datasets = {}

datasets_lock = Lock()

ai_lock = Lock()

excel_editor = ExcelEditor()

ai_engine = None

file_agent = None





class QueryRequest(BaseModel):

    dataset_id: str

    question: str = Field(min_length=1, max_length=2000)

    language: Literal["en", "roman_ur", "ur"] = "en"





class EditPreviewRequest(BaseModel):

    dataset_id: str

    instruction: str = Field(min_length=1, max_length=2000)

    language: Literal["en", "roman_ur", "ur"] = "en"





class EditDecisionRequest(BaseModel):

    dataset_id: str

    edit_id: str





def records(df, limit=10):

    """JSON-safe records for numpy scalars, dates and missing pandas values."""

    return json.loads(df.head(limit).to_json(orient="records", date_format="iso"))





def find_dataset(dataset_id):

    with datasets_lock:

        dataset = datasets.get(dataset_id)

    if dataset is None:

        raise HTTPException(404, "Dataset not found. Please upload a file again.")

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





def call_ai_method(method, *args, language="en"):
    """Forward language when an AI implementation supports it.

    Compatibility with currently installed AIEngine/FileAgent versions is
    maintained until those classes are updated for multilingual prompts.
    """
    parameters = inspect.signature(method).parameters
    if "language" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return method(*args, language=language)
    return method(*args)


def preview_changes(original, updated, action):

    """Describe actual changed records, without changing either dataframe."""

    kind = action["action"]



    if kind in {"delete", "update"}:

        mask = excel_editor.get_filter_mask(original, action)

        selected = original.loc[mask]



        if kind == "delete":

            return {

                "affected_rows": int(mask.sum()),

                "matched_rows": int(mask.sum()),

                "affected_preview": records(selected, EDIT_PREVIEW_LIMIT),

                "changed_columns": list(original.columns),

                "changes_preview": [],

            }



        column = action["column"]

        old_values = original.loc[mask, column].reset_index(drop=True)

        new_values = updated.loc[mask, column].reset_index(drop=True)



        # Treat two nulls as equal, while counting null <-> non-null as a change.

        same = (

            old_values.eq(new_values).fillna(False)

            | (old_values.isna() & new_values.isna())

        )

        changed_positions = (~same).to_numpy(dtype=bool)

        before = selected.iloc[changed_positions]

        after = updated.loc[mask].iloc[changed_positions]

        row_numbers = (original.index.get_indexer(before.index) + 1).tolist()



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

            "affected_preview": records(before, EDIT_PREVIEW_LIMIT),

            "changed_columns": [column],

            "changes_preview": changes,

            # Backward-compatible with the currently used React preview.

            "before_after_preview": changes,

        }



    if kind == "add":

        appended = updated.iloc[len(original):]

        return {

            "affected_rows": int(len(appended)),

            "affected_preview": records(appended, EDIT_PREVIEW_LIMIT),

            "changed_columns": list(action["data"].keys()),

            "changes_preview": [],

        }



    if kind == "remove_duplicates":

        duplicate_rows = original.loc[original.duplicated(keep="first")]

        return {

            "affected_rows": int(len(duplicate_rows)),

            "affected_preview": records(duplicate_rows, EDIT_PREVIEW_LIMIT),

            "changed_columns": list(original.columns),

            "changes_preview": [],

        }



    raise ValueError(f"Unsupported action: {kind}")





@app.get("/")

def home():

    return {"application": "DataPilot AI", "status": "running", "version": "1.4.0"}





@app.get("/health")

def health():

    return {"status": "healthy"}





@app.post("/upload")

def upload_dataset(file: UploadFile = File(...)):

    filename = Path(file.filename or "").name

    if Path(filename).suffix.lower() not in {".csv", ".xlsx"}:

        raise HTTPException(400, "Only CSV and XLSX files are supported.")



    content = file.file.read(MAX_FILE_SIZE + 1)

    if not content:

        raise HTTPException(400, "Uploaded file is empty.")

    if len(content) > MAX_FILE_SIZE:

        raise HTTPException(413, "File exceeds the 200 MB limit.")



    with datasets_lock:

        if len(datasets) >= MAX_DATASETS:

            raise HTTPException(429, "Local dataset limit reached.")



    engine = None

    try:

        stream = io.BytesIO(content)

        stream.name = filename

        engine = DataEngine()

        df = engine.load_file(stream)



        if df is None or df.empty:

            raise ValueError("Dataset contains no data rows.")

        if len(df) > MAX_ROWS or len(df.columns) > MAX_COLUMNS:

            raise ValueError("Dataset exceeds row or column limit.")



        schema = engine.get_schema()

        dataset_id = uuid.uuid4().hex

        with datasets_lock:

            if len(datasets) >= MAX_DATASETS:

                raise HTTPException(429, "Local dataset limit reached.")

            datasets[dataset_id] = {

                "filename": filename,

                "dataframe": df.copy(),

                "engine": engine,

                "schema": schema,

                "revision": 0,

                "pending_edit": None,

                "lock": Lock(),

            }



        return {

            "success": True,

            "dataset_id": dataset_id,

            "filename": filename,

            "total_rows": len(df),

            "total_columns": len(df.columns),

            "columns": [{"name": str(c), "type": str(df[c].dtype)} for c in df.columns],

            "schema": schema,

            "revision": 0,

            "preview": records(df),

        }

    except HTTPException:

        if engine is not None and all(d["engine"] is not engine for d in datasets.values()):

            engine.close()

        raise

    except Exception as error:

        if engine is not None:

            engine.close()

        raise HTTPException(400, f"Upload failed: {error}") from error





@app.get("/datasets/{dataset_id}")

def get_dataset(dataset_id: str):

    dataset = find_dataset(dataset_id)

    with dataset["lock"]:

        df = dataset["dataframe"]

        return {

            "dataset_id": dataset_id,

            "filename": dataset["filename"],

            "total_rows": len(df),

            "total_columns": len(df.columns),

            "columns": [{"name": str(c), "type": str(df[c].dtype)} for c in df.columns],

            "schema": dataset["schema"],

            "revision": dataset["revision"],

            "preview": records(df),

        }





@app.post("/query")

def query_dataset(request: QueryRequest):

    dataset = find_dataset(request.dataset_id)

    try:

        ai = get_ai()

        with dataset["lock"]:

            schema = dataset["schema"]



        sql = call_ai_method(
                ai.generate_sql, request.question, schema, language=request.language
            )



        # Existing sql_validator is NOT a sufficient sandbox for public use.

        with dataset["lock"]:

            result = execute_safe_query(dataset["engine"].connection, sql)

            revision = dataset["revision"]



        if result.empty:

            answer = "No matching records found in the current dataset."

        else:

            answer = call_ai_method(
                ai.generate_answer,
                request.question,
                result.head(30).to_string(index=False),
                language=request.language,
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

            "result_truncated": len(result) > QUERY_RETURN_LIMIT,

        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(400, f"Query failed: {error}") from error





@app.post("/edit/preview")

def preview_edit(request: EditPreviewRequest):

    dataset = find_dataset(request.dataset_id)

    with dataset["lock"]:

        if dataset["pending_edit"] is not None:

            raise HTTPException(409, "An edit is awaiting confirmation. Confirm or cancel it first.")

        current_df = dataset["dataframe"].copy()

        current_revision = dataset["revision"]



    try:

        action = call_ai_method(
            get_file_agent().generate_action,
            request.instruction,
            list(current_df.columns),
            language=request.language,
        )

        if not isinstance(action, dict) or action.get("action") not in {

            "delete", "update", "add", "remove_duplicates"

        }:

            raise ValueError("Unsupported editing action.")



        updated_df = excel_editor.execute_action(current_df.copy(), action)

        if updated_df is None or updated_df.equals(current_df):

            raise ValueError("No changes detected. Check your instruction.")

        if updated_df.empty:

            raise ValueError("Deleting all rows is not supported in this version.")

        if len(updated_df) > MAX_ROWS or len(updated_df.columns) > MAX_COLUMNS:

            raise ValueError("Updated dataset exceeds row or column limit.")



        details = preview_changes(current_df, updated_df, action)

        if details["affected_rows"] == 0:

            raise ValueError("No actual changes detected.")



        edit_id = uuid.uuid4().hex

        with dataset["lock"]:

            if dataset["revision"] != current_revision:

                raise HTTPException(409, "Dataset changed. Please request a new preview.")

            if dataset["pending_edit"] is not None:

                raise HTTPException(409, "Another edit is awaiting confirmation.")

            dataset["pending_edit"] = {

                "edit_id": edit_id,

                "action": action,

                "dataframe": updated_df.copy(),

                "revision": current_revision,

            }



        return {

            "success": True,

            "message": "Preview generated. No changes applied yet.",

            "dataset_id": request.dataset_id,

            "dataset_revision": current_revision,

            "edit_id": edit_id,

            "action": action,

            "before_rows": len(current_df),

            "after_rows": len(updated_df),

            **details,

            "preview_limit": EDIT_PREVIEW_LIMIT,

            "preview_truncated": details["affected_rows"] > EDIT_PREVIEW_LIMIT,

            "requires_confirmation": True,

        }

    except HTTPException:

        raise

    except Exception as error:

        raise HTTPException(400, f"Edit preview failed: {error}") from error





@app.post("/edit/confirm")

def confirm_edit(request: EditDecisionRequest):

    dataset = find_dataset(request.dataset_id)

    with dataset["lock"]:

        pending = dataset["pending_edit"]

        if pending is None or pending["edit_id"] != request.edit_id:

            raise HTTPException(404, "Pending edit not found.")

        if pending["revision"] != dataset["revision"]:

            raise HTTPException(409, "Dataset changed. Generate a new preview.")



        updated_df = pending["dataframe"].copy()

        try:

            # DataEngine.reload_database updates DuckDB before the frontend state.

            dataset["engine"].reload_database(updated_df)

            schema = dataset["engine"].get_schema()

        except Exception as error:

            raise HTTPException(500, f"Database update failed: {error}") from error



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





@app.post("/edit/cancel")

def cancel_edit(request: EditDecisionRequest):

    dataset = find_dataset(request.dataset_id)

    with dataset["lock"]:

        pending = dataset["pending_edit"]

        if pending is None or pending["edit_id"] != request.edit_id:

            raise HTTPException(404, "Pending edit not found.")

        dataset["pending_edit"] = None

    return {"success": True, "message": "Edit cancelled. Dataset unchanged."}





@app.get("/datasets/{dataset_id}/download")

def download_dataset(dataset_id: str):

    dataset = find_dataset(dataset_id)

    with dataset["lock"]:

        df = dataset["dataframe"].copy()

    try:

        excel_data = excel_editor.export_excel(df)

        content = excel_data.getvalue() if hasattr(excel_data, "getvalue") else bytes(excel_data)

    except Exception as error:

        raise HTTPException(500, f"Excel export failed: {error}") from error



    return StreamingResponse(

        io.BytesIO(content),

        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        headers={"Content-Disposition": 'attachment; filename="updated_data.xlsx"'},

    )
