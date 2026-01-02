# -*- coding: utf-8 -*-
"""
情绪指数获取模块
- Fear & Greed Index
- 其他情绪指标
"""

import requests
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SentimentData:
    """情绪数据"""
    value: int                    # 0-100
    classification: str           # Extreme Fear / Fear / Neutral / Greed / Extreme Greed
    timestamp: int                # Unix 时间戳
    source: str = "alternative.me"


class SentimentFetcher:
    """情绪数据获取器"""
    
    FEAR_GREED_API = "https://api.alternative.me/fng/"
    CACHE_TTL = 60  # 缓存 60 秒
    
    def __init__(self):
        self._cache: Optional[SentimentData] = None
        self._cache_ts: float = 0
    
    def get_fear_greed(self, use_cache: bool = True) -> Optional[SentimentData]:
        """获取恐惧贪婪指数"""
        now = time.time()
        
        # 检查缓存
        if use_cache and self._cache and (now - self._cache_ts) < self.CACHE_TTL:
            return self._cache
        
        try:
            response = requests.get(self.FEAR_GREED_API, timeout=5)
            if response.status_code == 200:
                data = response.json()
                item = data.get("data", [{}])[0]
                
                sentiment = SentimentData(
                    value=int(item.get("value", 50)),
                    classification=item.get("value_classification", "Neutral"),
                    timestamp=int(item.get("timestamp", time.time())),
                    source="alternative.me"
                )
                
                # 更新缓存
                self._cache = sentiment
                self._cache_ts = now
                
                return sentiment
        except Exception as e:
            print(f"[SentimentFetcher] 获取恐惧贪婪指数失败: {e}")
        
        return self._cache  # 返回旧缓存
    
    def get_sentiment_level(self, value: int) -> str:
        """根据数值返回情绪等级"""
        if value <= 20:
            return "extreme_fear"
        elif value <= 40:
            return "fear"
        elif value <= 60:
            return "neutral"
        elif value <= 80:
            return "greed"
        else:
            return "extreme_greed"
    
    def get_sentiment_emoji(self, value: int) -> str:
        """根据数值返回情绪 emoji"""
        if value <= 20:
            return "😱"
        elif value <= 40:
            return "😰"
        elif value <= 60:
            return "😐"
        elif value <= 80:
            return "😊"
        else:
            return "🤑"
    
    def get_trading_suggestion(self, value: int) -> str:
        """根据情绪给出交易建议"""
        if value <= 25:
            return "极度恐惧，可能是买入机会"
        elif value <= 40:
            return "市场恐惧，谨慎观望"
        elif value <= 60:
            return "情绪中性，按策略执行"
        elif value <= 75:
            return "市场贪婪，注意风险"
        else:
            return "极度贪婪，考虑减仓"


# 全局单例
_fetcher: Optional[SentimentFetcher] = None


def get_sentiment_fetcher() -> SentimentFetcher:
    """获取情绪获取器单例"""
    global _fetcher
    if _fetcher is None:
        _fetcher = SentimentFetcher()
    return _fetcher


def get_fear_greed_index() -> Optional[Dict[str, Any]]:
    """快捷函数：获取恐惧贪婪指数"""
    fetcher = get_sentiment_fetcher()
    data = fetcher.get_fear_greed()
    if data:
        return {
            "value": data.value,
            "classification": data.classification,
            "timestamp": data.timestamp,
            "level": fetcher.get_sentiment_level(data.value),
            "emoji": fetcher.get_sentiment_emoji(data.value),
            "suggestion": fetcher.get_trading_suggestion(data.value)
        }
    return None


def get_market_sentiment() -> Dict[str, Any]:
    """获取综合市场情绪（可扩展更多指标）"""
    result = {
        "fear_greed": get_fear_greed_index(),
        "timestamp": int(time.time()),
        "overall_score": 50,  # 默认中性
        "overall_bias": "neutral"
    }
    
    # 计算综合得分（目前只有 Fear & Greed）
    if result["fear_greed"]:
        result["overall_score"] = result["fear_greed"]["value"]
        if result["overall_score"] < 40:
            result["overall_bias"] = "bearish"
        elif result["overall_score"] > 60:
            result["overall_bias"] = "bullish"
    
    return result
