# -*- coding: utf-8 -*-
"""
兼容层：重定向到 utils.symbol_utils

此文件保留用于向后兼容，新代码请使用:
    from utils import normalize_symbol
    或
    from utils.symbol_utils import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.symbol_utils import *
