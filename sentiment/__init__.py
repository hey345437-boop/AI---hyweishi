# -*- coding: utf-8 -*-
"""
市场情绪与新闻分析模块

功能：
- 恐惧贪婪指数获取
- 加密货币新闻爬取（多源）
- AI/本地情绪分析
- 重大事件识别与推送
- 链上数据监控（清算、巨鲸转账）

可与 AI 交易员模块联动，影响交易决策
"""

from .sentiment_fetcher import (
    SentimentFetcher,
    get_fear_greed_index,
    get_market_sentiment
)

from .news_fetcher import (
    NewsFetcher,
    NewsItem,
    get_latest_news
)

from .news_analyzer import (
    SmartNewsAnalyzer,
    NewsDigest,
    MarketSignal,
    get_smart_news_analyzer,
    get_news_analyzer,
    analyze_news_sentiment,
    get_market_impact
)

from .sentiment_cache import (
    SentimentCache,
    CachedSentiment,
    get_sentiment_cache
)

from .onchain_fetcher import (
    OnchainFetcher,
    get_onchain_fetcher,
    get_liquidation_data,
    get_whale_data
)

__all__ = [
    'SentimentFetcher',
    'get_fear_greed_index',
    'get_market_sentiment',
    'NewsFetcher',
    'NewsItem',
    'get_latest_news',
    'SmartNewsAnalyzer',
    'NewsDigest',
    'MarketSignal',
    'get_smart_news_analyzer',
    'get_news_analyzer',
    'analyze_news_sentiment',
    'get_market_impact',
    'SentimentCache',
    'CachedSentiment',
    'get_sentiment_cache',
    'OnchainFetcher',
    'get_onchain_fetcher',
    'get_liquidation_data',
    'get_whale_data',
]
