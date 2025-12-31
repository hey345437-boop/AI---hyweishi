# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_config_manager

此文件保留用于向后兼容，新代码请使用:
    from ai import AIConfigManager, get_ai_config_manager
    或
    from ai.ai_config_manager import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_config_manager import *
