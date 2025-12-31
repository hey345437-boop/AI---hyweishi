# -*- coding: utf-8 -*-
"""
兼容层：重定向到 core.async_market_fetcher

此文件保留用于向后兼容，新代码请使用:
    from core.async_market_fetcher import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.async_market_fetcher import *
