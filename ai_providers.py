# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ai.ai_providers

此文件保留用于向后兼容，新代码请使用:
    from ai import AI_PROVIDERS, UniversalAIClient
    或
    from ai.ai_providers import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.ai_providers import *
