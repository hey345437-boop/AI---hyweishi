# -*- coding: utf-8 -*-
"""
情绪数据缓存模块

功能：
- 内存缓存 + 数据库持久化
- 历史数据存储与查询
- 缓存过期管理
"""

import time
import json
import sqlite3
import threading
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CachedSentiment:
    """缓存的情绪数据"""
    fear_greed_value: int
    fear_greed_class: str
    news_score: int
    news_bias: str
    combined_score: int
    combined_bias: str
    key_events: List[str]
    timestamp: int


class SentimentCache:
    """情绪数据缓存管理器"""
    
    def __init__(self, db_path: str = "arena.db", memory_ttl: int = 60):
        self._db_path = db_path
        self._memory_ttl = memory_ttl
        self._memory_cache: Optional[CachedSentiment] = None
        self._memory_ts: float = 0
        self._lock = threading.Lock()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sentiment_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fear_greed_value INTEGER,
                    fear_greed_class TEXT,
                    news_score INTEGER,
                    news_bias TEXT,
                    combined_score INTEGER,
                    combined_bias TEXT,
                    key_events TEXT,
                    timestamp INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sentiment_ts 
                ON sentiment_history(timestamp)
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SentimentCache] 初始化数据库失败: {e}")
    
    def get(self) -> Optional[CachedSentiment]:
        """获取缓存的情绪数据"""
        with self._lock:
            now = time.time()
            if self._memory_cache and (now - self._memory_ts) < self._memory_ttl:
                return self._memory_cache
        return None
    
    def set(self, data: CachedSentiment, persist: bool = True):
        """设置缓存数据"""
        with self._lock:
            self._memory_cache = data
            self._memory_ts = time.time()
        
        if persist:
            self._persist(data)
    
    def _persist(self, data: CachedSentiment):
        """持久化到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO sentiment_history 
                (fear_greed_value, fear_greed_class, news_score, news_bias,
                 combined_score, combined_bias, key_events, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.fear_greed_value,
                data.fear_greed_class,
                data.news_score,
                data.news_bias,
                data.combined_score,
                data.combined_bias,
                json.dumps(data.key_events, ensure_ascii=False),
                data.timestamp
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[SentimentCache] 持久化失败: {e}")
    
    def get_history(self, hours: int = 24, limit: int = 100) -> List[Dict[str, Any]]:
        """获取历史情绪数据"""
        cutoff = int(time.time()) - hours * 3600
        results = []
        
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fear_greed_value, fear_greed_class, news_score, news_bias,
                       combined_score, combined_bias, key_events, timestamp
                FROM sentiment_history
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (cutoff, limit))
            
            for row in cursor.fetchall():
                results.append({
                    "fear_greed_value": row[0],
                    "fear_greed_class": row[1],
                    "news_score": row[2],
                    "news_bias": row[3],
                    "combined_score": row[4],
                    "combined_bias": row[5],
                    "key_events": json.loads(row[6]) if row[6] else [],
                    "timestamp": row[7]
                })
            conn.close()
        except Exception as e:
            print(f"[SentimentCache] 查询历史失败: {e}")
        
        return results
    
    def get_latest_from_db(self) -> Optional[Dict[str, Any]]:
        """从数据库获取最新记录"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT fear_greed_value, fear_greed_class, news_score, news_bias,
                       combined_score, combined_bias, key_events, timestamp
                FROM sentiment_history
                ORDER BY timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "fear_greed_value": row[0],
                    "fear_greed_class": row[1],
                    "news_score": row[2],
                    "news_bias": row[3],
                    "combined_score": row[4],
                    "combined_bias": row[5],
                    "key_events": json.loads(row[6]) if row[6] else [],
                    "timestamp": row[7]
                }
        except Exception as e:
            print(f"[SentimentCache] 查询最新记录失败: {e}")
        return None
    
    def cleanup_old(self, days: int = 7):
        """清理旧数据"""
        cutoff = int(time.time()) - days * 24 * 3600
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM sentiment_history WHERE timestamp < ?",
                (cutoff,)
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if deleted > 0:
                print(f"[SentimentCache] 清理了 {deleted} 条旧记录")
        except Exception as e:
            print(f"[SentimentCache] 清理失败: {e}")


# 全局单例
_cache: Optional[SentimentCache] = None


def get_sentiment_cache(db_path: str = "arena.db") -> SentimentCache:
    """获取情绪缓存单例"""
    global _cache
    if _cache is None:
        _cache = SentimentCache(db_path)
    return _cache
