from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout

from english_typing_trainer.services.reading_service import clean_reading_text


class ReadingImportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("粘贴英文文章")
        self.resize(760, 620)
        self.setMinimumSize(620, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("英文精读")
        title.setProperty("role", "page-title")
        self.description = QLabel("粘贴网页文章或帖子，整理后确认正文，再开始逐句理解。")
        self.description.setWordWrap(True)
        self.description.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(self.description)
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("文章标题")
        self.source_input = QLineEdit()
        self.source_input.setPlaceholderText("来源网址（可选，仅作来源记录）")
        self.text_input = QTextEdit()
        self.text_input.setAcceptRichText(False)
        self.text_input.setPlaceholderText("在这里粘贴英文正文……")
        layout.addWidget(self.title_input)
        layout.addWidget(self.source_input)
        layout.addWidget(self.text_input, stretch=1)
        row = QHBoxLayout()
        self.back_button = QPushButton("返回编辑")
        self.back_button.hide()
        self.back_button.clicked.connect(self._edit)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        self.next_button = QPushButton("整理并预览")
        self.next_button.setProperty("variant", "primary")
        self.next_button.clicked.connect(self._advance)
        row.addWidget(self.back_button)
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.next_button)
        layout.addLayout(row)
        self._previewing = False

    def _edit(self) -> None:
        self._previewing = False
        self.back_button.hide()
        self.next_button.setText("整理并预览")

    def _advance(self) -> None:
        if not self.title_input.text().strip() or not self.text_input.toPlainText().strip():
            QMessageBox.information(self, "内容不完整", "请填写标题并粘贴英文正文。")
            return
        if not self._previewing:
            self.text_input.setPlainText(clean_reading_text(self.text_input.toPlainText()))
            self.description.setText("已整理多余空格和网页折行，保留自然段。请检查或修改正文，然后开始精读。")
            self.back_button.show()
            self.next_button.setText("开始精读")
            self._previewing = True
        else:
            self.accept()
