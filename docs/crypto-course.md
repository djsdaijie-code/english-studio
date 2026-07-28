# 币圈与区块链英语 MVP

## 可交付范围

`crypto-blockchain-english` 是一门纯文本课程：1 个 Level、2 个 Unit、14 个 Day、40 条中级短句。Unit 1 覆盖钱包、转账、订单和安全；Unit 2 覆盖 DeFi、TVL、市场指标、跨链和风险。

课程目标是帮助用户看懂常见英文界面、文档与风险提示，不提供投资建议，不包含实时价格、收益率、币种推荐或交易信号。

## 学习流程

```text
CourseRepository
→ CourseLearningSession
→ 现有逐句打字组件
→ stable-key 课程进度
→ 可选 FSRS 复习
```

每条内容都包含英文、自然中文翻译、核心词、句型和一个常见误解。Day 1–4 学新句，Day 5 组合场景，Day 6 术语辨析，Day 7 全单元复习。

## 无音频能力

本课程按当前产品能力设计：

- 不配置朗读或听写入口；
- 不配置 `speaking`、`listening` 或 `dictation` 活动；
- 所有 `audio_hint` 为 `null`；
- 只使用必做 `typing` 和可选 `fsrs`；
- 中文翻译和词汇能力不依赖音频服务。

因此，课程不会调用 TTS、麦克风、录音或语音 Provider，也不会出现已下线能力的占位按钮。

## TVL 口径

课程使用：

```text
TVL stands for Total Value Locked in DeFi.
TVL 指 DeFi 中的总锁定价值（Total Value Locked）。
```

下一条进一步说明 TVL 衡量存入协议智能合约的资产价值，并明确它不等同于代币市值。

## 数据边界

课程内容保持只读，通过稳定 ID 和 stable key 查询。SQLite 只保存 enrollment、Item 进度和可选 FSRS 状态，不创建文章或文章句子记录。本功能不修改 schema 13。

## 验证

```powershell
.\.venv\Scripts\python.exe scripts\validate_courses.py
.\.venv\Scripts\python.exe -m pytest -q tests\test_crypto_course.py
```

专项测试应覆盖课程规模、TVL 定义、唯一 stable key、无音频配置、Day 会话构建、课程页面能力按钮和文章表零写入。
