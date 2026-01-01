# -*- coding: utf-8 -*-
"""
市场情绪与新闻 UI 组件

金十数据风格的币圈新闻流 + 情绪分析面板
"""

import streamlit as st
import time
from datetime import datetime
from typing import Dict, Any, List, Optional


def render_sentiment_card():
    """渲染情绪分析卡片（嵌入式）"""
    st.markdown("#### ◇ 市场情绪")
    
    with st.expander("情绪分析 & 新闻 & 链上数据", expanded=False):
        tab1, tab2, tab3 = st.tabs(["◈ 情绪指数", "◈ 新闻流", "◈ 链上数据"])
        
        with tab1:
            _render_sentiment_tab()
        
        with tab2:
            _render_news_tab_fragment()
        
        with tab3:
            _render_onchain_tab_fragment()


def _render_sentiment_tab():
    """渲染情绪指数标签页"""
    from sentiment import get_fear_greed_index, get_market_impact
    
    fg_data = get_fear_greed_index()
    
    if fg_data:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("恐惧贪婪指数", fg_data["value"])
        with col2:
            st.metric("情绪水平", fg_data["classification"])
        
        value = fg_data["value"]
        _render_sentiment_bar(value)
        
        st.caption(f"(・ω・) {fg_data.get('suggestion', '')}")
    else:
        st.warning("(；ω；) 情绪数据获取失败")
    
    st.divider()
    
    st.markdown("##### 综合分析")
    try:
        impact = get_market_impact()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            score = impact.get("combined_score", 0)
            icon = "(≧▽≦)" if score > 20 else "(；ω；)" if score < -20 else "(・ω・)"
            st.metric("综合得分", f"{icon} {score}")
        with col2:
            bias = impact.get("combined_bias", "neutral")
            bias_cn = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性"}.get(bias, bias)
            st.metric("市场偏向", bias_cn)
        with col3:
            news_count = impact.get("news_sentiment", {}).get("news_count", 0)
            st.metric("新闻数量", news_count)
        
        key_events = impact.get("news_sentiment", {}).get("key_events", [])
        if key_events:
            st.markdown("**关键事件:**")
            for event in key_events[:3]:
                st.caption(f"• {event}")
    except Exception as e:
        st.error(f"(；ω；) 分析失败: {str(e)[:50]}")


