from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class ChineseArticleDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("粘贴中文文章")
        self.setMinimumSize(620, 500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("导入中文五笔练习")
        title.setProperty("role", "page-title")
        description = QLabel("填写标题并粘贴整篇中文正文。文章会作为一个完整练习保存，不会自动分段。")
        description.setProperty("role", "subtitle")
        description.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(description)

        layout.addWidget(QLabel("标题"))
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("例如：五笔练习文章")
        layout.addWidget(self.title_input)

        layout.addWidget(QLabel("正文"))
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("在这里粘贴中文正文……")
        self.text_input.setAcceptRichText(False)
        layout.addWidget(self.text_input, stretch=1)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("导入")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self._validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def article_title(self) -> str:
        return self.title_input.text().strip()

    def article_text(self) -> str:
        return self.text_input.toPlainText()

    def _validate_and_accept(self) -> None:
        if not self.article_title():
            QMessageBox.information(self, "缺少标题", "请填写文章标题。")
            self.title_input.setFocus()
            return
        if not self.article_text().strip():
            QMessageBox.information(self, "缺少正文", "请粘贴中文正文。")
            self.text_input.setFocus()
            return
        self.accept()
