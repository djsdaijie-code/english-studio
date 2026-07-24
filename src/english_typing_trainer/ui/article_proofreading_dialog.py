from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.services.article_proofreading import ArticleProofreadingResult


class ArticleProofreadingDialog(QDialog):
    def __init__(
        self,
        article_title: str,
        original_text: str,
        result: ArticleProofreadingResult,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("DeepSeek 文章检测")
        self.setMinimumSize(920, 640)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        summary = f"发现 {len(result.issues)} 处可能问题" if result.issues else "检测到建议修改"
        title = QLabel(f"《{article_title}》{summary}")
        title.setProperty("role", "page-title")
        subtitle = QLabel("请核对 AI 建议。应用后会重新分段并重置本文进度，历史练习记录仍会保留。")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        issue_text = "\n".join(
            f"{index}. [{self._type_name(item.issue_type)}] {item.original or '（格式）'} → {item.suggestion or '（删除）'}\n   {item.reason}"
            for index, item in enumerate(result.issues, start=1)
        ) or "DeepSeek 建议调整文章格式，但未返回逐项说明。"
        issues = QTextEdit()
        issues.setObjectName("ProofreadingIssues")
        issues.setReadOnly(True)
        issues.setPlainText(issue_text)
        issues.setMaximumHeight(180)
        layout.addWidget(issues)

        comparison = QSplitter(Qt.Orientation.Horizontal)
        comparison.addWidget(self._text_panel("当前原文", original_text))
        comparison.addWidget(self._text_panel("建议版本", result.corrected_text))
        comparison.setSizes([450, 450])
        layout.addWidget(comparison, stretch=1)

        actions = QHBoxLayout()
        keep_button = QPushButton("保留原文")
        keep_button.clicked.connect(self.reject)
        apply_button = QPushButton("应用建议")
        apply_button.setProperty("variant", "primary")
        apply_button.clicked.connect(self.accept)
        actions.addStretch(1)
        actions.addWidget(keep_button)
        actions.addWidget(apply_button)
        layout.addLayout(actions)

    @staticmethod
    def _text_panel(title: str, text: str) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setProperty("role", "section-title")
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        layout.addWidget(label)
        layout.addWidget(editor)
        return panel

    @staticmethod
    def _type_name(issue_type: str) -> str:
        return {
            "spelling": "拼写",
            "word": "单词",
            "punctuation": "标点",
            "formatting": "格式",
        }.get(issue_type, "建议")
