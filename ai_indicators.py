# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_indicators

此文件保留用于向后兼容，新代码请使用:
    from ai import IndicatorCalculator, get_ai_indicators
    或
    from ai.ai_indicators import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_indicators import *
