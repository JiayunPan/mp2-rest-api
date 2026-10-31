# data_processor.py
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def remove_duplicates(df):
    """Remove duplicate rows."""
    before = len(df)
    df = df.drop_duplicates()
    after = len(df)
    logger.debug("remove_duplicates: %d → %d rows", before, after)
    return df


def handle_missing(df, axis="rows"):
    """Drop rows or columns containing missing values."""
    if axis == "rows":
        before = len(df)
        df = df.dropna(axis=0)
        after = len(df)
        logger.debug("handle_missing: %d → %d rows", before, after)
    elif axis == "columns":
        before = len(df.columns)
        df = df.dropna(axis=1)
        after = len(df.columns)
        logger.debug("handle_missing: %d → %d columns", before, after)
    else:
        logger.error("Unsupported axis: %s", axis)
        raise ValueError(f"Unsupported axis: {axis}")
    return df


def remove_outliers(df, columns, method, threshold):
    """Remove outliers from the specified numeric columns."""
    # 只支持 iqr 和 zscore 两种方法，其它一律报错退出
    if method not in ("iqr", "zscore"):
        logger.error("Unsupported outlier method: %s", method)
        raise ValueError(f"Unsupported outlier method: {method}")

    before = len(df)

    # 逐个处理配置里点名的列
    for col in columns:
        # 保护①：这列在表里根本不存在 → 警告并跳过
        if col not in df.columns:
            logger.warning("Column not found: %s", col)
            continue

        # 保护②：这列不是数字（没法算四分位数）→ 警告并跳过
        if not pd.api.types.is_numeric_dtype(df[col]):
            logger.warning("Column not numeric: %s", col)
            continue

        # 用 IQR 方法算上下界
        if method == "iqr":
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower = q1 - threshold * iqr
            upper = q3 + threshold * iqr

            # 只保留落在 [lower, upper] 范围内的行，范围外的=离群值=删掉
            df = df[(df[col] >= lower) & (df[col] <= upper)]

            logger.debug(
                "%s: lower=%s, upper=%s, removed=%d",
                col, lower, upper, before - len(df),
            )

    return df


def process_data(df, config):
    """Apply the processing steps enabled in the configuration."""
    # 从 config 里取出 processing 这一段
    processing = config["processing"]

    # 工序1：去重（仅当 remove_duplicates 为 true）
    if processing.get("remove_duplicates"):
        df = remove_duplicates(df)

    # 工序2：处理缺失（仅当 missing.enabled 为 true）
    missing = processing.get("missing", {})
    if missing.get("enabled"):
        df = handle_missing(df, axis=missing.get("axis", "rows"))

    # 工序3：去离群（仅当 outliers.enabled 为 true）
    outliers = processing.get("outliers", {})
    if outliers.get("enabled"):
        df = remove_outliers(
            df,
            columns=outliers.get("columns", []),
            method=outliers.get("method"),
            threshold=outliers.get("threshold"),
        )

    return df

def create_cleaning_report(df_before, df_after):
    """Return a dictionary summarizing the cleaning results."""
    rows_before = len(df_before)
    rows_after = len(df_after)
    columns_before = len(df_before.columns)
    columns_after = len(df_after.columns)

    return {
        "rows_before": rows_before,
        "rows_after": rows_after,
        "rows_removed": rows_before - rows_after,
        "columns_before": columns_before,
        "columns_after": columns_after,
        "columns_removed": columns_before - columns_after,
    }