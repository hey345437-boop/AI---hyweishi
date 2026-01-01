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
#   Copyright (c) 2024-2025 HyWeiShi. All Rights Reserved.
#   License: AGPL-3.0
#
# ============================================================================
import sqlite3
import json
import time
from typing import Dict, List, Any, Optional
from core.config import DB_PATH

# 数据库表名常量
TABLE_BOT_CONFIG = "bot_config"
TABLE_ENGINE_STATUS = "engine_status"
TABLE_CONTROL_FLAGS = "control_flags"
TABLE_PERFORMANCE_METRICS = "performance_metrics"

# 错误处理常量
ERROR_DB_CONNECTION = "数据库连接错误"
ERROR_DB_EXECUTION = "数据库执行错误"
ERROR_DB_CLOSE = "数据库关闭错误"
ERROR_EMPTY_RESULT = "查询结果为空"

def get_db_connection():
    """获取数据库连接
    
    返回:
    - SQLite连接对象
    
    异常:
    - sqlite3.Error: 当数据库连接失败时
    """
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL;")  # 启用WAL模式，支持并发读写
        return conn
    except sqlite3.Error as e:
        print(f"{ERROR_DB_CONNECTION}: {e}")
        raise

def init_db():
    """初始化数据库，创建所需的表
    
    创建engine_status、control_flags、bot_config和performance_metrics表
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 创建bot_config表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bot_config (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    run_mode TEXT,
                    symbols TEXT,
                    base_position_size REAL,
                    enable_trading INTEGER,
                    updated_at INTEGER
                )
            """)
            
            # 创建engine_status表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS engine_status (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    ts INTEGER,
                    alive INTEGER,
                    cycle_ms INTEGER,
                    last_error TEXT,
                    last_okx_latency_ms INTEGER,
                    run_mode TEXT,
                    pause_trading INTEGER,
                    last_plan_order_json TEXT,
                    positions_json TEXT
                )
            """)
            
            # 创建control_flags表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS control_flags (
                    id INTEGER PRIMARY KEY CHECK (id=1),
                    stop_signal INTEGER DEFAULT 0,
                    pause_trading INTEGER DEFAULT 0,
                    reload_config INTEGER DEFAULT 0,
                    allow_live INTEGER DEFAULT 0,
                    emergency_flatten INTEGER DEFAULT 0
                )
            """)
            
            # 创建performance_metrics表用于存储性能指标历史
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts INTEGER,
                    cycle_ms INTEGER,
                    api_calls INTEGER,
                    avg_api_latency_ms REAL,
                    cache_hits INTEGER,
                    cache_misses INTEGER,
                    cache_hit_rate REAL,
                    errors INTEGER
                )
            """)
            
            # 初始化bot_config表
            cursor.execute("""
                INSERT OR REPLACE INTO bot_config 
                (id, run_mode, symbols, base_position_size, enable_trading, updated_at) 
                VALUES (1, 'sim', 'BTC/USDT:USDT,ETH/USDT:USDT', 0.01, 0, ?)
            """, (int(time.time() * 1000),))
            
            # 初始化engine_status表
            cursor.execute("""
                INSERT OR REPLACE INTO engine_status 
                (id, ts, alive, cycle_ms, last_error, last_okx_latency_ms, run_mode, pause_trading, last_plan_order_json, positions_json) 
                VALUES (1, 0, 0, 0, '', 0, 'sim', 1, '{}', '{}')
            """)
            
            # 初始化control_flags表
            cursor.execute("""
                INSERT OR REPLACE INTO control_flags 
                (id, stop_signal, pause_trading, reload_config, allow_live, emergency_flatten) 
                VALUES (1, 0, 1, 0, 0, 0)
            """)
            
            conn.commit()
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        raise

def get_engine_status() -> Dict[str, Any]:
    """获取引擎状态
    
    返回:
    - 引擎状态字典
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM engine_status WHERE id=1")
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'ts': row[1],
                    'alive': row[2],
                    'cycle_ms': row[3],
                    'last_error': row[4],
                    'last_okx_latency_ms': row[5],
                    'run_mode': row[6],
                    'pause_trading': row[7],
                    'last_plan_order_json': row[8],
                    'positions_json': row[9]
                }
            return {}
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return {}

def update_engine_status(status_data: Dict[str, Any]) -> bool:
    """更新引擎状态
    
    参数:
    - status_data: 状态数据字典
    
    返回:
    - bool: 操作是否成功
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 获取当前状态
            current_status = get_engine_status()
            
            # 更新字段，同时更新ts为当前时间
            status_data['ts'] = int(time.time() * 1000)
            for key, value in status_data.items():
                current_status[key] = value
            
            # 执行更新
            cursor.execute("""
                INSERT OR REPLACE INTO engine_status 
                (id, ts, alive, cycle_ms, last_error, last_okx_latency_ms, run_mode, pause_trading, last_plan_order_json, positions_json) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                current_status['id'],
                current_status['ts'],
                current_status['alive'],
                current_status['cycle_ms'],
                current_status['last_error'],
                current_status['last_okx_latency_ms'],
                current_status['run_mode'],
                current_status['pause_trading'],
                current_status['last_plan_order_json'],
                current_status['positions_json']
            ))
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return False

