# -*- coding: utf-8 -*-
"""
兼容层：重定向到 database.db_config

此文件保留用于向后兼容，新代码请使用:
    from database import get_db_config_from_env_and_secrets
    或
    from database.db_config import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_config import *
