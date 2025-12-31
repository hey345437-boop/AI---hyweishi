# -*- coding: utf-8 -*-
"""
兼容层：重定向到 exchange.exchange_adapter

此文件保留用于向后兼容，新代码请使用:
    from exchange import ExchangeAdapter
    或
    from exchange.exchange_adapter import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchange.exchange_adapter import *
