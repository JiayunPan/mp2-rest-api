# src/data_output.py
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


def save_data(df, filepath):
    """Save a DataFrame as a CSV file."""
    path = Path(filepath)

    # 如果输出目录（比如 output/）不存在，就自动创建
    path.parent.mkdir(parents=True, exist_ok=True)

    # 存成 CSV，不带 index 行号
    df.to_csv(path, index=False)

    logger.debug("Saved %d rows to %s", len(df), path)
    return path