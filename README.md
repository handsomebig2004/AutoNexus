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

## 项目目录结构

```text
.
├── config/                 # YAML 等配置文件
├── src/                    # 项目核心代码
│   ├── agents/             # 各类 Agent 的源代码
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
| `src/prompts/` | 各类模型的固定提示词。后续可以考虑加入 `manager` 或 `memory`，在提示词进入 Agent 前做统一处理。 |
| `src/models/` | 经过总结的模型信息，可输入给 LLM Agent，辅助它按指定模型写代码。 |
| `src/skills/` | 输入给 LLM Agent 的技能文档，例如如何找论文、如何使用 `models/` 中的模型信息。 |
| `src/schemas/` | Agent 输出的标准格式定义。 |
| `src/tools/` | 与外部连接、代码执行、数据处理相关的工具函数或类，后续可加入安全检查。 |
| `src/utils/` | Agent 和 tools 之间复用的小函数。后续如果做 Agent 记忆，也可以在这里扩展 `memory/` 等目录。 |

## 工具规划

只考虑了 `data_agent`，其他的后面再说

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
| JSON/YAML IO | `src/utils/io.py` | 统一读写 `json`、`yaml`、`txt`、`md`，避免各处重复实现。 |
| 日志工具 | `src/utils/logging.py` | 统一记录 Agent 调用日志和脚本执行日志。 |
| 文本格式工具 | `src/utils/text.py` | 清理 LLM 输出，例如从回复中提取 Python 代码块或 JSON。 |
| 哈希/版本工具 | `src/utils/hash.py` | 记录原始数据 hash 和脚本 hash，方便复现。 |
| ~~错误类型定义~~ | `src/utils/errors.py` | 定义 `DataValidationError`、`GeneratedCodeError` 等异常类型。 |
| 时间/命名工具 | `src/utils/naming.py` | 管理时间戳、运行名、文件名等命名逻辑。 |

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