def get_bot_config() -> Dict[str, Any]:
    """获取机器人配置
    
    返回:
    - 机器人配置字典
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM bot_config WHERE id=1")
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'run_mode': row[1],
                    'symbols': row[2],
                    'base_position_size': row[3],
                    'enable_trading': row[4],
                    'updated_at': row[5]
                }
            return {}
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return {}

def update_bot_config(config_data: Dict[str, Any]) -> bool:
    """更新机器人配置
    
    参数:
    - config_data: 配置数据字典
    
    返回:
    - bool: 操作是否成功
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 获取当前配置
            current_config = get_bot_config()
            
            # 更新字段
            for key, value in config_data.items():
                current_config[key] = value
            
            # 更新时间戳
            current_config['updated_at'] = int(time.time() * 1000)
            
            # 执行更新
            cursor.execute("""
                INSERT OR REPLACE INTO bot_config 
                (id, run_mode, symbols, base_position_size, enable_trading, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                current_config['id'],
                current_config['run_mode'],
                current_config['symbols'],
                current_config['base_position_size'],
                current_config['enable_trading'],
                current_config['updated_at']
            ))
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return False

def get_control_flags() -> Dict[str, Any]:
    """获取控制标志
    
    返回:
    - 控制标志字典
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM control_flags WHERE id=1")
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'stop_signal': row[1],
                    'pause_trading': row[2],
                    'reload_config': row[3],
                    'allow_live': row[4],
                    'emergency_flatten': row[5]
                }
            return {}
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return {}

def update_control_flags(flags_data: Dict[str, Any]) -> bool:
    """更新控制标志
    
    参数:
    - flags_data: 控制标志数据字典
    
    返回:
    - bool: 操作是否成功
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 获取当前控制标志
            current_flags = get_control_flags()
            
            # 更新字段
            for key, value in flags_data.items():
                current_flags[key] = value
            
            # 执行更新
            cursor.execute("""
                INSERT OR REPLACE INTO control_flags 
                (id, stop_signal, pause_trading, reload_config, allow_live, emergency_flatten) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                current_flags['id'],
                current_flags['stop_signal'],
                current_flags['pause_trading'],
                current_flags['reload_config'],
                current_flags['allow_live'],
                current_flags['emergency_flatten']
            ))
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return False

def reset_reload_config_flag() -> bool:
    """重置重载配置标志
    
    返回:
    - bool: 操作是否成功
    """
    return update_control_flags({'reload_config': 0})

def reset_stop_signal() -> bool:
    """重置停止信号
    
    返回:
    - bool: 操作是否成功
    """
    return update_control_flags({'stop_signal': 0})

def check_engine_status() -> bool:
    """检查引擎状态
    
    返回:
    - 引擎是否活跃
    """
    status = get_engine_status()
    return status.get('alive', 0) == 1 and status.get('ts', 0) > 0

def get_engine_activity_time() -> int:
    """获取引擎活跃时间
    
    返回:
    - 引擎活跃时间(毫秒)
    """
    status = get_engine_status()
    if status.get('alive', 0) == 1:
        return int(time.time() * 1000) - status.get('ts', 0)
    return 0

def insert_performance_metrics(metrics: Dict[str, Any]) -> bool:
    """插入性能指标记录
    
    参数:
    - metrics: 性能指标字典
    
    返回:
    - bool: 操作是否成功
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # 插入新记录
            cursor.execute("""
                INSERT INTO performance_metrics 
                (ts, cycle_ms, api_calls, avg_api_latency_ms, cache_hits, cache_misses, cache_hit_rate, errors) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(time.time() * 1000),  # 毫秒时间戳
                metrics.get('cycle_ms', 0),
                metrics.get('api_calls', 0),
                metrics.get('avg_api_latency_ms', 0),
                metrics.get('cache_hits', 0),
                metrics.get('cache_misses', 0),
                metrics.get('cache_hit_rate', 0),
                metrics.get('errors', 0)
            ))
            
            # 保持表的大小限制在最近100条记录
            cursor.execute("""
                DELETE FROM performance_metrics WHERE id NOT IN (
                    SELECT id FROM performance_metrics ORDER BY ts DESC LIMIT 100
                )
            """)
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return False

def get_recent_performance_metrics(limit: int = 20) -> List[Dict[str, Any]]:
    """获取最近的性能指标记录
    
    参数:
    - limit: 返回的记录数量，默认20条
    
    返回:
    - 性能指标记录列表，按时间升序排列
    
    异常:
    - sqlite3.Error: 当数据库执行失败时
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT ts, cycle_ms, api_calls, avg_api_latency_ms, cache_hits, cache_misses, cache_hit_rate, errors 
                FROM performance_metrics 
                ORDER BY ts DESC 
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            
            # 转换为字典列表
            metrics_list = []
            for row in rows:
                metrics_list.append({
                    'ts': row[0],
                    'cycle_ms': row[1],
                    'api_calls': row[2],
                    'avg_api_latency_ms': row[3],
                    'cache_hits': row[4],
                    'cache_misses': row[5],
                    'cache_hit_rate': row[6],
                    'errors': row[7]
                })
            
            # 按时间升序返回
            return list(reversed(metrics_list))
    except sqlite3.Error as e:
        print(f"{ERROR_DB_EXECUTION}: {e}")
        return []