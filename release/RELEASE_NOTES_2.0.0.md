# English Studio 2.0.0

English Studio 2.0.0 是面向 Windows 10/11 x64 的正式版，重点增加内置课程，并优化文章、逐句、单词和每日学习体验。

## 主要更新

- 新增内置课程浏览、Level / Unit / Day 层级、推荐继续和独立进度。
- 课程复用逐句打字、中文译文、AI 朗读、单词收藏和 FSRS 复习能力。
- 首页集中展示今日有效学习时间、打卡、等级、本周轨迹和快捷入口。
- 单词本支持用户主动选词、可拖动快捷入口、复选/全选和紧凑的单词学习工作区。
- 文章导入支持可选 DeepSeek 格式与拼写检查，改为全文单段保存，不再自动将全文单词加入单词本。
- 移除听写、用户录音和 Azure 跟读评分入口；旧数据表只作升级兼容保留。

## 安装与数据

- `EnglishStudio-2.0.0-Setup.exe`：当前用户安装，不需要 Python 或管理员权限。
- `EnglishStudio-2.0.0-win-x64-portable.zip`：解压后运行 `EnglishStudio.exe`。
- 用户数据保存在 `%LOCALAPPDATA%\EnglishStudio\`，覆盖安装和默认卸载不删除学习数据。
- DeepSeek 和 MiniMax Key 仅从 Windows Credential Manager 读取，不包含在安装包、便携包、数据库或日志中。

## 已知限制

- 安装向导目前为英文，应用本体为简体中文。
- 本版未进行代码签名，Windows SmartScreen 可能显示提示；请使用 `SHA256SUMS.txt` 验证下载完整性。
- 在线翻译、文章校对和 MiniMax 音频需要用户自行配置对应 Key；未配置时本地学习功能仍可使用。
