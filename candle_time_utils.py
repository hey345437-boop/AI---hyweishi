# -*- coding: utf-8 -*-
"""
兼容层：重定向到 utils.candle_time_utils

此文件保留用于向后兼容，新代码请使用:
    from utils import get_candle_open_time
    或
    from utils.candle_time_utils import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.candle_time_utils import *
