# 全球汽车品牌与车标英语：MVP 课程计划

## 定位

- 课程 ID：`global-car-logos`
- 版本：`0.1.1`
- 规范版本：`1.1`
- 状态：`draft`
- 规模：1 个 Level、2 个 Unit、14 个 Day、40 个品牌
- 核心任务：先读英文品牌名，再跟打一条简短事实介绍；车标作为辅助记忆线索

本版本是最小可交付课程，不宣称穷举全世界所有汽车品牌，也不讲具体车型、详细公司史、销量、价格或短期产品信息。介绍句只保留产地、常见产品类别、所属关系或长期品牌特点等稳定信息。

## 教学结构

| Unit | 主题 | 品牌数 | 教学目标 |
|---|---|---:|---|
| 1 | 高频汽车品牌与介绍 | 20 | 学习高频英文品牌名，并跟打一句简短介绍 |
| 2 | 地区与进阶品牌介绍 | 20 | 扩展地区、豪华和新兴电动车品牌及常用描述 |

每个 Unit 使用相同的 7 Day 节奏：

1. Day 1–4：每天学习 5 个“品牌名 + 简短介绍”；车标、完整英文目标同时显示，严格跟打为必做。
2. Day 5：复习 10 个易混或高频品牌及介绍，巩固大小写、标点和高频句型。
3. Day 6：通过重复打字巩固 10 条品牌介绍；AI 朗读仅作为练习页辅助能力。
4. Day 7：完整复习 20 条品牌介绍，不设置识图或成绩门槛；FSRS 为可选。

## 品牌范围

Unit 1：Toyota、Volkswagen、Ford、Honda、BMW、Mercedes-Benz、Audi、Tesla、Nissan、Hyundai、Kia、Chevrolet、BYD、Porsche、Ferrari、Lamborghini、Volvo、Mazda、Subaru、Jeep。

Unit 2：Renault、Peugeot、Fiat、SEAT、MINI、Cadillac、Mitsubishi、Suzuki、Tata、Lexus、Land Rover、Infiniti、Bentley、Maserati、McLaren、Rolls-Royce、MG、Aston Martin、XPENG、Geely。

## 技术映射

- 每个品牌仍是不可变 `CourseSentence`；`english` 采用“品牌名。简短介绍。”，从练习开始就是可见的完整输入目标。
- `visual_prompt.asset_path` 指向课程内 SVG；课程使用 `prompt_type: illustrated_word` 和 `hide_answer: false`，将车标作为单词记忆线索。
- Item stable key 使用 `global-car-logos-brand-<slug>`，不依赖 Day、数组顺序、图片文件哈希或品牌文本。
- 课程内容版本为 `0.1.1`，原 40 个 Item stable key 全部保留；内容版本变化会为 TTS 生成新的缓存身份。
- 打字完成、可选能力和 FSRS 继续写 schema 13 的课程状态表；图片、品牌名和介绍句不写文章表。
- 素材来源、上游版本和 SHA-256 见 `ASSET_SOURCES.json`。

## 发布门禁

课程保持 `draft`，直至完成：

- 40 个视觉素材的当前官方形态复核；
- 商标与品牌指南的目标市场审查；
- 中文品牌名、英文大小写和读音人工签核；
- 40 条简短介绍的事实与中文翻译人工签核；
- 桌面端与正式 PyInstaller 包真人试学；
- 易混车标和 Day 5–7 难度调整。
