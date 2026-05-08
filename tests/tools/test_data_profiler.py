from __future__ import annotations

import json

import pandas as pd

from src.tools.data_loader import load_table
from src.tools.data_profiler import profile_table, profile_table_from_path


def _column(profile, name):
    return next(column for column in profile["columns"] if column["name"] == name)


def test_profile_table_summarizes_dataframe_columns():
    # 测试 profiler 能统计 DataFrame 的行列数、缺失率、唯一值和数值摘要。
    dataframe = pd.DataFrame(
        {
            "customer_id": ["C1", "C2", "C3", "C3"],
            "age": [20, 30, None, 40],
            "churn": [0, 1, 0, 0],
        }
    )

    profile = profile_table(dataframe, dataset_name="customers")

    assert profile["dataset_name"] == "customers"
    assert profile["shape"] == {
        "rows": 4,
        "columns": 3,
        "profiled_columns": 3,
        "truncated_columns": [],
    }
    assert profile["duplicate_row_count"] == 0

    age = _column(profile, "age")
    assert age["missing_count"] == 1
    assert age["missing_rate"] == 0.25
    assert age["numeric_summary"]["min"] == 20.0
    assert age["numeric_summary"]["max"] == 40.0

    churn = _column(profile, "churn")
    assert churn["top_values"][0]["value"] == 0
    assert churn["top_values"][0]["count"] == 3


def test_profile_table_from_path_reuses_data_loader(tmp_path):
    # 测试传入文件路径时，profiler 会复用 data_loader 读取数据并记录来源信息。
    path = tmp_path / "train.csv"
    path.write_text("date,sales\n2026-01-01,10\n2026-01-02,12\n", encoding="utf-8")

    profile = profile_table_from_path(path)

    assert profile["dataset_name"] == "train.csv"
    assert profile["source"]["source_type"] == "path"
    assert profile["source"]["file_name"] == "train.csv"
    assert _column(profile, "date")["datetime_summary"]["min"] == "2026-01-01T00:00:00"


def test_profile_table_accepts_loaded_table(tmp_path):
    # 测试 profiler 可以直接接收 LoadedTable，避免重复读取已经加载的数据。
    path = tmp_path / "data.csv"
    path.write_text("x,y\n1,a\n2,b\n", encoding="utf-8")
    loaded = load_table(path)

    profile = profile_table(loaded)

    assert profile["source"]["source_type"] == "loaded_table"
    assert profile["shape"]["rows"] == 2
    assert _column(profile, "x")["numeric_summary"]["mean"] == 1.5


def test_profile_table_can_limit_profiled_columns():
    # 测试 max_columns 会限制详细分析的列数，并记录被截断的列名。
    dataframe = pd.DataFrame(
        {
            "a": [1],
            "b": [2],
            "c": [3],
        }
    )

    profile = profile_table(dataframe, max_columns=2)

    assert [column["name"] for column in profile["columns"]] == ["a", "b"]
    assert profile["shape"]["profiled_columns"] == 2
    assert profile["shape"]["truncated_columns"] == ["c"]


def test_profile_table_output_is_json_serializable():
    # 测试 profiler 输出可以直接 JSON 序列化，方便写文件或传给 LLM。
    dataframe = pd.DataFrame(
        {
            "when": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "value": [1.0, float("nan")],
        }
    )

    profile = profile_table(dataframe)

    json.dumps(profile, ensure_ascii=False)
    assert _column(profile, "value")["sample_values"] == [1.0]
