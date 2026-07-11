from __future__ import annotations

from PySide6.QtCharts import QChart, QChartView, QBarCategoryAxis, QLineSeries, QValueAxis
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)


class StatisticsPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        title = QLabel("学习统计")
        title.setProperty("role", "page-title")
        subtitle = QLabel("把最近练习时长、速度和错误趋势放在一起查看。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.metrics_layout = QGridLayout()
        self.metrics_layout.setHorizontalSpacing(16)
        self.metrics_layout.setVerticalSpacing(16)
        self.metric_labels: dict[str, QLabel] = {}
        metric_specs = [
            ("today_practice_sessions", "今日练习"),
            ("total_practice_seconds", "累计时长"),
            ("average_wpm", "平均 WPM"),
            ("average_accuracy", "平均正确率"),
            ("current_streak_days", "当前连续天数"),
            ("completed_sessions", "累计完成"),
            ("highest_effective_wpm", "最高有效 WPM"),
            ("due_vocabulary_words", "今日待复习"),
        ]
        for index, (key, title_text) in enumerate(metric_specs):
            card = QFrame()
            card.setObjectName("MetricCard")
            card.setMinimumHeight(96)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 16, 18, 16)
            card_layout.setSpacing(8)
            title_label = QLabel(title_text)
            title_label.setProperty("role", "metric-title")
            value_label = QLabel("-")
            value_label.setProperty("role", "metric-value")
            value_label.setMinimumHeight(38)
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            self.metric_labels[key] = value_label
            self.metrics_layout.addWidget(card, index // 5, index % 5)
        layout.addLayout(self.metrics_layout)

        range_card = QFrame()
        range_card.setObjectName("Card")
        range_row = QHBoxLayout(range_card)
        range_row.setContentsMargins(16, 12, 16, 12)
        self.trend_range = QComboBox()
        self.trend_range.addItem("最近 7 天", "7d")
        self.trend_range.addItem("最近 30 天", "30d")
        self.trend_range.addItem("最近 90 天", "90d")
        self.trend_range.addItem("全部", "all")
        self.error_range = QComboBox()
        self.error_range.addItem("最近 7 天", "7d")
        self.error_range.addItem("最近 30 天", "30d")
        self.error_range.addItem("全部", "all")
        range_row.addWidget(QLabel("趋势范围"))
        range_row.addWidget(self.trend_range)
        range_row.addSpacing(16)
        range_row.addWidget(QLabel("错误范围"))
        range_row.addWidget(self.error_range)
        range_row.addStretch(1)
        layout.addWidget(range_card)

        self.wpm_chart = self._build_chart("每日平均 WPM", "WPM")
        self.accuracy_chart = self._build_chart("每日平均正确率", "%")
        self.minutes_chart = self._build_chart("每日练习时长", "分钟")
        layout.addWidget(self.wpm_chart["view"])
        layout.addWidget(self.accuracy_chart["view"])
        layout.addWidget(self.minutes_chart["view"])

        analysis_row = QHBoxLayout()
        self.character_list = QListWidget()
        self.combination_list = QListWidget()
        self.word_list = QListWidget()
        self.type_list = QListWidget()
        for title_text, widget in (
            ("最高频错误字符", self.character_list),
            ("常见字符混淆", self.combination_list),
            ("高频错误单词", self.word_list),
            ("错误类型分布", self.type_list),
        ):
            card = QFrame()
            card.setObjectName("Card")
            box = QVBoxLayout(card)
            box.setContentsMargins(16, 16, 16, 16)
            label = QLabel(title_text)
            label.setProperty("role", "page-title")
            label.setStyleSheet("font-size: 16px;")
            box.addWidget(label)
            box.addWidget(widget)
            analysis_row.addWidget(card, stretch=1)
        layout.addLayout(analysis_row, stretch=1)

    def populate_overview(self, overview: dict[str, object]) -> None:
        self._set_metric("today_practice_sessions", f"{overview['today_practice_sessions']} 次")
        self._set_metric("total_practice_seconds", f"{overview['total_practice_seconds'] / 3600:.1f} 小时")
        self._set_metric("average_wpm", "-" if overview["average_wpm"] is None else f"{overview['average_wpm']:.1f}")
        self._set_metric(
            "average_accuracy",
            "-" if overview["average_accuracy"] is None else f"{overview['average_accuracy']:.1f}%",
        )
        self._set_metric("current_streak_days", f"{overview['current_streak_days']} 天")
        self._set_metric("completed_sessions", str(overview["completed_sessions"]))
        self._set_metric(
            "highest_effective_wpm",
            "-" if overview["highest_effective_wpm"] is None else f"{overview['highest_effective_wpm']:.1f}",
        )
        self._set_metric("due_vocabulary_words", str(overview["due_vocabulary_words"]))

    def populate_trends(self, trend_rows: list[dict[str, object]]) -> None:
        self._update_chart(self.wpm_chart, trend_rows, "average_wpm", decimals=1)
        self._update_chart(self.accuracy_chart, trend_rows, "average_accuracy", decimals=1)
        self._update_chart(self.minutes_chart, trend_rows, "active_minutes", decimals=1)

    def populate_error_analysis(self, analysis: dict[str, list[dict[str, object]]]) -> None:
        self._fill_list(self.character_list, [f"{row['expected_character']} · {row['error_count']} 次" for row in analysis["characters"]])
        self._fill_list(
            self.combination_list,
            [f"{row['expected_character']} -> {row['actual_character']} · {row['error_count']} 次" for row in analysis["combinations"]],
        )
        self._fill_list(self.word_list, [f"{row['target_word']} · {row['error_count']} 次" for row in analysis["words"]])
        self._fill_list(
            self.type_list,
            [f"{row['error_type']} · {row['error_count']} 次（{row['percentage']:.1f}%）" for row in analysis["types"]],
        )

    def _set_metric(self, key: str, value: str) -> None:
        self.metric_labels[key].setText(value)

    def _fill_list(self, widget: QListWidget, lines: list[str]) -> None:
        widget.clear()
        if not lines:
            widget.addItem(QListWidgetItem("暂无数据"))
            return
        for line in lines[:20]:
            widget.addItem(QListWidgetItem(line))

    def _build_chart(self, title: str, axis_title: str) -> dict[str, object]:
        chart = QChart()
        chart.setTitle(title)
        chart.legend().hide()
        chart.setBackgroundVisible(False)
        chart.setPlotAreaBackgroundVisible(False)
        view = QChartView(chart)
        view.setMinimumHeight(240)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        return {"chart": chart, "view": view, "axis_title": axis_title}

    def _update_chart(self, chart_bundle: dict[str, object], rows: list[dict[str, object]], key: str, *, decimals: int) -> None:
        chart: QChart = chart_bundle["chart"]
        chart.removeAllSeries()
        for axis in chart.axes():
            chart.removeAxis(axis)

        meaningful = [row for row in rows if (row.get(key, 0.0) or 0.0) > 0]
        if not meaningful:
            chart.setTitle(f"{chart.title()}（暂无数据）")
            return

        base_title = chart.title().split("（", 1)[0]
        chart.setTitle(base_title)
        series = QLineSeries()
        categories: list[str] = []
        max_value = 0.0
        for index, row in enumerate(rows):
            value = float(row.get(key, 0.0) or 0.0)
            label = str(row["date"])[5:]
            categories.append(label)
            series.append(index, value)
            max_value = max(max_value, value)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories)
        axis_y = QValueAxis()
        axis_y.setTitleText(str(chart_bundle["axis_title"]))
        axis_y.setLabelFormat(f"%.{decimals}f")
        axis_y.setRange(0.0, max_value * 1.15 if max_value > 0 else 1.0)
        axis_y.setTickCount(5)

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_x)
        series.attachAxis(axis_y)
