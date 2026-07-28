# AI 与大模型英语：课程总体规划

状态：Reviewed

课程 ID：`ai-large-models`

规划版本：1.0.0

## 课程定位与规模

课程面向英语基础较弱、希望在真实 AI 工作中使用英语的用户。约 50% 内容来自普通用户操作 AI 的高频场景，约 50% 来自 AI 技术、API、Agent 和自动化场景。它不是人工智能理论课、考试英语课或厂商产品手册。

第一版候选课程已完成 5 个 Level、8 个 Unit、56 个学习日和 176 个核心句子。每个 Unit 为 7 天、22 个新句子：Day 1–4 每天 5–6 句，Day 5 综合场景，Day 6 重点句打字巩固，Day 7 复习与测评。AI 朗读作为练习页辅助能力，不单独设置课程日。参数写入课程或 Unit 数据，不写死在程序与 Schema 中。

课程版本与内容版本均为 `1.0.0`，状态为 `reviewed`。Unit 1 的原 12 条结构样例已逐句审核并保留原 stable key，随后扩展为完整 7 Day、22 句；其余 Unit 使用连续的新 sentence ID 和 stable key。

## 难度递进

1. Level 1 以 4–9 词的直接命令和简单界面陈述为主。
2. Level 2 引入任务动词、比较、格式和输出限制，范围为 4–8 词，过半句子不少于 6 词。
3. Level 3 引入文件上下文、失败原因、条件和修正步骤，范围为 5–10 词，过半句子不少于 8 词。
4. Level 4 使用 API、认证、参数和限制等技术概念，使用 10–13 词的完整说明句。
5. Level 5 使用 10–13 词的条件句和说明句描述权限、确认、重试、监控与多步骤工作流。

技术难度与语言难度分别审核。短句包含新技术概念时仍可属于较高 Level；高频术语会在场景中计划复现，但不通过机械替换名词凑数。

## Level 1：基础使用

目标：看懂 AI 软件的基本界面动作，完成对话、文件和模型的基础设置；建立“动词 + 宾语”的操作英语框架。

### Unit 1：AI 基础界面与操作

- 目标：新建对话、发送消息、停止生成、重新尝试、复制和保存回答、上传文件、下载结果。
- 实际：7 天，22 个核心句子。
- 核心词汇：`chat`、`message`、`send`、`stop`、`generate`、`response`、`copy`、`save`、`upload`、`download`、`file`、`result`。
- 核心句型：`Verb + noun.`、`Verb + noun + here.`、`Verb + noun + when ready.`、`Verb + noun + before + verb-ing.`
- 场景比例：普通 AI 使用为主；只解释完成操作所需的技术词。

### Unit 2：模型选择与基础设置

- 目标：选择适合任务的模型，理解速度、质量、推理模式、上下文、token 和输出长度。
- 实际：7 天，22 个核心句子。
- 核心词汇：`model`、`fast`、`accurate`、`reasoning`、`context`、`token`、`limit`、`output`、`length`、`task`。
- 核心句型：`Choose ... for ...`、`This model is better for ...`、`Set the output length to ...`、`Does this model support ...?`
- 边界：不比较厂商短期排行榜，不承诺固定速度、价格或上下文窗口。

## Level 2：向 AI 下达指令

目标：使用明确任务动词、对象、格式和限制向 AI 提出请求，并能迭代修改输出。

### Unit 3：提问与基础指令

- 目标：熟练使用 `explain`、`summarize`、`translate`、`rewrite`、`compare`、`list`、`check`、`show` 和 `generate`。
- 实际：7 天，22 个核心句子。
- 核心词汇：上述九个任务动词，以及 `example`、`difference`、`mistake`、`step`、`idea`。
- 核心句型：`Explain ... in simple English.`、`Summarize ... in three points.`、`Compare A with B.`、`Show me how to ...`
- 场景比例：普通 AI 使用为主，用技术场景巩固同一指令框架。

### Unit 4：提示词与输出控制

