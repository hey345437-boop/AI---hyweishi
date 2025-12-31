# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_db_manager

此文件保留用于向后兼容，新代码请使用:
    from ai import AIDBManager, get_ai_db_manager
    或
    from ai.ai_db_manager import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_db_manager import *
