# -*- coding: utf-8 -*-
"""
兼容层：重定向到 ui.ui_legacy

此文件保留用于向后兼容，新代码请使用:
    from ui import render_main
    或
    from ui.ui_legacy import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.ui_legacy import *