- 目标：要求更短、更详细、更自然或更专业的输出；改变格式、删除重复、保留重点并要求分步骤输出。
- 实际：7 天，22 个核心句子。
- 核心词汇：`shorter`、`detailed`、`natural`、`professional`、`format`、`remove`、`repeat`、`keep`、`table`、`step`。
- 核心句型：`Make it + adjective.`、`Use ... instead of ...`、`Keep ... but remove ...`、`Put the result in a table.`
- 边界：不教授“万能提示词”，不声称某种提示格式始终更优。

## Level 3：内容处理与错误

目标：围绕给定内容工作，识别失败或不完整输出，并用英语描述问题和下一步动作。

### Unit 5：文件、图片和长文本

- 目标：上传文件、阅读文档、分析截图、提取内容、比较文件、基于文档回答并导出结果。
- 实际：7 天，22 个核心句子。
- 核心词汇：`document`、`image`、`screenshot`、`extract`、`compare`、`based on`、`source`、`page`、`section`、`export`。
- 核心句型：`Answer based on this file.`、`Extract ... from ...`、`Compare these two documents.`、`Which page mentions ...?`
- 边界：强调核对来源，不暗示 AI 一定能读取所有文件格式或图片细节。

### Unit 6：错误、失败和修正

- 目标：描述请求失败、回答错误、文件不可读、内容不完整、格式不支持、超时、重试、日志检查和修复。
- 实际：7 天，22 个核心句子。
- 核心词汇：`failed`、`incorrect`、`unreadable`、`incomplete`、`unsupported`、`timeout`、`retry`、`log`、`fix`、`issue`。
- 核心句型：`The request failed because ...`、`The response is missing ...`、`Try again after ...`、`Check the log for ...`
- 边界：错误信息必须技术上合理；不虚构具体产品错误码。

## Level 4：AI 技术使用

目标：阅读和表达 API 与模型调用中的基础概念，不要求编写完整程序。

### Unit 7：API 与模型基础

- 目标：理解 API key、request、response、input、output、parameter、endpoint、authentication、token usage、rate limit、JSON 和 system message。
- 实际：7 天，22 个核心句子。
- 核心词汇：`API key`、`request`、`response`、`input`、`output`、`parameter`、`endpoint`、`authentication`、`token usage`、`rate limit`、`JSON`、`system message`。
- 核心句型：`Send ... in the request.`、`The response contains ...`、`Set the ... parameter.`、`The request requires authentication.`、`We reached the rate limit.`
- 边界：不讲模型训练算法、数学公式或厂商 SDK 的短期版本细节；密钥示例不得包含真实凭据。

## Level 5：Agent 与自动化

目标：理解 Agent 如何接收任务、调用工具和按条件执行工作流，并能讨论权限、确认、重试和监控。

### Unit 8：AI Agent、工具和工作流

- 目标：描述 agent、tool、task、workflow、trigger、condition、action、schedule、permission、confirmation、retry、monitor 和 save result。
- 实际：7 天，22 个核心句子。
- 核心词汇：上述工作流术语，以及 `run`、`allow`、`deny`、`complete`、`failed`。
- 核心句型：`The agent uses ... to ...`、`Run this action when ...`、`Ask for confirmation before ...`、`Retry the task if ...`、`Save the result after ...`
- 边界：不把 Agent 描述成有自主意识；涉及写入、发送、删除和付费动作时必须强调权限与确认。

## 全课程不应包含的内容

- 纯日常口语、考试技巧或论文阅读训练。
- 数学公式、模型训练算法、参数推导和系统性人工智能理论。
- 厂商价格、模型榜单、短期按钮位置或容易过期的版本说明。
- 暗示 AI 输出必然正确、安全或无须人工检查的表达。
- 真实 API key、个人数据、版权不明的长文本或未经授权的产品文案。
- 只替换名词、场景价值不变的批量句子。

## 后续扩展方向

- 在八个核心 Unit 内容稳定后，增加行业专题包，例如办公写作、数据分析、编程协作和客户支持。
- 为阅读型 Unit 增加短文 Learning Item，同时保持 Day 和稳定键规则不变。
- 为课程包导入增加清单、签名、兼容范围和内容迁移映射。
- 在不改变静态内容权威源的前提下，增加用户复制课程和自定义课程。
- 更后期可设计在线课程目录；当前规划不包含服务端、在线下载或自动更新。
