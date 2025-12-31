# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_api_validator

此文件保留用于向后兼容，新代码请使用:
    from ai import validate_api_key
    或
    from ai.ai_api_validator import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_api_validator import *
