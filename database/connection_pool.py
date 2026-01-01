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
# connection_pool.py - 数据库连接池
"""
数据库连接池实现，支持 SQLite 和 PostgreSQL。
提高高频数据库操作的性能。
"""

import sqlite3
import threading
import time
import logging
from typing import Dict, Any, Optional, List
from queue import Queue, Empty
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 尝试导入 PostgreSQL 支持
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False


class ConnectionPool:
    """
    数据库连接池
    
    支持 SQLite 和 PostgreSQL，提供连接复用以提高性能。
    """
    
    DEFAULT_POOL_SIZE = 5
    DEFAULT_TIMEOUT = 30.0  # 秒
    
    def __init__(
        self,
        db_config: Dict[str, Any],
        pool_size: Optional[int] = None,
        timeout: Optional[float] = None
    ):
        """
        初始化连接池
        
        Args:
            db_config: 数据库配置，包含 kind, path/url 等
            pool_size: 连接池大小，默认 5
            timeout: 获取连接超时时间（秒），默认 30
        """
        self.db_config = db_config
        self.db_kind = db_config.get("kind", "sqlite")
        self.pool_size = pool_size or self.DEFAULT_POOL_SIZE
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        
        # 连接队列
        self._pool: Queue = Queue(maxsize=self.pool_size)
        self._lock = threading.Lock()
        self._created_count = 0
        
        logger.info(
            f"ConnectionPool 初始化 | 类型: {self.db_kind} | "
            f"池大小: {self.pool_size} | 超时: {self.timeout}s"
        )
    
    def _create_connection(self) -> Any:
        """创建新的数据库连接"""
        if self.db_kind == "postgres":
            if not PSYCOPG2_AVAILABLE:
                raise ImportError("psycopg2 not available")
            
            url = self.db_config.get("url")
            conn = psycopg2.connect(
                url,
                connect_timeout=10,
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=5
            )
            logger.debug("创建新的 PostgreSQL 连接")
            return conn
        else:
            path = self.db_config.get("path")
            conn = sqlite3.connect(path, check_same_thread=False)
            logger.debug(f"创建新的 SQLite 连接: {path}")
            return conn
    
    def _validate_connection(self, conn: Any) -> bool:
        """
        验证连接是否有效
        
        Args:
            conn: 数据库连接
        
        Returns:
            bool: 连接是否有效
        """
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception as e:
            logger.warning(f"连接验证失败: {e}")
            return False
    
    def get_connection(self, timeout: Optional[float] = None) -> Any:
        """
        获取数据库连接
        
        优先从池中获取，如果池空且未达到最大连接数则创建新连接。
        
        Args:
            timeout: 超时时间（秒），默认使用初始化时的配置
        
        Returns:
            数据库连接对象
        
        Raises:
            TimeoutError: 超时未能获取连接
        """
        timeout = timeout or self.timeout
        
        # 尝试从池中获取
        try:
            conn = self._pool.get(block=False)
            if self._validate_connection(conn):
                logger.debug("从池中获取有效连接")
                return conn
            else:
                # 连接无效，关闭并创建新的
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._created_count -= 1
        except Empty:
            pass
        
        # 池空，尝试创建新连接
        with self._lock:
            if self._created_count < self.pool_size:
                self._created_count += 1
                try:
                    conn = self._create_connection()
                    return conn
                except Exception as e:
                    self._created_count -= 1
                    raise
        
        # 池满，等待连接归还
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                conn = self._pool.get(block=True, timeout=1.0)
                if self._validate_connection(conn):
                    return conn
                else:
                    try:
                        conn.close()
                    except:
                        pass
                    with self._lock:
                        self._created_count -= 1
                    # 创建新连接替代
                    with self._lock:
                        if self._created_count < self.pool_size:
                            self._created_count += 1
                            return self._create_connection()
            except Empty:
                continue
        
        raise TimeoutError(f"获取数据库连接超时 ({timeout}s)")
    
    def return_connection(self, conn: Any) -> None:
        """
        归还连接到池
        
        Args:
            conn: 数据库连接
        """
        if conn is None:
            return
        
        try:
            # 验证连接是否有效
            if self._validate_connection(conn):
                try:
                    self._pool.put(conn, block=False)
                    logger.debug("连接已归还到池")
                except:
                    # 池满，关闭连接
                    conn.close()
                    with self._lock:
                        self._created_count -= 1
            else:
                # 连接无效，关闭
                conn.close()
                with self._lock:
                    self._created_count -= 1
        except Exception as e:
            logger.warning(f"归还连接时出错: {e}")
            with self._lock:
                self._created_count = max(0, self._created_count - 1)
    
    @contextmanager
    def connection(self):
        """
        上下文管理器，自动获取和归还连接
        
        Usage:
            with pool.connection() as conn:
                cursor = conn.cursor()
                ...
        """
        conn = None
        try:
            conn = self.get_connection()
            yield conn
        finally:
            if conn is not None:
                self.return_connection(conn)
    
    def close_all(self) -> None:
        """关闭所有连接"""
        logger.info("关闭连接池中的所有连接")
        while True:
            try:
                conn = self._pool.get(block=False)
                try:
                    conn.close()
                except:
                    pass
            except Empty:
                break
        
        with self._lock:
            self._created_count = 0
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        return {
            "pool_size": self.pool_size,
            "created_count": self._created_count,
            "available_count": self._pool.qsize(),
            "db_kind": self.db_kind
        }


# 全局连接池实例（懒加载）
_global_pool: Optional[ConnectionPool] = None
_pool_lock = threading.Lock()


def get_global_pool(db_config: Optional[Dict[str, Any]] = None) -> ConnectionPool:
    """
    获取全局连接池实例
    
    Args:
        db_config: 数据库配置，首次调用时必须提供
    
    Returns:
        ConnectionPool: 全局连接池实例
    """
    global _global_pool
    
    if _global_pool is None:
        with _pool_lock:
            if _global_pool is None:
                if db_config is None:
                    from db_config import get_db_config_from_env_and_secrets
                    _, db_config = get_db_config_from_env_and_secrets()
                _global_pool = ConnectionPool(db_config)
    
    return _global_pool
