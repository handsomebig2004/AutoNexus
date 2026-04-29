# AutoNexus

autoNexus 是一个面向自动建模流程的多 Agent 项目。当前目标是先让大模型生成多种可运行的建模方案，统一执行后比较结果；模型/Agent 的迭代优化暂时放到后续阶段。

## Agent 分工

| Agent | 职责 |
| --- | --- |
| `requirement_agent` | 理解用户需求，把问题转化为可建模的问题，并明确所需输入和输出。 |
| `research_agent` | 查找数据与相关文献，生成模型方案，并筛选可用数据和可用方法。 |
| `data_agent` | 根据数据和方法特征完成数据清洗、预处理和特征工程。 |
| `train_agent` | 编写模型训练代码并运行训练。 |
| `evaluation_agent` | 评估实验结果，辅助比较不同方案。 |
检查的时候考虑使用一个固定的脚本

## 项目目录结构

```text
.
├── config/                 # YAML 等配置文件
├── src/                    # 项目核心代码
│   ├── agents/             # 各类 Agent 的源代码
│   ├── interfaces/         # CLI、stdin、文件、未来 Web API 等外部输入接口
│   ├── models/             # 总结后的模型信息，供 LLM Agent 参考
│   ├── prompts/            # 固定提示词
│   ├── schemas/            # Agent 输出的标准格式
│   ├── skills/             # 输入给 LLM Agent 的技能文档
│   ├── tools/              # 外部连接、代码执行、数据处理等工具
│   └── utils/              # Agent 和 tools 之间复用的小函数
└── tasks/                  # 每次任务运行产生的任务目录
```

### `tasks/` 目录约定

每运行一个 `task`，可能会产生多个建模方法；每个方法对应一个 `run_xxx`。

```text
tasks/
└── task_xxx/
    ├── data/
    │   ├── raw/                    # research_agent 找到的原始数据
    │   └── processed/run_xxx/      # data_agent 处理后的数据
    ├── doc/                        # research_agent 找到的文献或资料
    ├── src/
    │   └── run_xxx/                # 大模型为该 run 生成的代码
    │       ├── preprocess/         # data_agent 生成的预处理代码
    │       └── train/              # train_agent 生成的训练代码
    └── outputs/run_xxx/            # 模型运行结果、日志、审查记录等任务内产物
```

约定：

- `data/raw/` 保存原始数据。
- `data/processed/run_xxx/` 保存某个 run 对应的处理后数据。
- `doc/` 保存文献、数据说明、研究记录等可被其他 Agent 读取的资料。
- `src/run_xxx/` 保存该 run 的生成代码。
- `outputs/run_xxx/` 保存该 run 的输出结果、日志和只在当前 task 内使用的审查记录。

### `config/` 目录约定

`config/` 用来保存各种 YAML 配置文件。后续配置变多后，可以按 Agent、运行环境或任务类型继续分层。

### `src/` 目录约定

| 目录 | 说明 |
| --- | --- |
| `src/agents/` | 各类 Agent 的源代码。每个 Agent 应输出固定结构，方便后续工具或其他 Agent 消费。 |
| `src/interfaces/` | 外部输入接口。负责把命令行、文件、stdin 或未来 Web API 的输入统一转成内部 schema。 |
| `src/prompts/` | 各类模型的固定提示词。后续可以考虑加入 `manager` 或 `memory`，在提示词进入 Agent 前做统一处理。 |
| `src/models/` | 经过总结的模型信息，可输入给 LLM Agent，辅助它按指定模型写代码。 |
| `src/skills/` | 输入给 LLM Agent 的技能文档，例如如何找论文、如何使用 `models/` 中的模型信息。 |
| `src/schemas/` | Agent 输出的标准格式定义。 |
| `src/tools/` | 与外部连接、代码执行、数据处理相关的工具函数或类，后续可加入安全检查。 |
| `src/utils/` | Agent 和 tools 之间复用的小函数。后续如果做 Agent 记忆，也可以在这里扩展 `memory/` 等目录。 |

## 输入接口说明

AutoNexus 的输入层和 Agent 层是分离的。命令行、文件、PowerShell 管道、未来网页接口都不应该直接把字符串塞进某个 Agent，而是先统一转换成 `UserRequest`。

统一输入对象定义在：

```text
src/schemas/user_request.py
```

结构如下：

