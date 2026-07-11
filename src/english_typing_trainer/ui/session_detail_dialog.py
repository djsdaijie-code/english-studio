from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView

from english_typing_trainer.services.statistics_service import ERROR_TYPE_LABELS
from english_typing_trainer.typing_engine.text_analysis import humanize_character


def _local_text(value: str | None) -> str:
    if not value:
        return "暂无"
    try:
        return datetime.fromisoformat(value).strftime("%Y年%m月%d日 %H:%M:%S")
    except ValueError:
        return value


class SessionDetailDialog(QDialog):
    def __init__(self, session_row, error_rows, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("练习详情")
        self.resize(900, 640)

        layout = QVBoxLayout(self)
        lines = [
            f"练习类型：{session_row['practice_type']}",
            f"练习集：{session_row['practice_set_title'] or '暂无'}",
            f"文章：{session_row['article_title'] or '已删除内容'}",
            f"段落：{(session_row['section_index'] or 0) + 1 if session_row['section_index'] is not None else '-'}",
            f"开始时间：{_local_text(session_row['started_at'])}",
            f"结束时间：{_local_text(session_row['finished_at'])}",
            f"有效时长：{session_row['active_seconds']:.1f} 秒",
            f"暂停时长：{session_row['paused_seconds']:.1f} 秒",
            f"完成状态：{'已完成' if session_row['completed'] else '未完成'}",
            f"完成度：{session_row['completion_rate'] * 100:.1f}%",
            f"正确字符：{session_row['correct_characters']}",
            f"总按键：{session_row['total_keystrokes']}",
            f"正确按键：{session_row['correct_keystrokes']}",
            f"错误按键：{session_row['error_keystrokes']}",
            f"WPM：{session_row['wpm']:.1f}" if session_row["is_effective_result"] else "WPM：数据不足",
            f"CPM：{session_row['cpm']:.1f}" if session_row["is_effective_result"] else "CPM：数据不足",
            f"正确率：{session_row['accuracy']:.1f}%" if session_row["is_effective_result"] else "正确率：数据不足",
            f"最长连续正确：{session_row['longest_correct_streak']}",
        ]
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)

        table = QTableWidget(len(error_rows), 5)
        table.setHorizontalHeaderLabels(["位置", "期望字符", "实际输入", "目标单词", "错误类型"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row_index, error in enumerate(error_rows):
            table.setItem(row_index, 0, QTableWidgetItem(str(error["character_index"])))
            table.setItem(row_index, 1, QTableWidgetItem(humanize_character(error["expected_character"])))
            table.setItem(row_index, 2, QTableWidgetItem(humanize_character(error["actual_character"])))
            table.setItem(row_index, 3, QTableWidgetItem(error["target_word"]))
            table.setItem(
                row_index,
                4,
                QTableWidgetItem(ERROR_TYPE_LABELS.get(error["error_type"], error["error_type"])),
            )
        layout.addWidget(table)