@st.fragment
def _render_news_tab_fragment():
    """新闻流标签页 - fragment 局部刷新"""
    from sentiment import get_latest_news
    from sentiment.news_fetcher import get_news_fetcher
    
    # 检查可用的 AI 翻译服务
    available_providers = []
    try:
        from ai.ai_config_manager import get_ai_config_manager
        config_mgr = get_ai_config_manager()
        
        # 检查讯飞星火
        spark_config = config_mgr.get_ai_api_config("spark")
        if spark_config and spark_config.get('api_key'):
            available_providers.append(("spark", "讯飞星火"))
        
        # 检查 DeepSeek
        ds_config = config_mgr.get_ai_api_config("deepseek")
        if ds_config and ds_config.get('api_key'):
            available_providers.append(("deepseek", "DeepSeek"))
    except:
        pass
    
    # 初始化翻译状态
    if "news_translated" not in st.session_state:
        st.session_state.news_translated = False
    if "news_translations" not in st.session_state:
        st.session_state.news_translations = {}
    
    # 顶部工具栏
    if available_providers:
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            provider_options = {name: key for key, name in available_providers}
            selected_name = st.selectbox(
                "翻译服务",
                list(provider_options.keys()),
                key="translate_provider_select",
                label_visibility="collapsed"
            )
            selected_provider = provider_options[selected_name]
        
        with col2:
            translate_clicked = st.button("🌐 翻译全部", key="translate_all_btn", use_container_width=True)
        
        with col3:
            if st.button("↻", key="refresh_news_frag", use_container_width=True, help="刷新"):
                st.session_state.news_translated = False
                st.session_state.news_translations = {}
                st.cache_data.clear()
    else:
        col1, col2 = st.columns([4, 1])
        with col1:
            st.caption("(・ω・) 前往「AI竞技场」配置 AI API 后可翻译新闻")
        with col2:
            if st.button("↻", key="refresh_news_frag", use_container_width=True, help="刷新"):
                st.cache_data.clear()
        translate_clicked = False
        selected_provider = None
    
    load_key = "news_tab_load_count"
    if load_key not in st.session_state:
        st.session_state[load_key] = 8
    
    # 缓存 90 秒
    @st.cache_data(ttl=90, show_spinner=False)
    def fetch_news():
        return get_latest_news(limit=30)
    
    with st.spinner("加载中..."):
        news_list = fetch_news()
    
    if not news_list:
        st.info("(・ω・) 暂无新闻数据")
        return
    
    # 点击翻译按钮后立即翻译
    if translate_clicked and selected_provider:
        fetcher = get_news_fetcher()
        progress_bar = st.progress(0, text="正在翻译...")
        
        titles_to_translate = []
        for news in news_list:
            title = news.get("title", "")
            if title and title not in st.session_state.news_translations:
                # 检查是否已经是中文
                chinese_count = sum(1 for c in title if '\u4e00' <= c <= '\u9fff')
                if chinese_count / max(len(title), 1) < 0.3:
                    titles_to_translate.append(title)
        
        total = len(titles_to_translate)
        for i, title in enumerate(titles_to_translate):
            progress_bar.progress((i + 1) / max(total, 1), text=f"翻译中 ({i+1}/{total})...")
            translated = fetcher.translate_with_ai(title, selected_provider)
            if translated:
                st.session_state.news_translations[title] = translated
        
        progress_bar.empty()
        st.session_state.news_translated = True
    
    # 渲染新闻列表
    display_count = min(st.session_state[load_key], len(news_list))
    
    for news in news_list[:display_count]:
        # 应用翻译
        original_title = news.get("title", "")
        if original_title in st.session_state.news_translations:
            news = news.copy()
            news["title"] = st.session_state.news_translations[original_title]
        _render_news_card(news)
    
    # 加载更多
    if display_count < len(news_list):
        remaining = len(news_list) - display_count
        if st.button(f"加载更多 ({remaining})", key="load_more_news_frag", use_container_width=True):
            st.session_state[load_key] += 8


def _render_news_card(news: Dict[str, Any]):
    """渲染单条新闻卡片 - 使用 Streamlit 原生组件"""
    ts = news.get("published_at", 0)
    if ts:
        dt = datetime.fromtimestamp(ts)
        # 判断是否是今天
        today = datetime.now().date()
        if dt.date() == today:
            time_str = dt.strftime("%H:%M")  # 今天只显示时间
        else:
            time_str = dt.strftime("%m-%d %H:%M")  # 其他日期显示月-日 时:分
    else:
        time_str = "--:--"
    
    # 情绪分数决定显示
    score = news.get("sentiment_score", 0)
    if score >= 50:
        sentiment_text = "▲▲ 强烈利多"
        sentiment_color = "green"
    elif score >= 20:
        sentiment_text = "▲ 利多"
        sentiment_color = "green"
    elif score <= -50:
        sentiment_text = "▼▼ 强烈利空"
        sentiment_color = "red"
    elif score <= -20:
        sentiment_text = "▼ 利空"
        sentiment_color = "red"
    else:
        sentiment_text = "● 中性"
        sentiment_color = "gray"
    
    # 影响程度
    impact = news.get("impact", "low")
    if impact == "high":
        impact_badge = "🔴"
    elif impact == "medium":
        impact_badge = "🟡"
    else:
        impact_badge = "⚪"
    
    # 相关币种
    coins = news.get("related_coins", [])
    coins_str = " ".join([f"`{c}`" for c in coins[:3]]) if coins else ""
    
    # 来源
    source = news.get("source", "")
    source_map = {"CD": "CoinDesk", "CT": "CoinTelegraph", "DL": "Defiant", "BM": "Blockworks"}
    source_name = source_map.get(source, source)
    
    title = news.get("title", "")[:100]
    
    # 使用 Streamlit 原生渲染
    col_time, col_sentiment, col_impact = st.columns([1.5, 2, 1.5])
    with col_time:
        st.caption(f"🕐 {time_str}")
    with col_sentiment:
        st.markdown(f":{sentiment_color}[{sentiment_text}]")
    with col_impact:
        st.caption(f"{impact_badge} {source_name}")
    
    st.markdown(f"**{title}**")
    
    if coins_str:
        st.caption(f"{coins_str} · 情绪分 {'+' if score > 0 else ''}{score}")
    else:
        st.caption(f"情绪分 {'+' if score > 0 else ''}{score}")
    
    st.divider()