```json
{
  "request_text": "预测客户是否流失",
  "source": "stdin",
  "source_path": null,
  "metadata": {
    "interface": "cli"
  }
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `request_text` | 用户原始需求文本，后续会传给 `requirement_agent`。 |
| `source` | 输入来源，目前支持 `cli`、`file`、`stdin`、`web`。 |
| `source_path` | 如果来源是文件，记录文件路径；否则为 `null`。 |
| `metadata` | 额外信息，例如接口类型、文件编码、用户 ID、前端来源等。 |

### 为什么要有输入接口层

这样设计是为了降低耦合：

```text
CLI / 文件 / PowerShell 管道 / Web API
        ↓
UserRequest
        ↓
requirement_agent
        ↓
TaskDefinition
```

`requirement_agent` 只接收 `UserRequest`，不关心用户输入来自命令行、文件还是网页。以后从 CLI 换成 Web API 时，只需要新增 Web 接口，把 HTTP 请求转换成同一个 `UserRequest`，不用改 Agent 本身。

### 当前支持的输入方式

当前命令行接口在：

```text
src/interfaces/cli.py
```

支持三种输入方式。

#### 1. 直接传入文本

```powershell
conda activate automl
python -m src.interfaces.cli --text "预测客户是否流失"
```

输出：

```json
{
  "request_text": "预测客户是否流失",
  "source": "cli",
  "source_path": null,
  "metadata": {
    "interface": "cli"
  }
}
```

适合快速测试或脚本调用。

#### 2. 从文件读取

```powershell
conda activate automl
python -m src.interfaces.cli --file .\request.txt
```

默认文件编码是 `utf-8-sig`，可以兼容带 BOM 的 UTF-8 文件。如果需要指定编码：

```powershell
python -m src.interfaces.cli --file .\request.txt --encoding utf-8
```

输出里的 `source` 会是 `file`，并记录 `source_path`：

```json
{
  "request_text": "预测未来7天销量",
  "source": "file",
  "source_path": "request.txt",
  "metadata": {
    "interface": "cli",
    "encoding": "utf-8-sig"
  }
}
```

适合较长需求、从文档中复制出的任务描述，或者后续批量任务。

#### 3. 从 PowerShell 管道 / stdin 读取

```powershell
conda activate automl
"给客户做无监督分群" | python -m src.interfaces.cli
```

也可以：

```powershell
Get-Content .\request.txt | python -m src.interfaces.cli
```

输出里的 `source` 会是 `stdin`：

```json
{
  "request_text": "给客户做无监督分群",
  "source": "stdin",
  "source_path": null,
  "metadata": {
    "interface": "cli"
  }
}
```

如果 PowerShell 管道传中文时出现乱码，可以先设置：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

### 写出标准输入 JSON

CLI 可以把标准化后的 `UserRequest` 写入文件：

```powershell
python -m src.interfaces.cli --text "预测房价" --output tasks\user_request.json
```

这会同时：

- 在终端打印 `UserRequest`
- 将同样内容写入 `tasks/user_request.json`

后续 pipeline 可以直接读取这个 JSON，作为 task 的原始输入记录。

### 如何传给 requirement_agent

后续 `requirement_agent` 推荐只接收 `UserRequest`，不要接收裸字符串：

```python
from src.interfaces.cli import read_user_request_from_cli
from src.agents.requirement_agent import RequirementAgent

user_request = read_user_request_from_cli()

agent = RequirementAgent()
task_definition = agent.run(user_request)
```

`requirement_agent` 内部应该使用：

```python
user_request.request_text
```

作为 LLM prompt 的用户需求输入，同时把这些信息写入日志：

```python
user_request.source
user_request.source_path
user_request.metadata
```

这样可以追踪任务来自哪里，也方便复现实验。

### 未来 Web API 如何接入

以后如果加网页或 HTTP API，不需要改 `requirement_agent`，只需要在 Web 层构造同一个 schema：

```python
from src.schemas import UserRequest

user_request = UserRequest(
    request_text=payload["text"],
    source="web",
    metadata={
        "user_id": payload.get("user_id"),
        "session_id": payload.get("session_id"),
    },
)

