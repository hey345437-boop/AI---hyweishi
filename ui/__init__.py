# -*- coding: utf-8 -*-
"""
UI 界面模块

包含 Streamlit Web UI 组件
"""

from .ui_legacy import render_main, render_dashboard
from .ui_arena import render_arena_main, get_arena_mock_data
from .ui_strategy_builder import render_strategy_builder
from .ui_sentiment import (
    render_sentiment_card,
    render_sentiment_panel,
    get_sentiment_for_ai
)

__all__ = [
    'render_main',
    'render_dashboard',
    'render_arena_main',
    'get_arena_mock_data',
    'render_strategy_builder',
    'render_sentiment_card',
    'render_sentiment_panel',
    'get_sentiment_for_ai'
]