def _render_sentiment_bar(value: int):
    """渲染情绪条 - 使用 Streamlit progress"""
    if value <= 25:
        label = "极度恐惧 😱"
    elif value <= 45:
        label = "恐惧 😟"
    elif value <= 55:
        label = "中性 😐"
    elif value <= 75:
        label = "贪婪 😊"
    else:
        label = "极度贪婪 🤑"
    
    st.progress(value / 100, text=f"{label} ({value}/100)")


def render_sentiment_panel():
    """渲染完整情绪面板（独立页面用）"""
    from sentiment import get_fear_greed_index, get_market_impact
    
    st.markdown("## ◈ 市场情绪中心")
    st.caption("实时追踪市场情绪与重大新闻 (・ω・)")
    
    col1, col2, col3, col4 = st.columns(4)
    
    fg_data = get_fear_greed_index()
    impact = get_market_impact()
    
    with col1:
        if fg_data:
            st.metric("恐惧贪婪", fg_data["value"], delta=fg_data["classification"])
        else:
            st.metric("恐惧贪婪", "N/A")
    
    with col2:
        score = impact.get("combined_score", 0)
        st.metric("综合得分", score)
    
    with col3:
        bias = impact.get("combined_bias", "neutral")
        bias_cn = {"bullish": "↑ 偏多", "bearish": "↓ 偏空", "neutral": "→ 中性"}.get(bias, bias)
        st.metric("市场偏向", bias_cn)
    
    with col4:
        news_count = impact.get("news_sentiment", {}).get("news_count", 0)
        st.metric("新闻数量", f"{news_count} 条")
    
    st.divider()
    
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.markdown("### ◈ 新闻流")
        _render_news_stream_fragment()
    
    with right_col:
        st.markdown("### ◈ 情绪趋势")
        _render_sentiment_history()


@st.fragment
def _render_news_stream_fragment():
    """新闻流 - fragment 局部刷新"""
    from sentiment import get_latest_news
    
    # 筛选器 + 刷新按钮
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        impact_filter = st.selectbox(
            "影响程度",
            ["全部", "高影响", "中影响"],
            key="news_impact_filter"
        )
    with col2:
        coin_filter = st.selectbox(
            "相关币种",
            ["全部", "BTC", "ETH", "SOL", "其他"],
            key="news_coin_filter"
        )
    with col3:
        st.write("")
        if st.button("↻", key="refresh_stream_frag", help="刷新新闻", use_container_width=True):
            st.cache_data.clear()
    
    load_key = "stream_load_count"
    if load_key not in st.session_state:
        st.session_state[load_key] = 10
    
    @st.cache_data(ttl=90, show_spinner=False)
    def fetch_news():
        return get_latest_news(limit=30)
    
    news_list = fetch_news()
    
    # 筛选
    filtered = []
    for news in news_list:
        if impact_filter == "高影响" and news.get("impact") != "high":
            continue
        if impact_filter == "中影响" and news.get("impact") not in ["high", "medium"]:
            continue
        
        if coin_filter != "全部":
            coins = news.get("related_coins", [])
            if coin_filter == "其他":
                if any(c in coins for c in ["BTC", "ETH", "SOL"]):
                    continue
            elif coin_filter not in coins:
                continue
        
        filtered.append(news)
    
    if not filtered:
        st.info("(・ω・) 没有符合条件的新闻")
        return
    
    display_count = min(st.session_state[load_key], len(filtered))
    for news in filtered[:display_count]:
        _render_news_card(news)
    
    if display_count < len(filtered):
        remaining = len(filtered) - display_count
        if st.button(f"加载更多 ({remaining})", key="load_more_stream_frag", use_container_width=True):
            st.session_state[load_key] += 10


