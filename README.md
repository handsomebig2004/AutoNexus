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