task_definition = requirement_agent.run(user_request)
```

也就是说：

```text
CLI 和 Web 的区别只存在于 interfaces 层。
Agent 和 pipeline 只认识 UserRequest。
```

### 输入接口的边界

`src/interfaces/cli.py` 只负责：

- 读取 `--text`
- 读取 `--file`
- 读取 stdin / PowerShell 管道
- 转成 `UserRequest`
- 可选写出 JSON

它不负责：

- 调用 LLM
- 判断任务类型
- 创建模型方案
- 创建 run
- 执行 pipeline

这些逻辑应该放在 `agents/` 或后续的 `pipeline/` 中，避免输入接口和业务流程耦合。

## requirement_agent 说明

`requirement_agent` 是 AutoNexus pipeline 的第一个 Agent，也是一个“建模闸门”。它的职责不是直接建模，而是判断用户需求是否可以进入后续自动建模流程。

实现文件：

```text
src/agents/requirement_agent.py
src/prompts/requirement_agent.md
src/schemas/requirement.py
src/utils/requirement_validation.py
```

### 输入

`requirement_agent` 接收标准化后的 `UserRequest`，而不是裸字符串。

```python
from src.schemas import UserRequest

user_request = UserRequest(
    request_text="我有客户历史消费数据和是否流失标签，想预测客户是否会流失",
    source="cli",
)
```

字段来源可以是：

- `--text`
- `--file`
- PowerShell 管道 / stdin
- 未来 Web API

只要转换成 `UserRequest`，后续 `requirement_agent` 的使用方式都一样。

### 输出

`requirement_agent` 输出 `TaskDefinition`，定义在：

```text
src/schemas/requirement.py
```

核心结构如下：

```json
{
  "task_name": "客户流失预测",
  "task_type": "classification",
  "decision": "accepted",
  "should_model": true,
  "problem_statement": "基于客户历史消费数据预测客户是否会流失。",
  "input_mode": {
    "data_type": "tabular",
    "required_inputs": ["客户历史消费数据", "客户是否流失标签"],
    "optional_inputs": [],
    "target_column": "churn",
    "id_columns": ["customer_id"],
    "time_column": null,
    "data_granularity": null,
    "known_data_sources": []
  },
  "output_mode": {
    "prediction_type": "class_label",
    "target_description": "客户是否流失",
    "output_format": "每个客户输出一个流失/不流失类别"
  },
  "constraints": {
    "must_have": [],
    "must_not": [],
    "resource_limits": [],
    "privacy_or_safety": []
  },
  "evaluation": {
    "primary_metric": "f1",
    "secondary_metrics": ["accuracy"],
    "validation_strategy": "train/validation/test split",
    "metric_reasoning": "客户流失任务可能存在类别不均衡，f1 比 accuracy 更稳妥。"
  },
  "assumptions": [],
  "missing_information": {
    "critical": [],
    "optional": []
  },
  "user_facing_response": "已识别为分类任务，可以进入后续建模。",
  "downstream_notes": {
    "for_research_agent": [],
    "for_data_agent": [],
    "for_train_agent": [],
    "for_evaluation_agent": []
  },
  "raw_user_request": "我有客户历史消费数据和是否流失标签，想预测客户是否会流失"
}
```

### 支持的任务类型

当前只支持四类建模任务：

| task_type | 含义 | 示例 |
| --- | --- | --- |
| `classification` | 预测离散类别、标签、状态、是否发生等。 | 预测客户是否流失、判断邮件是否垃圾邮件。 |
| `regression` | 预测连续数值。 | 预测房价、预测评分、预测温度。 |
| `forecasting` | 基于时间顺序预测未来值或趋势。 | 预测未来 7 天销量、预测下月用电量。 |
| `clustering` | 无监督发现群组或样本结构。 | 客户分群、用户画像、行为模式发现。 |

其他需求统一归为：

```text
task_type = unknown
decision = rejected
should_model = false
```

例如：

- 只要求写报告
- 只要求查资料
- 只要求做可视化
- 只要求搭系统
- 没有明确机器学习建模目标

这些不会进入后续建模。

### 决策状态

`requirement_agent` 不只是判断 `task_type`，还会输出 `decision`。

| decision | 是否进入建模 | 含义 |
| --- | --- | --- |
| `accepted` | 是 | 任务类型支持，且关键信息和可选确认都已满足。 |
| `need_info` | 否 | 任务类型支持，但缺少关键建模信息，必须让用户补充。 |
| `need_confirmation` | 暂停 | 关键信息足够，但缺少可选信息；用户可以补充，也可以回复 `yes` 直接继续。 |
| `rejected` | 否 | 不属于当前支持的四类建模任务。 |

后续 pipeline 推荐这样判断：

```python
task_definition = requirement_agent.run(user_request)

