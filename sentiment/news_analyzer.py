# -*- coding: utf-8 -*-
"""
新闻情绪分析模块

支持：
- 本地规则分析（关键词匹配）
- AI 深度分析（调用 DeepSeek/通义千问）
"""

import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .news_fetcher import NewsItem, NewsImpact, get_news_fetcher
from .sentiment_fetcher import get_fear_greed_index


@dataclass
class MarketImpact:
    """市场影响评估"""
    overall_score: int          # -100 到 +100
    bias: str                   # bullish / bearish / neutral
    confidence: float           # 0-1
    key_events: List[str]       # 关键事件摘要
    affected_coins: List[str]   # 受影响币种
    suggestion: str             # 交易建议


class NewsAnalyzer:
    """新闻分析器"""
    
    def __init__(self):
        self._ai_client = None
    
    def analyze_local(self, news_list: List[NewsItem]) -> MarketImpact:
        """本地规则分析（无需 AI）"""
        if not news_list:
            return MarketImpact(
                overall_score=0,
                bias="neutral",
                confidence=0.3,
                key_events=[],
                affected_coins=[],
                suggestion="暂无新闻数据"
            )
        
        # 计算加权情绪分数
        total_score = 0
        total_weight = 0
        key_events = []
        affected_coins = set()
        
        for news in news_list:
            # 高影响新闻权重更高
            weight = 3 if news.impact == NewsImpact.HIGH else 1
            total_score += news.sentiment_score * weight
            total_weight += weight
            
            # 收集关键事件
            if news.impact == NewsImpact.HIGH:
                key_events.append(news.title[:50])
            
            # 收集受影响币种
            affected_coins.update(news.related_coins)
        
        # 计算平均分
        avg_score = int(total_score / total_weight) if total_weight > 0 else 0
        
        # 确定偏向
        if avg_score > 20:
            bias = "bullish"
        elif avg_score < -20:
            bias = "bearish"
        else:
            bias = "neutral"
        
        # 生成建议
        suggestion = self._generate_suggestion(avg_score, key_events)
        
        return MarketImpact(
            overall_score=avg_score,
            bias=bias,
            confidence=min(0.8, len(news_list) * 0.1),
            key_events=key_events[:5],
            affected_coins=list(affected_coins),
            suggestion=suggestion
        )
    
    async def analyze_with_ai(self, news_list: List[NewsItem], ai_provider: str = "deepseek") -> MarketImpact:
        """使用 AI 深度分析"""
        # 先做本地分析
        local_result = self.analyze_local(news_list)
        
        if not news_list:
            return local_result
        
        try:
            from ai.ai_providers import get_provider, create_client
            
            provider = get_provider(ai_provider)
            if not provider:
                return local_result
            
            client = create_client(provider)
            if not client:
                return local_result
            
            # 构建 prompt
            news_text = "\n".join([
                f"- [{n.source}] {n.title}" 
                for n in news_list[:10]
            ])
            
            prompt = f"""分析以下加密货币新闻，给出市场影响评估：

{news_text}

请用 JSON 格式回复：
{{
    "overall_score": <-100到100的整数，正数利多负数利空>,
    "bias": "<bullish/bearish/neutral>",
    "confidence": <0-1的置信度>,
    "key_insight": "<一句话总结>",
    "suggestion": "<交易建议>"
}}"""
            
            response = await client.chat.completions.create(
                model=provider.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500
            )
            
            # 解析响应
            import json
            content = response.choices[0].message.content
            # 提取 JSON
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
                return MarketImpact(
                    overall_score=result.get("overall_score", local_result.overall_score),
                    bias=result.get("bias", local_result.bias),
                    confidence=result.get("confidence", 0.7),
                    key_events=local_result.key_events,
                    affected_coins=local_result.affected_coins,
                    suggestion=result.get("suggestion", local_result.suggestion)
                )
        except Exception as e:
            print(f"[NewsAnalyzer] AI 分析失败: {e}")
        
        return local_result
    
    def _generate_suggestion(self, score: int, key_events: List[str]) -> str:
        """生成交易建议"""
        if not key_events:
            return "市场平静，按策略执行"
        
        if score > 50:
            return "多条利好消息，可考虑加仓"
        elif score > 20:
            return "市场偏多，保持观望"
        elif score < -50:
            return "重大利空，建议减仓或观望"
        elif score < -20:
            return "市场偏空，谨慎操作"
        else:
            return "消息面中性，关注技术面"


# 全局单例
_analyzer: Optional[NewsAnalyzer] = None


def get_news_analyzer() -> NewsAnalyzer:
    """获取新闻分析器单例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = NewsAnalyzer()
    return _analyzer


def analyze_news_sentiment(limit: int = 20) -> Dict[str, Any]:
    """快捷函数：分析新闻情绪"""
    fetcher = get_news_fetcher()
    analyzer = get_news_analyzer()
    
    news = fetcher.fetch_all_sources(limit_per_source=limit)
    impact = analyzer.analyze_local(news)
    
    return {
        "overall_score": impact.overall_score,
        "bias": impact.bias,
        "confidence": impact.confidence,
        "key_events": impact.key_events,
        "affected_coins": impact.affected_coins,
        "suggestion": impact.suggestion,
        "news_count": len(news),
        "timestamp": int(time.time())
    }


def get_market_impact() -> Dict[str, Any]:
    """获取综合市场影响（情绪 + 新闻）"""
    # 获取恐惧贪婪指数
    fear_greed = get_fear_greed_index()
    
    # 获取新闻情绪
    news_sentiment = analyze_news_sentiment(limit=15)
    
    # 综合计算
    fg_score = fear_greed["value"] if fear_greed else 50
    news_score = news_sentiment["overall_score"]
    
    # 加权平均（恐惧贪婪 60%，新闻 40%）
    # 将 fear_greed 的 0-100 转换为 -100 到 +100
    fg_normalized = (fg_score - 50) * 2
    combined_score = int(fg_normalized * 0.6 + news_score * 0.4)
    
    # 确定综合偏向
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
        "timestamp": int(time.time())
    }
