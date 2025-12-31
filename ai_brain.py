# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_brain

此文件保留用于向后兼容，新代码请使用:
    from ai import MarketContext, AIDecisionResult, BaseAgent
    或
    from ai.ai_brain import ...
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 从新位置导入所有内容
from ai.ai_brain import *
