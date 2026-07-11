from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class UiTexts:
    app_name: str = "英语打字练习"
    window_title: str = "英语打字练习"
    nav_articles: str = "文章库"
    nav_special: str = "专项练习"
    nav_vocabulary: str = "生词本"
    nav_history: str = "练习记录"
    nav_statistics: str = "学习统计"
    nav_settings: str = "设置"
    common_refresh: str = "刷新"
    common_save: str = "保存"
    common_cancel: str = "取消"
    common_confirm: str = "确认"
    common_search_article: str = "搜索文章"
    common_empty_dash: str = "暂无"
    article_page_title: str = "文章库"
    article_page_subtitle: str = "导入英文文章，按段练习并记录进步"
    article_import: str = "导入文章"
    article_continue: str = "继续练习"
    article_restart: str = "从头练习"
    article_rename: str = "重命名"
    article_delete: str = "删除"
    article_resegment: str = "重新分段"
    article_more: str = "更多操作"
    article_empty_title: str = "还没有导入文章"
    article_empty_body: str = "导入一篇英文 TXT，在打字过程中练习英语并记录速度和正确率。"
    article_empty_button: str = "导入第一篇文章"
    article_unselected_title: str = "暂未选择文章"
    article_unselected_body: str = "从左侧选择一篇文章，查看详情并开始练习。"
    article_preview_hint: str = "导入一篇英文 TXT，开始第一次练习"
    article_delete_confirm_title: str = "删除文章"
    article_delete_confirm_body: str = "删除后文章会从列表中隐藏，但历史记录会保留。"
    article_resegment_confirm_title: str = "重新分段"
    article_resegment_confirm_body: str = "重新分段会重置当前文章进度，但不会删除历史记录。"
    import_result_title: str = "导入结果"
    no_article_selected: str = "请先选择一篇文章。"
    section_target_label: str = "默认分段"
    settings_saved: str = "设置已保存，新练习会使用新的配置。"
    special_title: str = "专项练习"
    special_subtitle: str = "根据历史错误、生词和上下文生成更有针对性的练习。"
    special_no_preview: str = "先生成预览，再开始练习。"
    special_no_content: str = "当前条件下还没有可生成的练习内容。"
    special_today_empty: str = "今天没有待复习单词"
    special_saved_title: str = "已保存练习"
    vocabulary_title: str = "生词本"
    vocabulary_empty: str = "生词本还是空的"
    history_title: str = "练习记录"
    history_empty: str = "暂无练习记录"
    statistics_title: str = "学习统计"
    statistics_empty: str = "还没有足够的数据来生成统计图。"
    settings_title: str = "设置"
    practice_back: str = "结束练习"
    practice_pause: str = "暂停"
    practice_resume: str = "继续"
    practice_hint: str = "直接在本页输入。已禁用粘贴，按 Esc 可暂停或继续。"
    result_retry_errors: str = "只重练本次出错内容"
    result_next: str = "继续下一段"
    result_restart: str = "再练一次"
    result_back: str = "返回"
    session_detail_title: str = "练习详情"
    delete_session_title: str = "删除练习记录"
    delete_session_body: str = "删除后将同时移除该次练习的详细错误记录。"
    import_error_empty: str = "所选 TXT 为空，无法导入。"
    missing_session: str = "这条练习记录已不存在。"
    invalid_word: str = "请输入有效的英文单词。"
    theme_light: str = "浅色"
    theme_dark: str = "深色"
    theme_system: str = "跟随系统"
    grouped_labels: dict[str, str] = field(
        default_factory=lambda: {
            "overview_articles": "文章数量",
            "overview_completed": "已完成",
            "overview_due_words": "今日待复习",
            "overview_section_target": "默认分段",
            "overview_last_practice": "最近练习",
            "stats_today_seconds": "今日练习",
            "stats_today_sessions": "今日次数",
            "stats_total_seconds": "累计时长",
            "stats_completed_sessions": "完成次数",
            "stats_average_wpm": "平均 WPM",
            "stats_highest_wpm": "最高有效 WPM",
            "stats_average_accuracy": "平均正确率",
            "stats_special_sessions": "专项练习",
            "stats_vocabulary_sessions": "生词复习",
            "stats_mastered_words": "已掌握单词",
            "stats_due_words": "待复习单词",
            "stats_streak_current": "当前连续天数",
            "stats_streak_longest": "最长连续天数",
        }
    )


TEXTS = UiTexts()
