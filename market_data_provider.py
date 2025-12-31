# -*- coding: utf-8 -*-
"""
兼容层：重定向到 core.market_data_provider

此文件保留用于向后兼容，新代码请使用:
    from core import MarketDataProvider
    或
    from core.market_data_provider import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.market_data_provider import *
