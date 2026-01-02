# -*- coding: utf-8 -*-
"""
新闻情绪分析模块

功能：
- AI 智能分析新闻，生成压缩摘要
- 仅在新闻变化或多空比异常时触发分析
- 本地缓存最多 5 条分析结果
- 输出格式：简短关键词（如 "马斯克买入BTC" "SEC批准ETF"）
"""

import time
import json
import sqlite3
import hashlib
import asyncio
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

from .news_fetcher import NewsItem, NewsImpact, get_news_fetcher

logger = logging.getLogger(__name__)


@dataclass
class NewsDigest:
    """新闻摘要（AI 分析结果）"""
    news_id: str              # 新闻唯一标识（标题 hash）
    summary: str              # 压缩摘要（如 "马斯克买入BTC"）
    impact: str               # bullish / bearish / neutral
    score: int                # -100 到 +100
    source: str               # 来源
    analyzed_at: int          # 分析时间戳
    original_title: str       # 原始标题（用于去重）


@dataclass 
class MarketSignal:
    """市场信号（多空比等）"""
    signal_type: str          # long_short_ratio / whale_transfer / etc
    value: float              # 数值
    interpretation: str       # AI 解读
    timestamp: int


class NewsAnalysisCache:
    """
    新闻分析缓存
    
    - 最多存储 5 条 AI 分析结果
    - 按时间排序，新的在前
    - 持久化到 SQLite
    """
    
    MAX_CACHE_SIZE = 5
    
    def __init__(self, db_path: str = "arena.db"):
        self._db_path = db_path
        self._cache: List[NewsDigest] = []
        self._signals: List[MarketSignal] = []
        self._last_news_hash: str = ""
        self._last_analysis_time: int = 0
        self._init_db()
        self._load_from_db()
    
    def _init_db(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # 新闻摘要表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_digest_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id TEXT UNIQUE,
                    summary TEXT,
                    impact TEXT,
                    score INTEGER,
                    source TEXT,
                    analyzed_at INTEGER,
                    original_title TEXT
                )
            """)
            
            # 市场信号表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS market_signal_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_type TEXT,
                    value REAL,
                    interpretation TEXT,
                    timestamp INTEGER
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[NewsAnalysisCache] 初始化数据库失败: {e}")
    
    def _load_from_db(self):
        """从数据库加载缓存"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # 加载新闻摘要
            cursor.execute("""
                SELECT news_id, summary, impact, score, source, analyzed_at, original_title
                FROM news_digest_cache
                ORDER BY analyzed_at DESC
                LIMIT ?
            """, (self.MAX_CACHE_SIZE,))
            
            self._cache = []
            for row in cursor.fetchall():
                self._cache.append(NewsDigest(
                    news_id=row[0],
                    summary=row[1],
                    impact=row[2],
                    score=row[3],
                    source=row[4],
                    analyzed_at=row[5],
                    original_title=row[6]
                ))
            
            # 加载市场信号（最近 3 条）
            cursor.execute("""
                SELECT signal_type, value, interpretation, timestamp
                FROM market_signal_cache
                ORDER BY timestamp DESC
                LIMIT 3
            """)
            
            self._signals = []
            for row in cursor.fetchall():
                self._signals.append(MarketSignal(
                    signal_type=row[0],
                    value=row[1],
                    interpretation=row[2],
                    timestamp=row[3]
                ))
            
            conn.close()
            logger.debug(f"[NewsAnalysisCache] 加载了 {len(self._cache)} 条新闻摘要")
        except Exception as e:
            logger.error(f"[NewsAnalysisCache] 加载缓存失败: {e}")
    
    def _save_digest(self, digest: NewsDigest):
        """保存新闻摘要到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO news_digest_cache
                (news_id, summary, impact, score, source, analyzed_at, original_title)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                digest.news_id,
                digest.summary,
                digest.impact,
                digest.score,
                digest.source,
                digest.analyzed_at,
                digest.original_title
            ))
            
            # 清理超出限制的旧记录
            cursor.execute("""
                DELETE FROM news_digest_cache
                WHERE id NOT IN (
                    SELECT id FROM news_digest_cache
                    ORDER BY analyzed_at DESC
                    LIMIT ?
                )
            """, (self.MAX_CACHE_SIZE,))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[NewsAnalysisCache] 保存摘要失败: {e}")
    
    def _save_signal(self, signal: MarketSignal):
        """保存市场信号到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO market_signal_cache
                (signal_type, value, interpretation, timestamp)
                VALUES (?, ?, ?, ?)
            """, (
                signal.signal_type,
                signal.value,
                signal.interpretation,
                signal.timestamp
            ))
            
            # 只保留最近 10 条
            cursor.execute("""
                DELETE FROM market_signal_cache
                WHERE id NOT IN (
                    SELECT id FROM market_signal_cache
                    ORDER BY timestamp DESC
                    LIMIT 10
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[NewsAnalysisCache] 保存信号失败: {e}")
    
    def add_digest(self, digest: NewsDigest):
        """添加新闻摘要"""
        # 检查是否已存在
        for existing in self._cache:
            if existing.news_id == digest.news_id:
                return
        
        # 添加到缓存
        self._cache.insert(0, digest)
        
        # 限制大小
        if len(self._cache) > self.MAX_CACHE_SIZE:
            self._cache = self._cache[:self.MAX_CACHE_SIZE]
        
        # 持久化
        self._save_digest(digest)
        self._last_analysis_time = int(time.time())
    
    def add_signal(self, signal: MarketSignal):
        """添加市场信号"""
        self._signals.insert(0, signal)
        if len(self._signals) > 3:
            self._signals = self._signals[:3]
        self._save_signal(signal)
    
    def get_digests(self) -> List[NewsDigest]:
        """获取所有缓存的摘要"""
        return self._cache.copy()
    
    def get_signals(self) -> List[MarketSignal]:
        """获取市场信号"""
        return self._signals.copy()
    
    def get_news_ids(self) -> set:
        """获取已分析的新闻 ID"""
        return {d.news_id for d in self._cache}
    
    def format_for_ai(self) -> str:
        """格式化为 AI 可读的文本"""
        lines = []
        
        if self._cache:
            lines.append("【新闻摘要】")
            for d in self._cache[:5]:
                impact_icon = "↑" if d.impact == "bullish" else ("↓" if d.impact == "bearish" else "→")
                lines.append(f"  {impact_icon} {d.summary}")
        
        if self._signals:
            lines.append("【市场信号】")
            for s in self._signals[:3]:
                lines.append(f"  • {s.interpretation}")
        
        return "\n".join(lines) if lines else ""


class SmartNewsAnalyzer:
    """
    智能新闻分析器
    
    - 检测新闻变化，仅在有新内容时触发 AI 分析
    - 检测多空比异常，触发信号分析
    - 生成压缩摘要供决策 AI 使用
    """
    
    # 触发分析的阈值
    LONG_SHORT_THRESHOLD_HIGH = 2.5   # 多空比 > 2.5 触发
    LONG_SHORT_THRESHOLD_LOW = 0.4    # 多空比 < 0.4 触发
    MIN_ANALYSIS_INTERVAL = 300       # 最小分析间隔（秒）
    
    def __init__(self, db_path: str = "arena.db"):
        self._cache = NewsAnalysisCache(db_path)
        self._last_long_short_ratio: Optional[float] = None
        self._ai_provider: str = "deepseek"
    
    def set_ai_provider(self, provider: str):
        """设置 AI 服务商"""
        self._ai_provider = provider
    
    def _hash_news(self, title: str) -> str:
        """生成新闻唯一标识"""
        return hashlib.md5(title.encode()).hexdigest()[:12]
    
    def _should_analyze_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """判断哪些新闻需要分析"""
        existing_ids = self._cache.get_news_ids()
        new_news = []
        
        for news in news_list:
            news_id = self._hash_news(news.title)
            if news_id not in existing_ids:
                # 只分析高影响新闻
                if news.impact == NewsImpact.HIGH:
                    new_news.append(news)
        
        return new_news[:3]  # 最多分析 3 条
    
    def _should_analyze_long_short(self, ratio: float) -> bool:
        """判断是否需要分析多空比"""
        if self._last_long_short_ratio is None:
            self._last_long_short_ratio = ratio
            return False
        
        # 检查是否超过阈值
        if ratio > self.LONG_SHORT_THRESHOLD_HIGH or ratio < self.LONG_SHORT_THRESHOLD_LOW:
            # 检查是否有显著变化
            change = abs(ratio - self._last_long_short_ratio)
            if change > 0.3:
                self._last_long_short_ratio = ratio
                return True
        
        self._last_long_short_ratio = ratio
        return False
    
    async def analyze_news_with_ai(self, news: NewsItem) -> Optional[NewsDigest]:
        """使用 AI 分析单条新闻，生成压缩摘要"""
        try:
            from ai.ai_providers import create_client, get_provider
            
            provider = get_provider(self._ai_provider)
            if not provider:
                logger.warning(f"[SmartNewsAnalyzer] 未找到 AI 服务商: {self._ai_provider}")
                return None
            
            client = create_client(provider)
            if not client:
                return None
            
            prompt = f"""分析这条加密货币新闻，用最简短的中文描述其影响：

标题：{news.title}
来源：{news.source}

要求：
1. 用 10 字以内概括（如 "马斯克买入BTC" "SEC批准ETF" "交易所被黑"）
2. 判断影响：bullish（利多）/ bearish（利空）/ neutral（中性）
3. 打分：-100 到 +100

JSON 格式回复：
{{"summary": "简短摘要", "impact": "bullish/bearish/neutral", "score": 0}}"""

            response = await client.chat(prompt)
            
            # 解析响应
            content = response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
                return NewsDigest(
                    news_id=self._hash_news(news.title),
                    summary=result.get("summary", news.title[:20]),
                    impact=result.get("impact", "neutral"),
                    score=result.get("score", 0),
                    source=news.source,
                    analyzed_at=int(time.time()),
                    original_title=news.title
                )
        except Exception as e:
            logger.error(f"[SmartNewsAnalyzer] AI 分析新闻失败: {e}")
        
        return None
    
    async def analyze_long_short_with_ai(self, ratio: float, symbol: str = "BTC") -> Optional[MarketSignal]:
        """使用 AI 分析多空比"""
        try:
            from ai.ai_providers import create_client, get_provider
            
            provider = get_provider(self._ai_provider)
            if not provider:
                return None
            
            client = create_client(provider)
            if not client:
                return None
            
            prompt = f"""{symbol} 当前多空比为 {ratio:.2f}，用一句话（15字以内）解读：

例如：
- 多空比 3.0 → "多头过度拥挤，警惕回调"
- 多空比 0.3 → "空头极端，可能反弹"
- 多空比 1.2 → "多空均衡，观望为主"

直接回复解读，不要其他内容。"""

            response = await client.chat(prompt)
            interpretation = response.strip()[:30]
            
            return MarketSignal(
                signal_type="long_short_ratio",
                value=ratio,
                interpretation=interpretation,
                timestamp=int(time.time())
            )
        except Exception as e:
            logger.error(f"[SmartNewsAnalyzer] AI 分析多空比失败: {e}")
        
        return None
    
    async def update(
        self, 
        news_list: Optional[List[NewsItem]] = None,
        long_short_ratio: Optional[float] = None
    ) -> bool:
        """
        更新分析（智能触发）
        
        返回：是否进行了新的分析
        """
        analyzed = False
        
        # 检查新闻
        if news_list:
            new_news = self._should_analyze_news(news_list)
            for news in new_news:
                digest = await self.analyze_news_with_ai(news)
                if digest:
                    self._cache.add_digest(digest)
                    analyzed = True
                    logger.info(f"[SmartNewsAnalyzer] 新闻分析: {digest.summary}")
        
        # 检查多空比
        if long_short_ratio is not None:
            if self._should_analyze_long_short(long_short_ratio):
                signal = await self.analyze_long_short_with_ai(long_short_ratio)
                if signal:
                    self._cache.add_signal(signal)
                    analyzed = True
                    logger.info(f"[SmartNewsAnalyzer] 多空比分析: {signal.interpretation}")
        
        return analyzed
    
    def update_sync(
        self,
        news_list: Optional[List[NewsItem]] = None,
        long_short_ratio: Optional[float] = None
    ) -> bool:
        """同步版本的 update"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 在已有事件循环中
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.update(news_list, long_short_ratio)
                    )
                    return future.result(timeout=30)
            else:
                return asyncio.run(self.update(news_list, long_short_ratio))
        except Exception as e:
            logger.error(f"[SmartNewsAnalyzer] 同步更新失败: {e}")
            return False
    
    def get_formatted_context(self) -> str:
        """获取格式化的上下文（供决策 AI 使用）"""
        return self._cache.format_for_ai()
    
    def get_digests(self) -> List[NewsDigest]:
        """获取新闻摘要列表"""
        return self._cache.get_digests()
    
    def get_signals(self) -> List[MarketSignal]:
        """获取市场信号列表"""
        return self._cache.get_signals()


# 全局单例
_analyzer: Optional[SmartNewsAnalyzer] = None


def get_smart_news_analyzer(db_path: str = "arena.db") -> SmartNewsAnalyzer:
    """获取智能新闻分析器单例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = SmartNewsAnalyzer(db_path)
    return _analyzer


# 兼容旧接口
def get_news_analyzer():
    """兼容旧接口"""
    return get_smart_news_analyzer()


def analyze_news_sentiment(limit: int = 20) -> Dict[str, Any]:
    """快捷函数：获取新闻情绪分析结果"""
    analyzer = get_smart_news_analyzer()
    digests = analyzer.get_digests()
    
    if not digests:
        return {
            "overall_score": 0,
            "bias": "neutral",
            "key_events": [],
            "formatted": ""
        }
    
    # 计算综合分数
    total_score = sum(d.score for d in digests)
    avg_score = total_score // len(digests) if digests else 0
    
    # 确定偏向
    bullish_count = sum(1 for d in digests if d.impact == "bullish")
    bearish_count = sum(1 for d in digests if d.impact == "bearish")
    
    if bullish_count > bearish_count:
        bias = "bullish"
    elif bearish_count > bullish_count:
        bias = "bearish"
    else:
        bias = "neutral"
    
    return {
        "overall_score": avg_score,
        "bias": bias,
        "key_events": [d.summary for d in digests],
        "formatted": analyzer.get_formatted_context()
    }


def get_market_impact() -> Dict[str, Any]:
    """获取综合市场影响"""
    from .sentiment_fetcher import get_fear_greed_index
    
    # 获取恐惧贪婪指数
    fear_greed = get_fear_greed_index()
    
    # 获取新闻情绪
    news_sentiment = analyze_news_sentiment()
    
    # 综合计算
    fg_score = fear_greed.get("value", 50) if fear_greed else 50
    news_score = news_sentiment.get("overall_score", 0)
    
    # 加权平均
    fg_normalized = (fg_score - 50) * 2
    combined_score = int(fg_normalized * 0.6 + news_score * 0.4)
    
    if combined_score > 20:
        combined_bias = "bullish"
    elif combined_score < -20:
        combined_bias = "bearish"
    else:
        combined_bias = "neutral"
    
    return {
        "combined_score": combined_score,
        "combined_bias": combined_bias,
        "fear_greed": fear_greed,
        "news_sentiment": news_sentiment,
        "key_events": news_sentiment.get("key_events", []),
        "formatted_news": news_sentiment.get("formatted", ""),
        "timestamp": int(time.time())
    }