if task_definition.decision == "accepted":
    continue_pipeline(task_definition)

elif task_definition.decision == "need_confirmation":
    return task_definition.user_facing_response

else:
    return task_definition.user_facing_response
```

### critical / optional 缺失信息

`missing_information` 被拆成两类：

```json
{
  "critical": [],
  "optional": []
}
```

含义：

| 字段 | 是否阻塞建模 | 含义 |
| --- | --- | --- |
| `critical` | 是 | 不补就不能安全建模的信息。 |
| `optional` | 需要用户确认 | 补了会更好，但用户确认后可以继续建模。 |

例如 forecasting 任务：

```json
{
  "decision": "need_info",
  "should_model": false,
  "missing_information": {
    "critical": [
      "请说明要预测的目标变量。",
      "请说明时间字段或时间粒度。",
      "请说明希望预测未来多久。"
    ],
    "optional": [
      "如果有节假日、促销、价格等外生变量，可以一起提供。"
    ]
  }
}
```

这种情况必须补充 `critical`，不能进入建模。

如果只有 optional 缺失：

```json
{
  "decision": "need_confirmation",
  "should_model": false,
  "missing_information": {
    "critical": [],
    "optional": [
      "建议补充类别分布，用于判断是否需要处理类别不均衡。"
    ]
  }
}
```

这种情况会先返回用户。用户可以补充信息，也可以回复：

```text
yes
```

然后系统可以直接进入后续建模，不需要再次调用 `requirement_agent`。

### 用户 yes 后如何继续

如果 `decision == "need_confirmation"`，并且用户回复 `yes`，使用：

```python
from src.utils import confirm_optional_information

task_definition = confirm_optional_information(task_definition)
```

这个函数会：

- 检查当前任务确实是 `need_confirmation`
- 确认 `critical` 为空
- 将 `decision` 改成 `accepted`
- 将 `should_model` 改成 `true`
- 清空 `missing_information`
- 把“用户确认缺少可选信息仍继续建模”写入 `assumptions`

它不会重新调用 LLM，也不会重新跑 `requirement_agent`。

### 内部处理逻辑

`RequirementAgent.run()` 的流程：

```text
UserRequest
  ↓
读取 src/prompts/requirement_agent.md
  ↓
拼接用户需求
  ↓
调用 LLMClient.generate()
  ↓
记录 llm_calls.jsonl
  ↓
从 LLM 输出中提取 JSON
  ↓
使用 TaskDefinition 做 schema 校验
  ↓
使用 normalize_requirement_gate() 做确定性业务校验
  ↓
必要时把 unsafe accepted 降级为 need_info / need_confirmation
  ↓
写 task_definition.json
  ↓
写 task.jsonl 摘要
  ↓
返回 TaskDefinition
```

其中：

- LLM 负责理解自然语言。
- `TaskDefinition` 负责结构校验。
- `normalize_requirement_gate()` 负责最终闸门校验。
- 只有 `accepted` 才允许进入后续 Agent。

### 确定性验证逻辑

确定性验证在：

```text
src/utils/requirement_validation.py
```

主要函数：

```python
validate_requirement_for_modeling(task_definition)
normalize_requirement_gate(task_definition)
confirm_optional_information(task_definition)
```

验证内容包括：

- `task_type` 必须是四类支持任务之一。
- `decision` 必须是 `accepted` 才能直接建模。
- `should_model` 必须为 `true` 才能直接建模。
- `missing_information.critical` 必须为空。
- `missing_information.optional` 必须为空，或者经过用户 `yes` 确认。
- `input_mode.data_type` 不能是 `unknown`。
- `input_mode.required_inputs` 不能为空。
- `classification` / `regression` 必须有 `target_column`。
- `forecasting` 必须有 `target_column` 和 `time_column`。
- `output_mode.prediction_type` 不能是 `unknown`。
- `output_mode.target_description` 不能为空。
- `output_mode.output_format` 不能为空。
- `evaluation.primary_metric` 不能为空。

如果 LLM 输出 `accepted`，但确定性验证发现关键信息不全，会自动变成：

```text
decision = need_info
should_model = false
```

如果只有可选信息缺失，会自动变成：

```text
decision = need_confirmation
should_model = false
```

### 如何使用 requirement_agent

最小用法：

```python
from src.agents.requirement_agent import RequirementAgent
from src.schemas import UserRequest

