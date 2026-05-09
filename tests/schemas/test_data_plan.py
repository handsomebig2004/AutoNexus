from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from src.schemas.data_plan import DataProcessPlan


def _valid_plan(**overrides):
    data = {
        "plan_name": "Customer churn preprocessing",
        "status": "executable",
        "task_type": "classification",
        "input_files": ["tasks/task_0/data/raw/train.csv"],
        "target_column": "churn",
        "id_columns": ["customer_id"],
        "feature_columns": ["age", "gender", "tenure"],
        "drop_columns": ["customer_id"],
        "missing_value_plan": [
            {
                "columns": ["age"],
                "strategy": "median",
                "reason": "Age has a small missing rate.",
            }
        ],
        "categorical_encoding_plan": [
            {
                "columns": ["gender"],
                "encoding": "one_hot",
                "handle_unknown": "ignore",
            }
        ],
        "numeric_scaling_plan": [
            {
                "columns": ["age", "tenure"],
                "scaling": "standard",
            }
        ],
        "split_strategy": {
            "strategy": "stratified",
            "train_size": 0.7,
            "validation_size": 0.1,
            "test_size": 0.2,
            "stratify_column": "churn",
            "random_state": 42,
        },
        "output_artifacts": [
            {
                "artifact_type": "train_data",
                "path": "tasks/task_0/runs/run_0/data/processed/train.csv",
            },
            {
                "artifact_type": "feature_report",
                "path": "tasks/task_0/runs/run_0/metadata/feature_report.json",
            },
        ],
        "quality_issues_to_handle": ["class_imbalance"],
        "assumptions": [],
        "warnings": [],
        "user_facing_response": "Data plan is executable.",
        "downstream_notes": {"for_train_agent": ["Use feature_report.json."]},
    }
    data.update(overrides)
    return DataProcessPlan.model_validate(data)


def test_data_process_plan_accepts_complete_executable_plan():
    # 测试完整可执行的数据处理计划可以通过 schema 校验。
    plan = _valid_plan()

    assert plan.status == "executable"
    assert plan.target_column == "churn"
    assert plan.split_strategy.strategy == "stratified"
    assert plan.output_artifacts[0].artifact_type == "train_data"


def test_data_process_plan_requires_target_for_supervised_tasks():
    # 测试分类、回归、预测任务的可执行计划必须包含 target_column。
    with pytest.raises(ValidationError, match="requires target_column"):
        _valid_plan(target_column=None)


def test_data_process_plan_requires_time_column_for_forecasting():
    # 测试 forecasting 可执行计划必须包含 time_column。
    with pytest.raises(ValidationError, match="requires time_column"):
        _valid_plan(
            task_type="forecasting",
            target_column="sales",
            time_column=None,
            split_strategy={
                "strategy": "time_based",
                "train_size": 0.8,
                "test_size": 0.2,
                "time_column": "date",
            },
        )


def test_data_process_plan_allows_clustering_without_target():
    # 测试 clustering 任务不需要 target_column。
    plan = _valid_plan(
        task_type="clustering",
        target_column=None,
        split_strategy={"strategy": "none"},
    )

    assert plan.task_type == "clustering"
    assert plan.target_column is None


def test_constant_missing_strategy_requires_fill_value():
    # 测试 constant 缺失值填补策略必须提供 fill_value。
    with pytest.raises(ValidationError, match="requires fill_value"):
        _valid_plan(
            missing_value_plan=[
                {
                    "columns": ["gender"],
                    "strategy": "constant",
                }
            ]
        )


def test_split_strategy_validates_required_fields():
    # 测试分层切分必须指定 stratify_column，时间切分必须指定 time_column。
    with pytest.raises(ValidationError, match="requires stratify_column"):
        _valid_plan(split_strategy={"strategy": "stratified"})

    with pytest.raises(ValidationError, match="requires time_column"):
        _valid_plan(
            task_type="forecasting",
            target_column="sales",
            time_column="date",
            split_strategy={"strategy": "time_based"},
        )


def test_need_info_and_rejected_require_user_response():
    # 测试 need_info/rejected 计划必须带有可返回给用户的说明。
    with pytest.raises(ValidationError, match="requires user_facing_response"):
        _valid_plan(
            status="need_info",
            input_files=[],
            target_column=None,
            feature_columns=[],
            output_artifacts=[],
            user_facing_response="",
        )

    with pytest.raises(ValidationError, match="requires user_facing_response"):
        _valid_plan(
            status="rejected",
            input_files=[],
            target_column=None,
            feature_columns=[],
            output_artifacts=[],
            user_facing_response="",
        )


def test_data_process_plan_rejects_unknown_extra_fields():
    # 测试 schema 会拒绝未定义字段，避免 LLM 输出随意扩展结构。
    with pytest.raises(ValidationError):
        _valid_plan(unexpected_field=True)


def test_data_process_plan_output_is_json_serializable():
    # 测试 DataProcessPlan 可以输出 JSON 可序列化的字典。
    plan = _valid_plan()
    data = plan.to_json_dict()

    json.dumps(data, ensure_ascii=False)
    assert data["plan_name"] == "Customer churn preprocessing"
