# English Studio 1.0.0

English Studio 是一个本地优先的英语阅读、打字、听写与复习工具。

## 包含内容

- 文章导入、连续练习与逐句学习
- 本地历史、学习统计、错误分析与专项练习
- 单词本、FSRS 智能复习、单词和句子听写
- 可选 DeepSeek 翻译、MiniMax 语音和 Azure 跟读评分 Beta
- 深浅主题、中文界面和本地 SQLite 数据管理

## 安装与隐私

- `EnglishStudio-1.0.0-Setup.exe` 默认安装到当前用户目录，不需要 Python 或管理员权限。
- 也可以解压 `EnglishStudio-1.0.0-win-x64-portable.zip` 后直接运行 `EnglishStudio.exe`。
- 用户数据保存在 `%LOCALAPPDATA%\EnglishStudio`，卸载默认保留。仅在运行卸载程序时明确传入 `/PURGEDATA=1` 才删除该目录。
- DeepSeek、MiniMax 与 Azure Key 仅保存在 Windows Credential Manager，不进入数据库、日志或发布包。

## 已知限制

- 本版本未进行代码签名，Windows SmartScreen 可能显示提示。请验证 `SHA256SUMS.txt`。
- Azure Speech 跟读评分为 Beta；未配置 Azure 时可以录音和回放，但不会显示模拟评分。
- 当前构建环境的 Inno Setup 不带简体中文向导资源，安装向导暂为英文；应用界面和中文路径仍正常。