user_request = UserRequest(
    request_text="我有客户历史消费数据和是否流失标签，想预测客户是否会流失",
    source="cli",
)

agent = RequirementAgent()
task_definition = agent.run(user_request)
print(task_definition.decision)
```

带 task 日志和输出文件：

```python
from src.agents.requirement_agent import RequirementAgent
from src.schemas import UserRequest
from src.utils import TaskLogger

task_dir = "tasks/task_0"
logger = TaskLogger(task_dir)

agent = RequirementAgent(task_logger=logger)
task_definition = agent.run(
    UserRequest(
        request_text="我有客户历史消费数据和是否流失标签，想预测客户是否会流失",
        source="cli",
    ),
    output_path="tasks/task_0/metadata/task_definition.json",
)
```

如果要从 CLI 输入接入：

```python
from src.interfaces.cli import read_user_request_from_cli
from src.agents.requirement_agent import RequirementAgent

user_request = read_user_request_from_cli()
task_definition = RequirementAgent().run(user_request)
```

### requirement_agent 相关文件

| 文件 | 作用 |
| --- | --- |
| `src/agents/requirement_agent.py` | Agent 主体逻辑：调用 LLM、解析输出、校验、写日志和输出。 |
| `src/prompts/requirement_agent.md` | 固定提示词：说明支持任务、决策规则、输出 JSON 格式。 |
| `src/schemas/requirement.py` | `TaskDefinition` schema：约束输出结构和基础规则。 |
| `src/schemas/user_request.py` | `UserRequest` schema：统一 CLI、文件、stdin、Web 输入。 |
| `src/utils/requirement_validation.py` | 确定性业务校验：判断是否能进入后续建模。 |
| `src/utils/text.py` | 从 LLM 回复中提取 JSON。 |
| `src/utils/ids.py` | 生成 `llm_0001` 这类 LLM 调用编号。 |
| `src/tools/llm_client.py` | 访问外部 LLM。 |
| `src/utils/task_logger.py` | 写入 `task.jsonl` 和 `llm_calls.jsonl`。 |

## 工具规划

只考虑了 `data_agent`，其他的后面再说（划掉的是目前已实现的）

| Tool | 文件 | 作用 |
| --- | --- | --- |
| ~~LLM访问工具~~| `src/tools/llm_client.py` | 访问外部LLM |
| ~~数据读取工具~~ | `src/tools/data_loader.py` | 统一读取 `csv`、`xlsx`、`json`、`parquet`，返回 DataFrame 和基础信息。 |
| 数据概览工具 | `src/tools/data_profiler.py` | 统计行列数、字段类型、缺失率、唯一值、样例值、标签分布等；也可由 `research_agent` 调用，用来总结数据集概况。 |
| Schema 推断工具 | `src/tools/schema_infer.py` | 推断字段类型，如数值、类别、文本、时间、ID、标签列候选等。该工具是否必要待定。 |
| 数据质量检查工具 | `src/tools/data_quality.py` | 检查重复行、常量列、高缺失列、异常值、类别过多、数据泄漏风险等。 |
| 预处理代码生成辅助 | `src/tools/code_writer.py` | 将 LLM 输出的 `preprocess.py` 安全写入 run 目录。 |
| 预处理代码校验工具 | `src/tools/code_validator.py` | 检查生成脚本是否包含规定入口函数、危险导入、危险系统调用等；可以后置实现。 |
| 预处理代码运行工具 | `src/tools/code_runner.py` | 在指定 run 目录运行 `preprocess.py`，捕获 `stdout`、`stderr` 和退出码。 |
| 产物管理工具 | `src/tools/artifact_manager.py` | 管理 processed data、feature report、preprocessor、日志路径等产物。 |
| 数据切分工具 | `src/tools/splitter.py` | 提供标准 train/val/test split，并支持分类任务 stratify。 |
| 特征报告工具 | `src/tools/feature_report.py` | 生成 `feature_report.json`，供 `train_agent` 使用。 |

## Utils 规划

| Util | 文件 | 作用 |
| --- | --- | --- |
| ~~路径工具~~ | `src/utils/numbered_paths.py` | 创建 `path/prefix_xxx` 目录：扫描已有编号，取最大编号并创建下一个目录；使用 `filelock` 防止并发重复，返回已创建好的 `Path`。 |
| ~~配置读取~~ | `src/utils/config.py` | 读取 `settings.yaml`及其中的Agent 配置和默认参数。 |
| ~~JSON/YAML IO~~ | `src/utils/io.py` | 统一读写 `json`、`yaml`、`txt`、`md`，避免各处重复实现。 |
| ~~任务日志工具~~ | `src/utils/task_logger.py` | 写入 `task.jsonl` 和 `llm_calls.jsonl`。 |
| ~~run 日志工具~~ | `src/utils/run_logger.py` | 写入某个 run 的 `run.jsonl`。 |
| ~~文本格式工具~~ | `src/utils/text.py` | 清理 LLM 输出，例如从回复中提取 Python 代码块或 JSON。 |
| ~~ID 生成工具~~ | `src/utils/ids.py` | 生成 `llm_0001` 等稳定编号，也可从 JSONL 中扫描下一个编号。 |
| 哈希/版本工具 | `src/utils/hash.py` | 记录原始数据 hash 和脚本 hash，方便复现。 |
| ~~错误类型定义~~ | `src/utils/errors.py` | 定义 `DataValidationError`、`GeneratedCodeError` 等异常类型。 |
| ~~日志事件/内容生成~~ | `src/utils/log_events.py` | 生成日志事件里需要的结构化信息。 |
| ~~需求闸门验证~~ | `src/utils/requirement_validation.py` | 验证 `TaskDefinition` 是否能进入建模，并处理 optional 信息确认。 |

## 错误处理规划

错误类型集中定义在 `src/utils/errors.py`，其他模块只负责在合适的边界捕获并转化错误。

| 模块 | 处理方式 |
| --- | --- |
| `src/utils/errors.py` | 只定义错误类型。 |
| `src/tools/llm_client.py` | 捕获 API 错误，并转成 `LLMError`。 |
| `schema_parser.py` / `agent.py` | 捕获输出解析失败，并转成 `LLMOutputParseError`。 |
| `src/tools/code_validator.py` | 检查生成代码，失败时抛出 `GeneratedCodeValidationError`。 |
| `src/tools/code_runner.py` | 脚本运行失败时抛出 `GeneratedCodeExecutionError`。 |
| `pipeline/runner.py` | 根据错误类型决定重试、终止、降级或继续执行。 |

## 日志说明

日志系统采用 JSONL 格式，即一行一个 JSON 对象。这样既可以直接打开查看，也方便后续用程序统计、筛选和生成实验报告。

当前日志分为三类：

```text
tasks/
└── task_xxx/
    ├── logs/
    │   ├── task.jsonl        # task 级摘要日志
    │   └── llm_calls.jsonl   # LLM 完整调用日志
    └── runs/
        └── run_xxx/
            └── logs/
                └── run.jsonl # run 级执行日志
