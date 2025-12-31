# -*- coding: utf-8 -*-
"""
兼容层：重定向到 core.trade_engine

此文件保留用于向后兼容，新代码请使用:
    from core import get_exchange_adapter, initialize_exchange
    或
    from core.trade_engine import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.trade_engine import *
