# -*- coding: utf-8 -*-
"""
兼容层：重定向到 utils.beijing_time_converter

此文件保留用于向后兼容，新代码请使用:
    from utils import to_beijing_time
    或
    from utils.beijing_time_converter import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.beijing_time_converter import *
