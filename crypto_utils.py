# -*- coding: utf-8 -*-
"""
兼容层：重定向到 utils.crypto_utils

此文件保留用于向后兼容，新代码请使用:
    from utils import encrypt_text, decrypt_text
    或
    from utils.crypto_utils import ...
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.crypto_utils import *
