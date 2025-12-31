# -*- coding: utf-8 -*-
"""
兼容层：重定向到 strategies.strategy_v1

此文件保留用于向后兼容，新代码请使用:
    from strategies.strategy_v1 import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategies.strategy_v1 import *
