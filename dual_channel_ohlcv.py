# -*- coding: utf-8 -*-
"""
兼容层：重定向到 dual_channel.dual_channel_ohlcv

此文件保留用于向后兼容，新代码请使用:
    from dual_channel import DualChannelOHLCV
    或
    from dual_channel.dual_channel_ohlcv import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dual_channel.dual_channel_ohlcv import *
