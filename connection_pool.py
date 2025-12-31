# -*- coding: utf-8 -*-
"""
兼容层：重定向到 database.connection_pool

此文件保留用于向后兼容，新代码请使用:
    from database import ConnectionPool, get_global_pool
    或
    from database.connection_pool import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.connection_pool import *
