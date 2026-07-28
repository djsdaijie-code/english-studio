# 全球汽车品牌与车标英语：MVP 内容 QA

## 自动化结果

- Course / Level / Unit / Day / Item：1 / 1 / 2 / 14 / 40。
- Unit 1：7 Day、20 个新品牌；Unit 2：7 Day、20 个新品牌。
- 40 个 sentence ID、Item stable key、完整英文目标和素材路径均唯一；原有 40 个 stable key 全部保留。
- 40 个视觉引用均存在，均为 UTF-8 SVG，均通过大小、路径和可执行内容检查。
- catalog、Course、Unit、Lesson、Sentence 引用一致；课程规范 `1.0` 回归保持兼容。
- 素材 manifest 包含 40 条来源记录、上游版本和 SHA-256。
- Course、Unit、Lesson 与 Sentence 的内容版本同步为 `0.1.1`；40 条英文内容均为 8–12 词。

## 内容抽查

- 地区覆盖包含中国、日本、韩国、印度、欧洲和美国的常见品牌。
- 高频量产品牌与豪华、跑车、新兴电动车品牌分开递进。
- 每项使用“品牌名。简短介绍。”结构；介绍只采用产地、常见产品类别、所属关系或长期品牌特点，不采用广告口号、销量、价格和短期产品规则。
- 严格大小写覆盖 `BMW`、`BYD`、`SEAT`、`MINI`、`MG`、`XPENG`，复合名称覆盖 `Mercedes-Benz`、`Land Rover`、`Rolls-Royce`、`Aston Martin`。
- 每个品牌配置一个常见拼写、大小写、空格或连字符错误提示，并要求继续完整输入描述句。
- Day 5、6、7 只复用已学 stable key，没有为复习重复创建 Item。
- 中文采用中国大陆常见品牌译名和简洁事实翻译；课程不写短期销量、价格、具体车型或厂商临时规则。

## 内容事实来源抽查

- 产品范围参考品牌或公司官方页面，包括 [Honda 公司概况](https://global.honda/en/about/overview.html)、[Suzuki 公司概况](https://www.globalsuzuki.com/sustainability/data/company_profile.html)、[BYD 乘用车](https://www.bydglobal.com/en/car.html) 和 [Tata Motors 公司概况](https://www.tatamotors.com/organisation/about-us/)。
- 长期品牌特点参考 [Volvo 安全历史](https://www.volvocars.com/intl/safety/legacy/)、[Subaru 全轮驱动说明](https://www.subaru.com/vehicle-info/articles/what-is-all-wheel-drive.html)、[Jeep 越野车型说明](https://www.jeep.com/suv/offroad-suvs.html) 和 [Ferrari 公司介绍](https://www.ferrari.com/en-EN/corporate)。
- 品牌沿革与官方写法参考 [MINI 历史](https://www.mini.co.uk/en_GB/home/why-mini/history-of-mini.html)、[MG 品牌历史](https://www.mgmotor.eu/brand-history)、[SAIC 历史](https://www.saicmotor.com/english/history/r1.html) 和 [XPENG 官方新闻中心](https://www.xpeng.com/news/0189077394e388fa98d62c9e8d790065)。
- 自动化抽查不能代替逐品牌编辑签核；课程在完整事实复核和真人试学前继续保持 `draft`。

## 视觉与交互 QA

- 课程目标是学习品牌名及常用介绍表达，不是未教学先识图作答；40 个 Item 均使用 `illustrated_word`，且不隐藏完整目标。
- Qt 离屏实渲染确认：SVG 在白底卡片中保持比例、深浅主题可读，输入前车标、完整英文目标和右栏英文原文同时可见。
- 喇叭和完成后 Space 重听均提交完整“品牌名 + 介绍”，并使用 stable key 与 `content_version: 0.1.1` 形成课程 TTS 缓存身份。
- 正确完成后，同一页面显示完整中文翻译，进度写回原 Item stable key。
- Day 详情直接列出完整英文内容；Day 7 是综合复习，不设置识图测试或 80% 成绩门槛。
- 无核心词条的品牌项不显示“查看单词”，课程复习入口仍按配置显示。

## 素材与权利状态

- 34 个 SVG 来自 Simple Icons `16.21.0`；其项目采用 CC0，但上游免责声明明确指出单个品牌图标不必然属于 CC0。
- BYD、XPENG、Geely、Mercedes-Benz、Lexus、Land Rover 共 6 个 SVG 来自对应 Wikimedia Commons 文件页；页面按简单图形或文字标识说明其版权状态，同时明确提示商标限制。
- 所有品牌名和车标仍可能受商标、品牌指南及地区法规约束。当前用途为词汇教育练习，不表示品牌授权、赞助或背书。

## 已知风险与人工试学建议

- 品牌可能换标；`2026-07-24` 后发布前应重新核对来源页和品牌官网。
- Simple Icons 为单色简化图形，可能与车身实物徽标、彩色横版标志存在差异。
- BYD、XPENG 等文字型标志会直接提供部分拼写线索，难度低于纯图形车标。
- TTS 对 `Peugeot`、`Renault`、`Hyundai`、`Porsche` 等品牌的读音可能因 provider 和口音而不同；完整介绍也需要真人确认停顿是否自然，Day 6 目前保持可选。
- 严格输入对全大写、标点、空格与连字符较敏感；建议让 3–5 名目标用户完成两个 Unit，记录完整介绍的输入负担、品牌读音、延迟回忆效果和挫败点后再调整。
- 未完成商标/品牌指南审查和真人试学前，课程状态必须保持 `draft`。
