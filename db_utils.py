# -*- coding: utf-8 -*-
"""
兼容层：重定向到 database.db_utils

此文件保留用于向后兼容，新代码请使用:
    from database import get_db_connection
    或
    from database.db_utils import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_utils import *
