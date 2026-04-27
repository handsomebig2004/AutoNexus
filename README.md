# Agents

requirement_agent理解人需求的agent，把问题转化为一个可以建模的问题，给出来这个问题需要的输入和输出

research_agent负责找寻数据和相关文献并生成模型方案的agent，筛选出一些可用的数据和可用的方法

data_agent根据数据和方法的特征清洗/预处理/做特征的agent

train_agent写模型并训练的agent

evaluation_agent评估实验结果的agent

现在先不迭代模型，就是让大模型生成几个模型都跑一遍比较结果，迭代模型/agent后面再说

* ./tasks:

每运行一个task会有好几个方法，每个方法一个run，找数据的找到数据存到tasks/task_xxx/data/raw里面，然后dataagent处理完之后存到data/processed/run_xxx里面(xxx是编号)

tasks/task_xxx/doc里面是存research找到的文献，然后其他的agent如果需要的话可以打开看

tasks/task_xxx/src/run_xxx是大模型写的代码，dataagent放在src/preprocess里面，trainagent放到src/train里面

tasks/task_xxx/outputs/run_xxx是存运行完model的输出

比如说日志啊、审查纪录啊在其他task不复用的都放在这里，可以建新的文件夹

* ./config:

就是各种yaml配置文件，后面配置多了可以分层

* ./src：

src/prompts是各种模型的固定提示词，当然后面可以考虑加一个manager每次把提示词输入agent里面之前先在manager过一下（或者只用memory就够了？）

src/agents里面存着各种agent的源代码，注意每个agent的输出都是固定的，都能通过utils里面的对应的一个固定方法（比如说一个固定的bat文件或者一个固定的py函数）运行这个agent输出的代码，然后agent还会输出这个的一个简短解释，给其他的agent输入

src/models存经过总结的模型信息，可以输入llm agent里面让他用这个模型来写代码

src/skills是输入到llm agent里面的skill文档，比如说怎么找论文、怎么用models文件夹里的模型之类的

src/schemas里面写着agent输出的标准格式

src/tools是一些需要和外部连接/执行代码的函数/类之类的，后面可以做一些安全检查

src/utils是一些在agent或tools之间复用的小函数

后面迭代agent的记忆之类的可以在这里建一个memory文件夹之类的

Data Agent 需要的 Tools

Tool	文件	作用
数据读取工具	src/tools/data_loader.py	统一读取 csv/xlsx/json/parquet，返回 DataFrame 和基础信息
数据概览工具	src/tools/data_profiler.py	统计行列数、字段类型、缺失率、唯一值、样例值、标签分布 这个是researchagent 调用的，总结一下数据集的大概
Schema 推断工具	src/tools/schema_infer.py	推断字段类型：数值、类别、文本、时间、ID、标签列候选（感觉这个应该不用）
数据质量检查工具	src/tools/data_quality.py	检查重复行、常量列、高缺失列、异常值、类别过多、数据泄漏风险
预处理代码生成辅助	src/tools/code_writer.py	把 LLM 输出的 preprocess.py 安全写入 run 目录
预处理代码校验工具	src/tools/code_validator.py	检查生成脚本是否有规定入口函数、危险导入、危险系统调用 校验可以晚一点再写
预处理代码运行工具	src/tools/code_runner.py	在指定 run 目录运行 preprocess.py，捕获 stdout/stderr/退出码
产物管理工具	src/tools/artifact_manager.py	管理 processed data、feature report、preprocessor、日志路径
数据切分工具	src/tools/splitter.py	提供标准 train/val/test split，支持分类 stratify
特征报告工具	src/tools/feature_report.py	生成 feature_report.json，给 train_agent 使用
Data Agent 需要的 Utils

Util	文件	作用
路径工具	src/utils/numbered_paths.py 创建path/prefix_xxx文件夹，扫描输入路径下已有的 prefix_xxx 文件夹，找最大编号，创建下一个编号目录，用 filelock 防止并发重复，返回已经创建好的 Path
配置读取	src/utils/config.py	读取 settings.yaml、agent 配置、默认参数
JSON/YAML IO	src/utils/io.py	读写 json/yaml/txt/md，避免各处重复
日志工具	src/utils/logging.py	统一记录 agent 调用、脚本执行日志
文本格式工具	src/utils/text.py	清理 LLM 输出，比如提取 ```python 代码块、提取 JSON
哈希/版本工具	src/utils/hash.py	记录原始数据 hash、脚本 hash，方便复现
错误类型	src/utils/errors.py	定义 DataValidationError、GeneratedCodeError 等
时间/命名工具	src/utils/naming.py

errors.py
  只定义错误类型

llm_client.py
  捕获 API 错误，转成 LLMError

schema_parser.py / agent.py
  捕获解析失败，转成 LLMOutputParseError

code_validator.py
  检查生成代码，失败时抛 GeneratedCodeValidationError

code_runner.py
  脚本运行失败，抛 GeneratedCodeExecutionError

pipeline/runner.py
  根据错误类型决定怎么处理