```

三类日志的职责不同：

| 日志文件 | 粒度 | 主要用途 |
| --- | --- | --- |
| `task.jsonl` | 整个任务 | 记录任务级时间线、Agent 开始/结束、run 创建/完成、错误摘要、最优方案等。 |
| `llm_calls.jsonl` | LLM 调用 | 记录完整 prompt、system prompt、response、模型、provider、token 使用量和错误信息。 |
| `run.jsonl` | 单个 run | 记录某一个模型方案的代码生成、代码校验、预处理、训练、评估、指标和产物。 |

### 通用日志格式

`task.jsonl` 和 `run.jsonl` 都使用统一事件结构：

```json
{
  "time": "2026-04-28T12:00:00+08:00",
  "level": "INFO",
  "event": "agent_finished",
  "task_id": "task_0",
  "run_id": "run_0",
  "agent": "data_agent",
  "message": "Data agent finished.",
  "data": {
    "duration_seconds": 3.42,
    "output_path": "tasks/task_0/runs/run_0/metadata/feature_report.json"
  }
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `time` | 带时区的 ISO 时间戳。 |
| `level` | 日志级别：`DEBUG`、`INFO`、`WARNING`、`ERROR`、`CRITICAL`。 |
| `event` | 机器可读的事件名，例如 `agent_finished`、`train_failed`。 |
| `task_id` | 当前任务编号，例如 `task_0`。 |
| `run_id` | 当前 run 编号；task 级事件如果不属于某个 run，可以为 `null`。 |
| `agent` | 产生事件的 Agent，例如 `data_agent`、`train_agent`。 |
| `message` | 给人看的简短说明。 |
| `data` | 结构化附加信息，例如路径、指标、耗时、错误类型等。 |

### task 级摘要日志：`task.jsonl`

路径：

```text
tasks/task_xxx/logs/task.jsonl
```

`task.jsonl` 只记录摘要，不保存完整 prompt 或完整模型回复。它用于快速了解一个 task 从创建到结束发生了什么。

建议记录内容：

| 类型 | 事件名示例 | 记录内容 |
| --- | --- | --- |
| task 生命周期 | `task_created`、`task_started`、`task_finished`、`task_failed` | task 创建、开始、结束、失败原因。 |
| Agent 生命周期 | `agent_started`、`agent_finished`、`agent_failed` | 哪个 Agent 开始/结束、耗时、输出文件路径、错误摘要。 |
| LLM 调用摘要 | `llm_call_finished`、`llm_call_failed` | `llm_call_id`、provider、model、status、token 使用量。 |
| run 管理 | `run_created`、`run_started`、`run_finished`、`run_failed` | 创建了哪些 run、每个 run 是否成功、失败位置。 |
| 结果汇总 | `best_run_selected`、`task_report_written` | 最优 run、关键指标、最终报告路径。 |

示例：

```json
{"time":"2026-04-28T12:00:00+08:00","level":"INFO","event":"run_finished","task_id":"task_0","run_id":"run_1","agent":"evaluation_agent","message":"Run finished.","data":{"accuracy":0.91,"metrics_path":"tasks/task_0/runs/run_1/metadata/metrics.json"}}
```

用途：

- 快速查看 task 整体进展。
- 判断失败发生在哪个 Agent 或哪个 run。
- 汇总多个 run 的最终状态。
- 为后续自动生成 task 总结报告提供结构化依据。

对应工具：

```python
from src.utils import TaskLogger

logger = TaskLogger("tasks/task_0")
logger.info("task_created", message="Task created.")
logger.info("run_created", run_id="run_0", data={"model": "random_forest"})
```

### LLM 完整调用日志：`llm_calls.jsonl`

路径：

```text
tasks/task_xxx/logs/llm_calls.jsonl
```

`llm_calls.jsonl` 用来保存完整 LLM 调用记录。它和 `task.jsonl` 分开，是因为 prompt 和 response 可能很长；如果全部塞进 `task.jsonl`，会让 task 摘要变得难读。

建议记录内容：

| 字段 | 含义 |
| --- | --- |
| `llm_call_id` | 本次 LLM 调用的唯一编号，例如 `llm_0001`。 |
| `task_id` | 所属 task。 |
| `run_id` | 如果这次调用属于某个 run，就记录 run 编号。 |
| `agent` | 调用 LLM 的 Agent。 |
| `provider` | 例如 `openai`、`deepseek`。 |
| `model` | 实际使用的模型名。 |
| `status` | `success` 或 `failed`。 |
| `system_prompt` | 完整 system prompt。 |
| `prompt` | 完整 user prompt。 |
| `response` | 完整模型输出。 |
| `error` | 失败时的错误类型和错误消息。 |
| `usage` | token 使用量、耗时等可选信息。 |
| `metadata` | 其他辅助信息，例如 prompt 模板版本、schema 名称。 |

示例：

```json
{"time":"2026-04-28T12:00:00+08:00","llm_call_id":"llm_0001","task_id":"task_0","run_id":"run_0","agent":"data_agent","provider":"deepseek","model":"deepseek-v4-flash","status":"success","system_prompt":"...","prompt":"...","response":"...","error":null,"usage":{"input_tokens":1200,"output_tokens":800},"metadata":{"schema":"PreprocessPlan"}}
```

用途：

- 复盘某个 Agent 当时为什么做出某个决策。
- 调试 LLM 输出格式错误、代码生成错误、幻觉问题。
- 比较不同 prompt 或模型版本的输出质量。
- 为后续 prompt 优化和 Agent 迭代提供数据。

对应工具：

```python
from src.utils import TaskLogger

logger = TaskLogger("tasks/task_0")
logger.log_llm_call(
    llm_call_id="llm_0001",
    agent="data_agent",
    provider="deepseek",
    model="deepseek-v4-flash",
    prompt="...",
    response="...",
    run_id="run_0",
)
```

调用 `log_llm_call()` 时，默认会同时向 `task.jsonl` 写入一条简短摘要 `llm_call_finished`，完整内容仍然只保存在 `llm_calls.jsonl`。

### run 级执行日志：`run.jsonl`

路径：

```text
tasks/task_xxx/runs/run_xxx/logs/run.jsonl
```

`run.jsonl` 记录某一个模型方案的执行细节。它不保存完整 LLM prompt/response，只记录这个 run 的代码、数据、训练、评估和产物状态。

建议记录内容：

| 类型 | 事件名示例 | 记录内容 |
| --- | --- | --- |
| run 生命周期 | `run_created`、`run_started`、`run_finished`、`run_failed` | run 状态、耗时、失败原因。 |
| 方案信息 | `model_plan_loaded` | 模型名称、模型类型、超参数、方案来源。 |
| 代码生成 | `generated_code_written` | `preprocess.py`、`train.py`、`evaluate.py` 路径和 hash。 |
| 代码校验 | `generated_code_validated`、`generated_code_validation_failed` | 入口函数、危险导入、危险系统调用检查结果。 |
| 预处理 | `preprocess_started`、`preprocess_finished`、`preprocess_failed` | 输入数据路径、输出数据路径、样本数量、特征数量、耗时。 |
| 训练 | `train_started`、`train_finished`、`train_failed` | 模型文件路径、训练耗时、最佳参数、验证集指标。 |
| 评估 | `evaluate_started`、`evaluate_finished`、`evaluate_failed` | 测试集指标、评估报告路径、图表路径。 |
| 产物 | `artifact_written` | 模型、数据、图、报告、metrics 文件路径。 |
| 指标 | `metric_recorded` | accuracy、f1、rmse、auc 等指标。 |
| 错误 | `script_failed`、`run_failed` | 错误类型、错误消息、是否可重试。 |

示例：

```json
{"time":"2026-04-28T12:00:00+08:00","level":"INFO","event":"train_finished","task_id":"task_0","run_id":"run_0","agent":"train_agent","message":"Training finished.","data":{"model_path":"tasks/task_0/runs/run_0/artifacts/models/model.pkl","duration_seconds":42.18,"metrics":{"accuracy":0.91,"f1":0.89}}}
```

用途：

- 精确复盘某个模型方案是如何执行的。
- 定位失败发生在预处理、训练、评估还是代码校验阶段。
- 记录每个 run 的模型文件、数据文件、报告文件和指标文件。
- 后续自动比较多个 run，生成实验表格或最优方案报告。

对应工具：

```python
from src.utils import RunLogger

logger = RunLogger("tasks/task_0/runs/run_0")
logger.info("run_started", agent="train_agent")
logger.generated_code_written("preprocess", "generated/preprocess.py", agent="data_agent")
logger.artifact_written("model", "artifacts/models/model.pkl", agent="train_agent")
logger.metric_recorded({"accuracy": 0.91, "f1": 0.89}, split="test")
```

### 三类日志如何配合

三类日志通过 `task_id`、`run_id` 和 `llm_call_id` 关联：

```text
task.jsonl
  看到 run_0 的 data_agent 调用了一次 LLM：llm_call_id=llm_0001

llm_calls.jsonl
  用 llm_call_id=llm_0001 找到完整 prompt 和 response

run.jsonl
  用 run_id=run_0 查看该模型方案后续代码生成、预处理、训练、评估过程
```

推荐排查顺序：

1. 先看 `task.jsonl`，判断整个任务在哪一步失败。
2. 如果失败和某个 run 有关，再看对应 `runs/run_xxx/logs/run.jsonl`。
3. 如果失败和 LLM 输出有关，再用 `llm_call_id` 查 `llm_calls.jsonl`。
4. 如果失败和脚本运行有关，后续可再查看 `preprocess.stdout.log`、`train.stderr.log` 等脚本级日志。

### 当前已实现的日志相关工具

| 工具 | 文件 | 作用 |
| --- | --- | --- |
| `build_log_event()` | `src/utils/log_events.py` | 生成统一结构的日志事件。 |
| `build_error_event()` | `src/utils/log_events.py` | 根据异常生成统一结构的错误事件。 |
| `EventTimer` | `src/utils/log_events.py` | 记录 Agent、run 或脚本执行耗时。 |
| `append_jsonl()` | `src/utils/io.py` | 向 JSONL 文件追加一条 JSON 记录。 |
| `TaskLogger` | `src/utils/task_logger.py` | 写入 `task.jsonl` 和 `llm_calls.jsonl`。 |
| `RunLogger` | `src/utils/run_logger.py` | 写入某个 run 的 `run.jsonl`。 |
