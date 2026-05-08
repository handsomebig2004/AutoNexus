from __future__ import annotations

import json

import pandas as pd

from src.schemas.requirement import TaskDefinition
from src.tools.data_profiler import profile_table
from src.tools.schema_infer import infer_schema


def _column(schema, name):
    return next(column for column in schema["columns"] if column["name"] == name)


def _task_definition(**overrides):
    data = {
        "task_name": "Customer churn prediction",
        "task_type": "classification",
        "decision": "accepted",
        "should_model": True,
        "problem_statement": "Predict whether a customer will churn.",
        "input_mode": {
            "data_type": "tabular",
            "required_inputs": ["customer features", "churn label"],
            "target_column": "churn",
        },
        "output_mode": {
            "prediction_type": "class_label",
            "target_description": "Customer churn label",
            "output_format": "One class label per customer.",
        },
        "evaluation": {
            "primary_metric": "f1",
            "validation_strategy": "train/validation/test split",
        },
        "missing_information": {"critical": [], "optional": []},
        "user_facing_response": "Accepted.",
    }
    data.update(overrides)
    return TaskDefinition.model_validate(data)


def test_infer_schema_uses_explicit_target_and_detects_id_columns():
    # 测试显式 target_column 优先，并且 ID 字段会被识别为 identifier/drop。
    dataframe = pd.DataFrame(
        {
            "customer_id": [f"C{index}" for index in range(12)],
            "age": list(range(20, 32)),
            "churn": [0, 1] * 6,
        }
    )
    profile = profile_table(dataframe)

    schema = infer_schema(profile, task_definition=_task_definition())

    assert schema["target_column"] == "churn"
    assert schema["feature_columns"] == ["age"]
    assert schema["id_columns"] == ["customer_id"]
    assert schema["drop_columns"] == ["customer_id"]
    assert _column(schema, "churn")["role"] == "target"
    assert _column(schema, "customer_id")["recommended_use"] == "drop"


def test_infer_schema_detects_forecasting_time_index():
    # 测试 forecasting 任务会把显式 time_column 识别为 time_index。
    dataframe = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "sales": [10.0, 12.0, 13.0],
            "store": ["A", "A", "A"],
        }
    )
    profile = profile_table(dataframe)
    task = _task_definition(
        task_type="forecasting",
        input_mode={
            "data_type": "time_series",
            "required_inputs": ["sales history"],
            "target_column": "sales",
            "time_column": "date",
        },
        output_mode={
            "prediction_type": "future_value",
            "target_description": "Future sales",
            "output_format": "One forecast per date.",
        },
    )

    schema = infer_schema(profile, task_definition=task)

    assert schema["target_column"] == "sales"
    assert schema["time_columns"] == ["date"]
    assert _column(schema, "date")["recommended_use"] == "time_index"


def test_infer_schema_marks_possible_target_when_no_explicit_target():
    # 测试没有显式 target 时，像 label/churn 这样的列会进入 target_candidates。
    dataframe = pd.DataFrame(
        {
            "feature": [1, 2, 3, 4],
            "label": [0, 1, 0, 1],
        }
    )
    profile = profile_table(dataframe)

    schema = infer_schema(profile, task_definition={"task_type": "classification"})

    assert schema["target_column"] is None
    assert schema["target_candidates"] == ["label"]
    assert _column(schema, "label")["role"] == "target_candidate"
    assert schema["warnings"] == [
        "no explicit target column matched; review target_candidates."
    ]


def test_infer_schema_identifies_text_and_high_cardinality_categorical():
    # 测试长文本会识别为 text，高基数字符串会标记为 high_cardinality_categorical。
    dataframe = pd.DataFrame(
        {
            "review": [
                "This customer wrote a long complaint about billing issues.",
                "Another long free text message with multiple words.",
                "Short but still sentence like text.",
            ],
            "city_code": ["A001", "A002", "A003"],
        }
    )
    profile = profile_table(dataframe)

    schema = infer_schema(profile, categorical_unique_threshold=2)

    assert _column(schema, "review")["semantic_type"] == "text"
    assert _column(schema, "review")["recommended_use"] == "use_text"
    assert _column(schema, "city_code")["semantic_type"] == "id"


def test_infer_schema_does_not_require_target_for_clustering():
    # 测试 clustering 任务不会强制要求 target_column。
    dataframe = pd.DataFrame(
        {
            "age": [20, 30, 40],
            "income": [100.0, 200.0, 300.0],
        }
    )
    profile = profile_table(dataframe)

    schema = infer_schema(profile, task_definition={"task_type": "clustering"})

    assert schema["target_column"] is None
    assert schema["feature_columns"] == ["age", "income"]
    assert schema["warnings"] == []


def test_infer_schema_output_is_json_serializable():
    # 测试 schema_infer 输出可以直接 JSON 序列化，方便写文件或放进 prompt。
    dataframe = pd.DataFrame({"x": [1, 2], "y": [0, 1]})
    profile = profile_table(dataframe)

    schema = infer_schema(profile, target_column="y")

    json.dumps(schema, ensure_ascii=False)
    assert schema["target_column"] == "y"
