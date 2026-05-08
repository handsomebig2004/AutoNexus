from __future__ import annotations

import json

import pandas as pd

from src.tools.data_profiler import profile_table
from src.tools.data_quality import check_data_quality
from src.tools.schema_infer import infer_schema


def _issue_types(report):
    return [issue["issue_type"] for issue in report["issues"]]


def _issue(report, issue_type):
    return next(issue for issue in report["issues"] if issue["issue_type"] == issue_type)


def test_check_data_quality_reports_target_missing_values_as_blocking():
    # 测试监督任务的 target 有缺失值时，会生成阻塞性错误。
    dataframe = pd.DataFrame(
        {
            "age": [20, 30, 40, 50],
            "churn": [0, 1, None, 0],
        }
    )
    profile = profile_table(dataframe)
    schema = infer_schema(profile, target_column="churn")

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "classification"},
    )

    assert report["can_continue"] is False
    assert "target_missing_values" in _issue_types(report)
    assert _issue(report, "target_missing_values")["blocking"] is True
    assert report["summary"]["blocking_issue_count"] == 1


def test_check_data_quality_reports_single_class_and_class_imbalance():
    # 测试分类 target 只有一个类别会阻塞，类别极度不均衡会给 warning。
    single_class = pd.DataFrame({"x": range(5), "label": [1, 1, 1, 1, 1]})
    single_profile = profile_table(single_class)
    single_schema = infer_schema(single_profile, target_column="label")

    single_report = check_data_quality(
        single_profile,
        schema=single_schema,
        task_definition={"task_type": "classification"},
        min_rows_warning=0,
    )
    assert "target_single_class" in _issue_types(single_report)
    assert _issue(single_report, "target_single_class")["blocking"] is True

    imbalanced = pd.DataFrame({"x": range(20), "label": [0] * 19 + [1]})
    imbalanced_profile = profile_table(imbalanced)
    imbalanced_schema = infer_schema(imbalanced_profile, target_column="label")

    imbalanced_report = check_data_quality(
        imbalanced_profile,
        schema=imbalanced_schema,
        task_definition={"task_type": "classification"},
        min_rows_warning=0,
    )
    assert "class_imbalance" in _issue_types(imbalanced_report)
    assert _issue(imbalanced_report, "class_imbalance")["severity"] == "warning"


def test_check_data_quality_reports_missingness_duplicates_and_constant_columns():
    # 测试高缺失列、重复行、常量列都会被记录为数据质量问题。
    dataframe = pd.DataFrame(
        {
            "constant": ["A", "A", "A", "A"],
            "mostly_missing": [None, None, None, 1],
            "target": [0, 1, 0, 1],
        }
    )
    dataframe = pd.concat([dataframe, dataframe.iloc[[0]]], ignore_index=True)
    profile = profile_table(dataframe)
    schema = infer_schema(profile, target_column="target")

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "classification"},
        high_missing_rate=0.5,
        min_rows_warning=0,
    )

    issue_types = _issue_types(report)
    assert "duplicate_rows" in issue_types
    assert "constant_column" in issue_types
    assert "high_missing_rate" in issue_types


def test_check_data_quality_blocks_when_supervised_task_has_no_target():
    # 测试监督任务没有 target 时，会生成 target_missing 阻塞错误。
    dataframe = pd.DataFrame({"x": [1, 2, 3], "z": [4, 5, 6]})
    profile = profile_table(dataframe)
    schema = infer_schema(profile, task_definition={"task_type": "classification"})

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "classification"},
        min_rows_warning=0,
    )

    assert report["can_continue"] is False
    assert "target_missing" in _issue_types(report)


def test_check_data_quality_checks_forecasting_time_index():
    # 测试 forecasting 任务缺少 time_index 时，会生成阻塞错误。
    dataframe = pd.DataFrame({"sales": [10, 12, 13], "promo": [0, 1, 0]})
    profile = profile_table(dataframe)
    schema = infer_schema(
        profile,
        task_definition={
            "task_type": "forecasting",
            "input_mode": {"target_column": "sales"},
        },
    )

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "forecasting"},
        min_rows_warning=0,
    )

    assert "time_index_missing" in _issue_types(report)
    assert _issue(report, "time_index_missing")["blocking"] is True


def test_check_data_quality_warns_for_high_cardinality_categorical():
    # 测试 schema 标出的高基数类别特征会生成 warning，提醒不要朴素 one-hot。
    dataframe = pd.DataFrame(
        {
            "city": [f"City{index}" for index in range(12)],
            "target": [0, 1] * 6,
        }
    )
    profile = profile_table(dataframe)
    schema = infer_schema(
        profile,
        target_column="target",
        high_cardinality_threshold=1.1,
        categorical_unique_threshold=5,
    )

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "classification"},
        min_rows_warning=0,
    )

    assert "high_cardinality_categorical" in _issue_types(report)
    assert _issue(report, "high_cardinality_categorical")["columns"] == ["city"]


def test_check_data_quality_output_is_json_serializable():
    # 测试 data_quality 输出可以直接 JSON 序列化，方便写文件或传给 LLM。
    dataframe = pd.DataFrame({"x": [1, 2, 3], "target": [0, 1, 0]})
    profile = profile_table(dataframe)
    schema = infer_schema(profile, target_column="target")

    report = check_data_quality(
        profile,
        schema=schema,
        task_definition={"task_type": "classification"},
        min_rows_warning=0,
    )

    json.dumps(report, ensure_ascii=False)
    assert set(report) == {
        "dataset_name",
        "task_type",
        "issues",
        "summary",
        "recommended_actions",
        "can_continue",
    }
