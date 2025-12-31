# -*- coding: utf-8 -*-
"""
兼容层：重定向到 strategies.pine_converter

此文件保留用于向后兼容，新代码请使用:
    from strategies.pine_converter import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategies.pine_converter import *
