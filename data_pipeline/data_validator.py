# src/data_validator.py
import logging
import pandas as pd


logger = logging.getLogger(__name__)


def validate_dataframe(df, required_columns, numeric_columns):
    """Validate the DataFrame and return valid data.

    required_columns: a list of column names that must exist.
    numeric_columns: a list of column names whose values should be numeric.
    """
    before = len(df)

    # 1. 检查所有必需列是否存在，缺任何一个就报错退出
    for col in required_columns:
        if col not in df.columns:
            logger.error("Required column missing: %s", col)
            raise ValueError(f"Required column missing: {col}")

    # 2. 逐个清理数字列里的非数字脏值
    for col in numeric_columns:
        invalid_rows = []
        for i, value in df[col].items():
            if pd.notna(value):              # 跳过空值（空值交给后面的 handle_missing 处理）
                try:
                    float(value)             # 试着把这个值转成数字
                except ValueError:
                    # 转不动 = 非数字脏值，记下这一行的行号，并警告
                    logger.warning("Invalid numeric value in %s: %s", col, value)
                    invalid_rows.append(i)

        # 删掉所有含非数字脏值的行
        df = df.drop(invalid_rows)

        # 把这一列正式转成数字类型
        df[col] = pd.to_numeric(df[col])

    after = len(df)
    logger.debug("Validation: %d → %d rows", before, after)
    return df