# -*- coding: utf-8 -*-
# ============================================================================
#
#    _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
#   | | | | \ \ / / \ \      / / | ____||_ _|/ ___| | | | ||_ _|
#   | |_| |  \ V /   \ \ /\ / /  |  _|   | | \___ \ | |_| | | | 
#   |  _  |   | |     \ V  V /   | |___  | |  ___) ||  _  | | | 
#   |_| |_|   |_|      \_/\_/    |_____||___||____/ |_| |_||___|
#
#                         何 以 为 势
#                  Quantitative Trading System
#
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
import os
from pathlib import Path

# ============ 数据库配置（支持外部数据库）============
DB_URL = os.getenv("DATABASE_URL")  # Render的外部数据库URL

# 固定数据目录（部署时请把 ./data 挂载为持久化卷）
DATA_DIR = os.getenv("MYTRADINGBOT_DATA_DIR", str(Path(__file__).resolve().parent / "data"))
DB_FILE = "quant_system.db"

# 项目根目录（包含db_config.py的目录）
PROJECT_ROOT = Path(__file__).resolve().parent

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)


def get_db_config_from_env_and_secrets():
    """获取数据库配置，优先使用外部数据库，不存在则使用本地SQLite
    
    Returns:
        tuple: (db_kind, config)
            db_kind: str - "postgres"或"sqlite"
            config: dict - 包含数据库配置信息
                对于PostgreSQL: {"url": postgres_url, "kind": "postgres"}
                对于SQLite: {"path": sqlite_path, "kind": "sqlite"}
                
    Note:
        SQLite 路径始终返回绝对路径，防止工作目录变化导致的问题
    """
    # 每次调用时重新读取环境变量，支持动态配置
    db_url = os.getenv("DATABASE_URL")
    
    if db_url:
        # 兼容两种 PostgreSQL URL 前缀
        if db_url.startswith("postgres://"):
            postgres_url = db_url.replace("postgres://", "postgresql://", 1)
        else:
            postgres_url = db_url
        
        if postgres_url.startswith("postgresql://"):
            return "postgres", {"url": postgres_url, "kind": "postgres"}
    
    # 默认使用SQLite，使用 DATA_DIR 作为基准路径
    # 确保返回绝对路径
    sqlite_path = os.path.join(DATA_DIR, DB_FILE)
    sqlite_path = os.path.abspath(sqlite_path)  # 转换为绝对路径
    return "sqlite", {"path": sqlite_path, "kind": "sqlite"}
