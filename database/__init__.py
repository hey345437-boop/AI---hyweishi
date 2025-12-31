# -*- coding: utf-8 -*-
"""
数据库模块

包含数据库桥接层、配置、工具函数等
"""

from .db_bridge import (
    init_db,
    get_engine_status,
    get_control_flags,
    get_bot_config,
    update_bot_config,
    set_control_flags,
    get_paper_balance,
    get_paper_positions,
    get_hedge_positions,
    get_trade_stats,
    get_trade_history,
    get_bootstrap_state,
    get_credentials_status,
    verify_credentials_and_snapshot,
    get_pooled_connection
)
from .db_config import (
    get_db_config_from_env_and_secrets,
    PROJECT_ROOT,
    DATA_DIR
)
from .db_utils import (
    get_db_connection,
    update_engine_status,
    update_control_flags,
    insert_performance_metrics,
    get_recent_performance_metrics
)
from .connection_pool import (
    ConnectionPool,
    get_global_pool
)

__all__ = [
    # db_bridge
    'init_db', 'get_engine_status', 'get_control_flags', 'get_bot_config',
    'update_bot_config', 'set_control_flags', 'get_paper_balance',
    'get_paper_positions', 'get_hedge_positions', 'get_trade_stats',
    'get_trade_history', 'get_bootstrap_state', 'get_credentials_status',
    'verify_credentials_and_snapshot', 'get_pooled_connection',
    # db_config
    'get_db_config_from_env_and_secrets', 'PROJECT_ROOT', 'DATA_DIR',
    # db_utils
    'get_db_connection', 'update_engine_status', 'update_control_flags',
    'insert_performance_metrics', 'get_recent_performance_metrics',
    # connection_pool
    'ConnectionPool', 'get_global_pool'
]
