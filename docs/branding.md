# 拾句品牌资源

软件名称：拾句。品牌文案：拾句习语，读懂英文。

## 应用图标

图标以展开书页和金色引号表达“阅读、理解、积累句子”。深蓝底色延续界面色系，浅色书页与金色引号提供对比；图形不使用文字，方便在任务栏小尺寸中识别。

- SVG 源文件：resources/icons/shiju.svg，可直接修改矢量路径与颜色。
- 高清 PNG：resources/icons/shiju.png，1024×1024，圆角外透明。
- Windows：resources/icons/shiju.ico，包含 16、24、32、48、64、128、256px 七档尺寸。
- macOS：resources/icons/shiju.icns，包含 16～1024px 图像；作为后续 Mac 构建资源预备，尚未在真实 macOS Dock 中验收。

运行窗口与侧栏使用 SVG，PyInstaller EXE 和 Inno Setup 使用 ICO。旧 english-studio.svg 留作历史资源，当前程序不再引用。

## 导出

只依赖项目现有 PySide6，使用 Qt SVG 渲染器逐尺寸导出，不引入新的依赖：

```powershell
.\.venv\Scripts\python.exe scripts\export_brand_icons.py
```

脚本会验证 PNG、ICO 与 ICNS 可由 Qt 解码，并确认 ICO 包含全部七档尺寸。本轮只准备资源和构建引用，未重新打包、签名或发布。