def _render_sentiment_history():
    """渲染情绪历史趋势"""
    from sentiment import get_sentiment_cache
    
    cache = get_sentiment_cache()
    history = cache.get_history(hours=24, limit=24)
    
    if not history:
        st.info("(・ω・) 暂无历史数据")
        return
    
    st.markdown("**最近24小时:**")
    
    for item in history[:8]:
        ts = item.get("timestamp", 0)
        dt = datetime.fromtimestamp(ts) if ts else None
        time_str = dt.strftime("%H:%M") if dt else "--:--"
        
        fg = item.get("fear_greed_value", 50)
        combined = item.get("combined_score", 0)
        bias = item.get("combined_bias", "neutral")
        
        bias_icon = {"bullish": "↑", "bearish": "↓", "neutral": "→"}.get(bias, "")
        
        st.caption(f"{time_str} | FG:{fg} | 综合:{combined} {bias_icon}")


def get_sentiment_for_ai() -> Dict[str, Any]:
    """获取情绪数据供 AI 交易员使用"""
    from sentiment import get_market_impact, get_fear_greed_index
    
    try:
        impact = get_market_impact()
        fg = get_fear_greed_index()
        
        return {
            "fear_greed_index": fg.get("value") if fg else None,
            "fear_greed_class": fg.get("classification") if fg else None,
            "combined_score": impact.get("combined_score", 0),
            "combined_bias": impact.get("combined_bias", "neutral"),
            "key_events": impact.get("news_sentiment", {}).get("key_events", []),
            "suggestion": impact.get("news_sentiment", {}).get("suggestion", ""),
            "timestamp": int(time.time())
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": int(time.time())
        }


@st.fragment
def _render_onchain_tab_fragment():
    """链上数据标签页 - fragment 局部刷新"""
    from sentiment import get_liquidation_data, get_whale_data
    
    if st.button("↻ 刷新", key="refresh_onchain_btn"):
        st.cache_data.clear()
    
    # === 多空比数据 ===
    st.markdown("##### ◈ BTC 多空比")
    
    @st.cache_data(ttl=120, show_spinner=False)
    def fetch_long_short():
        return get_liquidation_data()
    
    with st.spinner("加载中..."):
        ls_data = fetch_long_short()
    
    if ls_data and ls_data.get("total_24h", 0) > 0:
        btc_data = ls_data.get("btc")
        if btc_data:
            long_pct = btc_data.get("long_ratio", 0.5) * 100
            short_pct = 100 - long_pct
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("多头", f"{long_pct:.1f}%")
            with col2:
                st.metric("空头", f"{short_pct:.1f}%")
            with col3:
                bias = ls_data.get("bias", "neutral")
                bias_map = {"bullish": "(≧▽≦) 偏多", "bearish": "(；ω；) 偏空", "neutral": "(・ω・) 中性"}
                st.metric("信号", bias_map.get(bias, "中性"))
            
            # 解读
            if long_pct > 60:
                st.caption("(；ω；) 多头拥挤，注意回调风险")
            elif long_pct < 40:
                st.caption("(≧▽≦) 空头拥挤，可能反弹")
            else:
                st.caption("(・ω・) 多空均衡")
        
        st.caption("数据来源: Binance")
    else:
        st.info("(・ω・) 多空比数据暂不可用")
    
    st.divider()
    
    # === 巨鲸转账 ===
    st.markdown("##### ◈ BTC 大额转账")
    
    @st.cache_data(ttl=180, show_spinner=False)
    def fetch_whale():
        return get_whale_data()
    
    with st.spinner("加载中..."):
        whale_data = fetch_whale()
    
    if whale_data and whale_data.get("count", 0) > 0:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("转账数", whale_data["count"])
        with col2:
            total_usd = whale_data.get("total_usd", 0)
            if total_usd >= 1e9:
                st.metric("总额", f"${total_usd/1e9:.2f}B")
            else:
                st.metric("总额", f"${total_usd/1e6:.1f}M")
        
        # 转账列表
        transfers = whale_data.get("recent_transfers", [])
        if transfers:
            for t in transfers[:5]:
                coin = t.get("coin", "BTC")
                amount = t.get("amount", 0)
                amount_usd = t.get("amount_usd", 0)
                ts = t.get("timestamp", 0)
                time_str = datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "--:--"
                
                if amount_usd >= 1e9:
                    usd_str = f"${amount_usd/1e9:.2f}B"
                else:
                    usd_str = f"${amount_usd/1e6:.1f}M"
                
                st.caption(f"○ {time_str} | {coin} {amount:.2f} ({usd_str})")
    else:
        st.info("(・ω・) 暂无大额转账数据")
    
    st.caption("数据来源: Blockchain.com (最新区块)")
