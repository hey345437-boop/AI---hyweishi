# -*- coding: utf-8 -*-
"""
加密货币新闻爬取模块

支持多个新闻源：
- CoinDesk RSS
- CoinTelegraph RSS  
- The Defiant RSS
- Blockworks RSS
"""

import requests
import time
import re
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading
import concurrent.futures


class NewsSource(Enum):
    """新闻源"""
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"
    DEFIANT = "defiant"
    BLOCKWORKS = "blockworks"


class NewsImpact(Enum):
    """新闻影响程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class NewsItem:
    """新闻条目"""
    title: str
    summary: str = ""
    url: str = ""
    source: str = ""
    published_at: int = 0
    impact: NewsImpact = NewsImpact.LOW
    sentiment_score: int = 0
    related_coins: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "source": self.source,
            "published_at": self.published_at,
            "impact": self.impact.value,
            "sentiment_score": self.sentiment_score,
            "related_coins": self.related_coins,
            "keywords": self.keywords
        }


class NewsFetcher:
    """新闻获取器"""
    
    RSS_SOURCES = {
        NewsSource.COINDESK: "https://www.coindesk.com/arc/outboundfeeds/rss/",
        NewsSource.COINTELEGRAPH: "https://cointelegraph.com/rss",
        NewsSource.DEFIANT: "https://thedefiant.io/feed",
        NewsSource.BLOCKWORKS: "https://blockworks.co/feed",
    }
    
    SOURCE_ABBR = {
        NewsSource.COINDESK: "CD",
        NewsSource.COINTELEGRAPH: "CT",
        NewsSource.DEFIANT: "DL",
        NewsSource.BLOCKWORKS: "BM",
    }
    
    # 高影响关键词
    HIGH_IMPACT_KEYWORDS = [
        # 监管/法律
        "etf", "sec", "cftc", "approval", "approved", "reject", "ban", "lawsuit", "regulation",
        "批准", "通过", "监管", "禁止", "诉讼",
        # 安全事件
        "hack", "hacked", "exploit", "stolen", "breach", "vulnerability",
        "黑客", "攻击", "盗取", "漏洞",
        # 市场剧烈波动
        "crash", "surge", "soar", "plunge", "record", "all-time",
        "暴跌", "暴涨", "崩盘", "创新高", "历史",
        # 重大事件
        "halving", "fork", "bankruptcy", "collapse", "liquidat",
        "减半", "分叉", "破产", "清算", "爆仓",
        # 大额资金
        "billion", "million", "$1b", "$500m",
    ]
    
    # 中等影响关键词
    MEDIUM_IMPACT_KEYWORDS = [
        "launch", "partnership", "integration", "upgrade", "update",
        "whale", "institutional", "adoption", "listing",
        "上线", "合作", "升级", "巨鲸", "机构",
    ]
    
    # 币种关键词
    COIN_KEYWORDS = {
        "BTC": ["bitcoin", "btc", "比特币", "₿"],
        "ETH": ["ethereum", "eth", "以太坊", "ether"],
        "SOL": ["solana", "sol"],
        "BNB": ["binance", "bnb", "币安"],
        "XRP": ["ripple", "xrp", "瑞波"],
        "DOGE": ["dogecoin", "doge", "狗狗币"],
        "ADA": ["cardano", "ada"],
        "AVAX": ["avalanche", "avax"],
        "DOT": ["polkadot", "dot", "波卡"],
        "LINK": ["chainlink", "link"],
    }
    
    # 看涨关键词
    BULLISH_KEYWORDS = [
        # 英文
        "surge", "soar", "rally", "jump", "spike", "breakout", "bullish", "bull",
        "approval", "approved", "adopt", "adoption", "partnership", "launch",
        "record high", "all-time high", "ath", "buy", "accumulate", "inflow",
        "upgrade", "growth", "gain", "rise", "climb", "recover", "rebound",
        # 中文
        "批准", "通过", "利好", "上涨", "突破", "新高", "反弹", "飙升",
        "合作", "升级", "采用", "增持", "买入", "看涨", "牛市", "利多",
    ]
    
    # 看跌关键词
    BEARISH_KEYWORDS = [
        # 英文
        "crash", "plunge", "dump", "drop", "fall", "decline", "bearish", "bear",
        "hack", "hacked", "exploit", "stolen", "breach", "scam", "fraud",
        "ban", "banned", "lawsuit", "sue", "investigation", "reject",
        "bankruptcy", "collapse", "liquidat", "outflow", "sell", "selling",
        # 中文
        "黑客", "攻击", "暴跌", "禁止", "诉讼", "欺诈", "破产", "跑路",
        "清算", "爆仓", "下跌", "崩盘", "利空", "熊市", "抛售",
    ]
    
    def __init__(self, cache_ttl: int = 90):
        self._cache: Dict[str, List[NewsItem]] = {}
        self._cache_ts: Dict[str, float] = {}
        self._cache_ttl = cache_ttl
        self._lock = threading.Lock()
        self._translation_cache: Dict[str, str] = {}
    
    def fetch_rss(self, source: NewsSource, limit: int = 15) -> List[NewsItem]:
        """从 RSS 源获取新闻"""
        if source not in self.RSS_SOURCES:
            return []
        
        cache_key = source.value
        now = time.time()
        
        with self._lock:
            if cache_key in self._cache:
                if (now - self._cache_ts.get(cache_key, 0)) < self._cache_ttl:
                    return self._cache[cache_key][:limit]
        
        url = self.RSS_SOURCES[source]
        news_list = []
        
        try:
            response = requests.get(url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                
                for item in root.findall(".//item")[:limit]:
                    title = item.findtext("title", "")
                    description = item.findtext("description", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")
                    
                    published_at = self._parse_rss_date(pub_date)
                    
                    # 翻译标题
                    translated_title = self._translate_to_chinese(title)
                    
                    source_abbr = self.SOURCE_ABBR.get(source, "??")
                    
                    news_item = NewsItem(
                        title=translated_title,
                        summary=self._clean_html(description)[:200],
                        url=link,
                        source=source_abbr,
                        published_at=published_at
                    )
                    
                    self._analyze_news_item(news_item)
                    news_list.append(news_item)
                
                with self._lock:
                    self._cache[cache_key] = news_list
                    self._cache_ts[cache_key] = now
                
        except Exception as e:
            # 静默处理，返回缓存数据
            with self._lock:
                if cache_key in self._cache:
                    return self._cache[cache_key][:limit]
        
        return news_list[:limit]
    
    def fetch_all_sources(self, limit_per_source: int = 10) -> List[NewsItem]:
        """从所有源并行获取新闻"""
        all_news = []
        sources = list(NewsSource)
        
        # 并行获取
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(self.fetch_rss, source, limit_per_source): source 
                for source in sources
            }
            try:
                for future in concurrent.futures.as_completed(futures, timeout=15):
                    try:
                        news = future.result(timeout=5)
                        all_news.extend(news)
                    except:
                        pass
            except concurrent.futures.TimeoutError:
                # 超时时收集已完成的结果
                for future in futures:
                    if future.done():
                        try:
                            news = future.result(timeout=0)
                            all_news.extend(news)
                        except:
                            pass
        
        # 按时间排序
        all_news.sort(key=lambda x: x.published_at, reverse=True)
        return all_news
    
    def get_high_impact_news(self, hours: int = 24) -> List[NewsItem]:
        """获取高影响新闻"""
        all_news = self.fetch_all_sources(limit_per_source=15)
        cutoff = int(time.time()) - hours * 3600
        
        return [
            n for n in all_news 
            if n.impact == NewsImpact.HIGH and n.published_at > cutoff
        ]
    
    def _translate_to_chinese(self, text: str) -> str:
        """不做自动翻译，保持原文"""
        return text if text else ""
    
    def translate_with_ai(self, text: str, provider: str = "spark") -> Optional[str]:
        """使用 AI 翻译（用户手动触发）
        
        Args:
            text: 要翻译的文本
            provider: AI 提供商 (spark=讯飞星火, deepseek=DeepSeek)
        """
        if not text:
            return text
        
        # 检测是否主要是中文，无需翻译
        chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        if chinese_count / max(len(text), 1) > 0.3:
            return text
        
        try:
            from ai.ai_config_manager import get_ai_config_manager
            from ai.ai_providers import create_client
            
            config_mgr = get_ai_config_manager()
            config = config_mgr.get_ai_api_config(provider)
            
            if not config or not config.get('api_key'):
                return None
            
            client = create_client(provider, api_key=config['api_key'])
            
            result = client.chat(
                prompt=f"将以下加密货币新闻标题翻译成简洁流畅的中文，保留专有名词如BTC/ETH/SEC/ETF等，只输出翻译结果，不要任何解释：\n{text}",
                max_tokens=200,
                temperature=0.1
            )
            
            if result:
                result = result.strip().strip('"\'')
                return result if len(result) > 3 else None
            return None
            
        except Exception as e:
            print(f"[NewsFetcher] AI翻译失败: {e}")
            return None
    
    def _analyze_news_item(self, news: NewsItem):
        """分析新闻影响和情绪"""
        text = (news.title + " " + news.summary).lower()
        
        # 判断影响程度
        for keyword in self.HIGH_IMPACT_KEYWORDS:
            if keyword.lower() in text:
                news.impact = NewsImpact.HIGH
                news.keywords.append(keyword)
                break
        else:
            for keyword in self.MEDIUM_IMPACT_KEYWORDS:
                if keyword.lower() in text:
                    news.impact = NewsImpact.MEDIUM
                    news.keywords.append(keyword)
                    break
            else:
                news.impact = NewsImpact.LOW
        
        # 识别相关币种
        for coin, keywords in self.COIN_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in text:
                    if coin not in news.related_coins:
                        news.related_coins.append(coin)
                    break
        
        # 计算情绪分数
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw.lower() in text)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw.lower() in text)
        
        # 高影响新闻情绪分数加权
        weight = 1.5 if news.impact == NewsImpact.HIGH else 1.0
        
        if bullish_count > bearish_count:
            news.sentiment_score = min(100, int(bullish_count * 20 * weight))
        elif bearish_count > bullish_count:
            news.sentiment_score = max(-100, int(-bearish_count * 20 * weight))
        else:
            news.sentiment_score = 0
    
    def _parse_rss_date(self, date_str: str) -> int:
        """解析 RSS 日期"""
        if not date_str:
            return int(time.time())
        
        formats = [
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return int(dt.timestamp())
            except ValueError:
                continue
        
        return int(time.time())
    
    def _clean_html(self, text: str) -> str:
        """清理 HTML"""
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()


_news_fetcher: Optional[NewsFetcher] = None


def get_news_fetcher() -> NewsFetcher:
    """获取新闻获取器单例"""
    global _news_fetcher
    if _news_fetcher is None:
        _news_fetcher = NewsFetcher()
    return _news_fetcher


def get_latest_news(limit: int = 10) -> List[Dict[str, Any]]:
    """快捷函数：获取最新新闻"""
    fetcher = get_news_fetcher()
    news = fetcher.fetch_all_sources(limit_per_source=limit)
    return [n.to_dict() for n in news[:limit]]
