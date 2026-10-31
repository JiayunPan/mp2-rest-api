import io
import json
import logging
from pathlib import Path
import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from src import (
    DatasetInfo,
    DatasetStorage,
    HealthResponse,
    log_requests,
    ProcessConfig,
    ProcessingReport,
    setup_logging,
)
from data_pipeline import create_cleaning_report, process_data, validate_dataframe

setup_logging(verbose=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Data Processing API", version="1.0.0")
app.middleware("http")(log_requests)
storage = DatasetStorage()


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Return the application status and version."""
    return {"status": "ok", "version": app.version}


@app.post("/upload", response_model=DatasetInfo)
async def upload_dataset(file: UploadFile = File(...)):
    """Read and store a CSV upload."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix != ".csv":
        logger.warning("Unsupported file format: %s", suffix)
        raise HTTPException(status_code=400, detail="Only .csv files are supported.")

    contents = await file.read()
    try:
        df = pd.read_csv(io.BytesIO(contents))
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError) as exc:
        logger.warning("Could not parse CSV '%s': %s", file.filename, exc)
        raise HTTPException(status_code=400, detail="Could not parse the uploaded CSV file.")

    dataset_id = storage.save(df, file.filename)
    metadata = storage.get_metadata(dataset_id)
    logger.info(
        "Uploaded dataset: id=%d, filename=%s, rows=%d",
        dataset_id, file.filename, metadata["rows"],
    )
    return metadata


@app.get("/datasets/{dataset_id}")
def get_dataset(dataset_id: int, limit: int = Query(default=100, ge=1)):
    """Return up to limit rows from a stored dataset."""
    df = storage.get(dataset_id)
    if df is None:
        logger.warning("Dataset not found: %d", dataset_id)
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")

    records = json.loads(df.head(limit).to_json(orient="records"))
    logger.info("Retrieved dataset: id=%d, returned_rows=%d", dataset_id, len(records))
    return {
        "id": dataset_id,
        "data": records,
        "total_rows": len(df),
    }

@app.post("/datasets/{dataset_id}/process", response_model=ProcessingReport)
def process_dataset(dataset_id: int, config: ProcessConfig):
    """Validate and process a stored dataset using MP1 functions."""
    # 1. 取货：找不到就 404（这一步必须在 try 块外）
    df = storage.get(dataset_id)
    if df is None:
        logger.warning("Dataset not found: %d", dataset_id)
        raise HTTPException(status_code=404, detail=f"Dataset {dataset_id} not found.")

    # 2. 把套娃模型翻译成纯字典，MP1 的函数才认得
    config_dict = config.model_dump()
    required_columns = config_dict["validation"]["required_columns"]
    numeric_columns = config_dict["validation"]["numeric_columns"]

    # 3. 先确认每个"数字列"都真实存在，缺就 400（在 try 块外，属于请求本身的问题）
    for col in numeric_columns:
        if col not in df.columns:
            logger.warning("Numeric column not found: %s", col)
            raise HTTPException(status_code=400, detail=f"Numeric column not found: {col}")

    # 4. 校验 + 加工：MP1 函数里抛出的 ValueError 统一转成 400
    try:
        validated = validate_dataframe(df, required_columns, numeric_columns)
        validation_rows_removed = len(df) - len(validated)

        # 加工前先存一份校验后的副本，用来和加工结果对比生成报告
        validated_copy = validated.copy()
        processed = process_data(validated, config_dict)
    except ValueError as error:
        logger.warning("Processing failed for id=%d: %s", dataset_id, error)
        raise HTTPException(status_code=400, detail=str(error))

    # 5. 对比"校验后 vs 加工后"生成清洗报告
    cleaning_report = create_cleaning_report(validated_copy, processed)

    # 6. 两步都成功了，才把结果写回仓库
    storage.update(dataset_id, processed)

    logger.info(
        "Processed dataset: id=%d, validation_removed=%d, rows_before=%d, rows_after=%d",
        dataset_id,
        validation_rows_removed,
        cleaning_report["rows_before"],
        cleaning_report["rows_after"],
    )

    return {
        "id": dataset_id,
        "validation_rows_removed": validation_rows_removed,
        "cleaning_report": cleaning_report,
    }