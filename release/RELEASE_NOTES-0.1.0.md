# 英语打字练习 0.1.0 发布说明

## 版本信息

- 版本：0.1.0
- 形式：Windows x64 可移植版（one-folder）
- 程序：`EnglishTypingTrainer.exe`
- 数据库 schema：3

## 主要功能

包含文章导入与分段、普通练习、专项练习、可见错误输入与 Backspace、进度恢复、历史记录、学习统计、错误分析、生词本、间隔复习、简体中文界面和深浅主题。

## 使用方式

解压完整 ZIP 后运行 `EnglishTypingTrainer\EnglishTypingTrainer.exe`。请勿只复制 EXE，`_internal` 目录是程序运行所必需的。

用户数据保存在 `%LOCALAPPDATA%\EnglishTypingTrainer\`，不会写入程序安装目录。日志位于该数据目录的 `logs\EnglishTypingTrainer.log`。

## 发布前说明

本候选版本已通过自动化测试与隔离运行验收。真人手动输入和真正无 Python 的干净 Windows 环境仍需由发布负责人完成最终确认。