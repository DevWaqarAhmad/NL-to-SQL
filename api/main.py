
import io
import json
import uuid
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from ai_engine import AIEngine
from data_engine import DataEngine
from sql_validator import execute_safe_query


app = FastAPI(
    title="AI Data Assistant API",
    description="Universal Excel/CSV Analysis and Editing API",
    version="1.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"]
)


MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_DATASETS = 10
MAX_ROWS = 100000
MAX_COLUMNS = 100

datasets = {}
datasets_lock = Lock()
ai_engine = None


class QueryRequest(BaseModel):
    dataset_id: str
    question: str = Field(min_length=1, max_length=2000)


def get_ai_engine():
    global ai_engine

    if ai_engine is None:
        ai_engine = AIEngine()

    return ai_engine


def dataframe_records(df, limit=1000):
    return json.loads(
        df.head(limit).to_json(
            orient="records",
            date_format="iso"
        )
    )


@app.get("/")
def home():
    return {
        "application": "AI Data Assistant",
        "status": "running",
        "version": "1.1.0"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/upload")
def upload_dataset(file: UploadFile = File(...)):
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in (".csv", ".xlsx"):
        raise HTTPException(
            status_code=400,
            detail="Only CSV and XLSX files are supported."
        )

    content = file.file.read(MAX_FILE_SIZE + 1)

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds 10 MB."
        )

    engine = DataEngine()

    try:
        stream = io.BytesIO(content)
        stream.name = filename

        df = engine.load_file(stream)

        if df is None or df.empty:
            raise ValueError("Dataset contains no data rows.")

        if len(df) > MAX_ROWS:
            raise ValueError("Dataset exceeds row limit.")

        if len(df.columns) > MAX_COLUMNS:
            raise ValueError("Dataset exceeds column limit.")

        schema = engine.get_schema()
        dataset_id = uuid.uuid4().hex

        with datasets_lock:
            if len(datasets) >= MAX_DATASETS:
                raise HTTPException(
                    status_code=429,
                    detail="Local dataset limit reached."
                )

            datasets[dataset_id] = {
                "filename": filename,
                "dataframe": df.copy(),
                "engine": engine,
                "schema": schema,
                "lock": Lock()
            }

        return {
            "success": True,
            "message": "File uploaded successfully.",
            "dataset_id": dataset_id,
            "filename": filename,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": [
                {
                    "name": str(column),
                    "type": str(df[column].dtype)
                }
                for column in df.columns
            ],
            "schema": schema,
            "preview": dataframe_records(df, 10)
        }

    except HTTPException:
        raise

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to load dataset: {error}"
        )


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: str):
    with datasets_lock:
        dataset = datasets.get(dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found."
        )

    with dataset["lock"]:
        df = dataset["dataframe"]
        return {
            "dataset_id": dataset_id,
            "filename": dataset["filename"],
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "schema": dataset["schema"],
            "preview": dataframe_records(df, 10)
        }


@app.post("/query")
def query_dataset(request: QueryRequest):
    with datasets_lock:
        dataset = datasets.get(request.dataset_id)

    if dataset is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. Upload a file first."
        )

    try:
        ai = get_ai_engine()

        with dataset["lock"]:
            schema = dataset["schema"]

        sql = ai.generate_sql(
            request.question,
            schema
        )

        # Uses the existing SQL validator.
        # This is not yet a production security boundary.
        with dataset["lock"]:
            result = execute_safe_query(
                dataset["engine"].connection,
                sql
            )

        records = dataframe_records(result, 1000)

        # Avoid sending a huge result to Gemini.
        answer_input = result.head(30).to_string(
            index=False
        )

        answer = ai.generate_answer(
            request.question,
            answer_input
        )

        return {
            "success": True,
            "dataset_id": request.dataset_id,
            "question": request.question,
            "generated_sql": sql,
            "answer": answer,
            "returned_rows": len(result),
            "columns": list(result.columns),
            "data": records
        }

    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Query failed: {error}"
        )
