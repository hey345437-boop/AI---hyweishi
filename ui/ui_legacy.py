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
# ============================================================================
"""
传统策略交易界面 - Streamlit UI
"""
import streamlit as st
import pandas as pd
import time
import requests
import os
from datetime import datetime

# K线图支持 - Lightweight Charts (TradingView 风格)
try:
    from streamlit_lightweight_charts import renderLightweightCharts
    HAS_LIGHTWEIGHT_CHARTS = True
except ImportError:
    HAS_LIGHTWEIGHT_CHARTS = False

# Plotly 回退
try:
    import plotly.graph_objects as go
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# 双通道信号系统支持
try:
    from beijing_time_converter import BeijingTimeConverter, DualChannelChartRenderer
    HAS_DUAL_CHANNEL = True
except ImportError:
    HAS_DUAL_CHANNEL = False

# 尝试导入 streamlit_autorefresh(可选依赖)
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# Run mode mappings (DB <-> UI)
# 统一使用 run_mode.py 中的定义
# 只保留两种模式: 实盘测试(读取实盘数据但不下单)和实盘(真实交易)
try:
    from core.run_mode import (
        RunMode, run_mode_to_display, run_mode_to_db, db_to_run_mode,
        RUN_MODE_DISPLAY, RUN_MODE_TO_DB, DB_TO_RUN_MODE
    )
    RUN_MODE_UI = [RUN_MODE_DISPLAY[RunMode.PAPER], RUN_MODE_DISPLAY[RunMode.LIVE]]
    RUN_MODE_UI_TO_DB = {v: k for k, v in RUN_MODE_DISPLAY.items()}
    RUN_MODE_UI_TO_DB = {RUN_MODE_DISPLAY[RunMode.PAPER]: "paper", RUN_MODE_DISPLAY[RunMode.LIVE]: "live"}
    RUN_MODE_DB_TO_UI = {v: k for k, v in RUN_MODE_UI_TO_DB.items()}
    # 兼容旧的sim和paper_on_real模式
    RUN_MODE_DB_TO_UI['sim'] = RUN_MODE_DISPLAY[RunMode.PAPER]
    RUN_MODE_DB_TO_UI['paper_on_real'] = RUN_MODE_DISPLAY[RunMode.PAPER]
except ImportError:
    # 回退到硬编码值
    RUN_MODE_UI = ["○ 测试", "● 实盘"]
    RUN_MODE_UI_TO_DB = {"○ 测试": "paper", "● 实盘": "live"}
    RUN_MODE_DB_TO_UI = {v: k for k, v in RUN_MODE_UI_TO_DB.items()}
    RUN_MODE_DB_TO_UI['sim'] = "○ 测试"
    RUN_MODE_DB_TO_UI['paper_on_real'] = "○ 测试"

# HTML 模板导入（保持代码整洁）
from ui.templates import (
    DISCLAIMER_STYLES, DISCLAIMER_CONTENT,
    ONBOARDING_STYLES, ONBOARDING_STEPS,
    CONTACT_FOOTER_HTML, MAIN_FOOTER_HTML,
    render_onboarding_step
)

# Market API
MARKET_API_URL = os.getenv("MARKET_API_URL", "http://127.0.0.1:8000")


def fetch_kline_from_api(symbol: str, timeframe: str, limit: int = 500, strategy_id: str = None) -> dict:
    """
    从 Market API 获取 K线数据（可选：附带策略信号标记）
    
    参数:
    - symbol: 交易对，如 "BTC/USDT:USDT"
    - timeframe: 时间周期，如 "1m", "5m"
    - limit: K线数量
    - strategy_id: 策略ID，如 "strategy_v1", "strategy_v2"（可选）
    
    返回:
    - {"ok": True, "data": [...], "markers": [...], "cached": True/False} 或 {"ok": False, "error": "..."}
    """
    try:
        url = f"{MARKET_API_URL}/kline"
        params = {"symbol": symbol, "tf": timeframe, "limit": limit}
        
        # 如果指定了策略，添加到请求参数
        if strategy_id:
            params["strategy"] = strategy_id
        
        response = requests.get(url, params=params, timeout=15)  # 增加超时时间（策略计算需要时间）
        
        if response.status_code == 200:
            result = response.json()
            return {
                "ok": True,
                "data": result.get("data", []),
                "markers": result.get("markers", []),  # 新增：策略信号标记
                "cached": result.get("cached", False),
                "count": result.get("count", 0)
            }
        else:
            return {"ok": False, "error": f"HTTP {response.status_code}"}
    except requests.exceptions.ConnectionError:
        return {"ok": False, "error": "行情服务未连接"}
    except requests.exceptions.Timeout:
        return {"ok": False, "error": "请求超时"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_market_api_status() -> bool:
    """检查 Market API 服务是否可用"""
    try:
        response = requests.get(f"{MARKET_API_URL}/", timeout=3)
        return response.status_code == 200
    except Exception:
        return False

# K线图专用缓存（与交易引擎隔离）
_UI_KLINE_CACHE = {}  # {(symbol, tf): {'data': [...], 'ts': timestamp}}
_UI_KLINE_CACHE_TTL = 10  # 10秒缓存

# WebSocket 客户端单例（UI 专用）
_UI_WS_CLIENT = None


def _get_ui_ws_client():
    """获取 UI 专用的 WebSocket 客户端"""
    global _UI_WS_CLIENT
    
    if _UI_WS_CLIENT is not None:
        return _UI_WS_CLIENT
    
    try:
        from exchange.okx_websocket import OKXWebSocketClient, is_ws_available
        if is_ws_available():
            _UI_WS_CLIENT = OKXWebSocketClient(use_aws=False)
            return _UI_WS_CLIENT
    except ImportError:
        pass
    
    return None


def _fetch_ohlcv_via_websocket(symbol: str, timeframe: str, limit: int = 500) -> list:
    """
     通过 WebSocket 获取 K线数据（UI 专用）
    
    特点：
    1. 实时推送，低延迟
    2. 自动订阅并缓存
    3. 数据不足时回退到 REST
    """
    ws_client = _get_ui_ws_client()
    if ws_client is None:
        return []
    
    # 确保连接
    if not ws_client.is_connected():
        if not ws_client.start():
            return []
    
    # 订阅（如果尚未订阅）
    ws_client.subscribe_candles(symbol, timeframe)
    
    # 获取缓存数据
    data = ws_client.get_candles(symbol, timeframe, limit)
    
    # 去掉最后一根正在形成的K线
    if data and len(data) > 1:
        return data[:-1]
    
    return data


def _fetch_ohlcv_for_chart(symbol: str, timeframe: str, limit: int = 500) -> list:
    """
     K线图专用数据获取（与交易引擎完全隔离）
    
    特点：
    1. 使用独立缓存字典 _UI_KLINE_CACHE
    2. 强制返回收盘K线（去掉最后一根正在形成的K线）
    3. 不影响交易引擎的数据
    4. 自动检测系统代理
    """
    import time as time_module
    from utils.candle_time_utils import normalize_daily_timeframe
    
    cache_key = (symbol, timeframe)
    now = time_module.time()
    
    # 检查缓存
    if cache_key in _UI_KLINE_CACHE:
        cached = _UI_KLINE_CACHE[cache_key]
        if now - cached['ts'] < _UI_KLINE_CACHE_TTL:
            return cached['data']
    
    # 日线格式转换
    actual_timeframe = normalize_daily_timeframe(timeframe)
    
    # 从交易所获取数据
    try:
        import ccxt
        from dotenv import load_dotenv
        load_dotenv()
        
        # 获取代理配置（优先环境变量，否则自动检测）
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        # 如果环境变量没有代理，自动检测系统代理
        if not http_proxy and not https_proxy:
            try:
                from utils.env_validator import EnvironmentValidator
                proxy_config = EnvironmentValidator.detect_system_proxy()
                http_proxy = proxy_config.get('http_proxy')
                https_proxy = proxy_config.get('https_proxy') or http_proxy
            except Exception:
                pass
        
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        }
        
        if https_proxy or http_proxy:
            config['proxies'] = {
                'http': http_proxy or https_proxy,
                'https': https_proxy or http_proxy
            }
        
        exchange = ccxt.okx(config)
        ohlcv = exchange.fetch_ohlcv(symbol, actual_timeframe, limit=limit + 1)  # 多拉一根
        
        # 强制去掉最后一根（正在形成的K线），只保留收盘K线
        if ohlcv and len(ohlcv) > 1:
            closed_ohlcv = ohlcv[:-1]
        else:
            closed_ohlcv = ohlcv
        
        # 更新缓存
        _UI_KLINE_CACHE[cache_key] = {
            'data': closed_ohlcv,
            'ts': now
        }
        
        return closed_ohlcv
    except Exception as e:
        # 静默处理错误，避免刷屏
        import logging
        logging.getLogger(__name__).debug(f"[_fetch_ohlcv_for_chart] Error: {e}")
        # 返回旧缓存（如果有）
        if cache_key in _UI_KLINE_CACHE:
            return _UI_KLINE_CACHE[cache_key]['data']
        return []


# 保留旧函数兼容性（但不再使用）
@st.cache_data(ttl=5)
def _fetch_ohlcv_direct(symbol: str, timeframe: str, limit: int = 500) -> list:
    """旧函数，保留兼容性，内部调用新函数"""
    return _fetch_ohlcv_for_chart(symbol, timeframe, limit)


# 实时数据获取
@st.cache_data(ttl=3)
def fetch_btc_ticker_cached():
    """获取 BTC 实时价格(3秒缓存)
    
    优先使用 Market API，回退到 CoinGecko
    """
    # 方案1: 尝试从 Market API 获取（更可靠）
    try:
        url = f"{MARKET_API_URL}/ticker"
        response = requests.get(url, params={"symbol": "BTC/USDT:USDT"}, timeout=3)
        if response.status_code == 200:
            data = response.json()
            price = data.get("last") or data.get("price")
            if price:
                return f"${float(price):,.2f}"
    except Exception:
        pass
    
    # 方案2: 回退到 CoinGecko API
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=5
        )
        data = response.json()
        btc_price = data.get("bitcoin", {}).get("usd")
        if btc_price:
            return f"${btc_price:,.2f}"
    except Exception:
        pass
    
    # 方案3: 从 K线图缓存中获取最新价格
    try:
        cache_key = ("BTC/USDT:USDT", "1m")
        if cache_key in _UI_KLINE_CACHE:
            ohlcv = _UI_KLINE_CACHE[cache_key].get('data', [])
            if ohlcv:
                last_close = ohlcv[-1][4]  # 最后一根K线的收盘价
                return f"${float(last_close):,.2f}"
    except Exception:
        pass
    
    return "----"


@st.cache_data(ttl=3)
def fetch_account_balance_cached(_actions_hash: str):
    """获取账户余额(3秒缓存)"""
    try:
        return {'equity': None, 'available': None, 'ts': int(time.time())}
    except Exception:
        return {'equity': None, 'available': None, 'ts': int(time.time())}


def clear_realtime_cache():
    """清除实时数据缓存(API 配置变更后调用)"""
    try:
        fetch_btc_ticker_cached.clear()
        fetch_account_balance_cached.clear()
    except Exception:
        pass


def plot_nofx_equity_curve(timestamps, equity_values, initial_equity=None):
    """
    NOFX 风格金色渐变资金曲线图表 + 专业级交互控制
    
    特点：
    1. 金色填充到0轴 (#F7D154)
    2. Y轴在右侧，虚线网格
    3. 透明背景
    4. 滚轮缩放 + 平移模式
    5. 底部 Rangeslider 缩放滑块
    6. 快捷时间按钮 (1H, 6H, 12H, 1D, All)
    """
    if not HAS_PLOTLY:
        st.warning("请安装 plotly: pip install plotly")
        return
    
    if not timestamps or not equity_values:
        st.info("暂无资金曲线数据")
        return
    
    fig = go.Figure()
    
    # 主曲线 - 金色填充到0轴
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=equity_values,
        mode='lines',
        name='净值',
        line=dict(color='#F7D154', width=2),
        fill='tozeroy',
        fillcolor='rgba(247, 209, 84, 0.1)',
    ))
    
    # 布局 - NOFX 极简风格 + 专业交互
    fig.update_layout(
        template='plotly_dark',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=0, r=0, t=40, b=10),
        height=350,
        showlegend=False,
        hovermode='x unified',
        dragmode='pan',  # 默认平移模式
        
        # X轴配置 - 带 Rangeslider 和快捷按钮
        xaxis=dict(
            showgrid=False,
            showline=False,
            tickformat='%m-%d %H:%M',
            # 底部缩放滑块
            rangeslider=dict(
                visible=True,
                thickness=0.08,
                bgcolor='rgba(30,30,30,0.5)',
                bordercolor='rgba(128,128,128,0.3)',
                borderwidth=1,
            ),
            # 快捷时间按钮
            rangeselector=dict(
                buttons=[
                    dict(count=1, label='1H', step='hour', stepmode='backward'),
                    dict(count=6, label='6H', step='hour', stepmode='backward'),
                    dict(count=12, label='12H', step='hour', stepmode='backward'),
                    dict(count=1, label='1D', step='day', stepmode='backward'),
                    dict(step='all', label='All'),
                ],
                bgcolor='rgba(40,40,40,0.8)',
                activecolor='#F7D154',
                bordercolor='rgba(128,128,128,0.3)',
                borderwidth=1,
                font=dict(color='white', size=11),
                x=0,
                y=1.12,
            ),
        ),
        
        # Y轴配置
        yaxis=dict(
            side='right',
            showgrid=True,
            gridcolor='rgba(128,128,128,0.2)',
            gridwidth=1,
            griddash='dot',
            tickprefix='$',
            fixedrange=False,  # 允许Y轴缩放
        ),
    )
    
    # 渲染图表 - 专业交互配置
    st.plotly_chart(fig, width="stretch", config={
        'scrollZoom': True,  # 滚轮缩放
        'displayModeBar': True,
        'displaylogo': False,  # 隐藏 Plotly logo
        'modeBarButtonsToRemove': [
            'lasso2d', 'select2d', 'autoScale2d',
            'hoverClosestCartesian', 'hoverCompareCartesian',
            'toggleSpikelines', 'zoom2d', 'zoomIn2d', 'zoomOut2d'
        ],
        'modeBarButtonsToAdd': [],
        # 只保留: 复位(resetScale2d) + 截图(toImage) + 平移(pan2d)
    })

# ACCESS_PASSWORD 从环境变量读取, 支持开发模式默认密码
from utils.env_validator import EnvironmentValidator

# 开源版本：无需密码验证
# _pwd_valid, _pwd_warning, ACCESS_PASSWORD = EnvironmentValidator.validate_access_password()
USING_DEV_PASSWORD = False


def render_login(view_model, actions):
    """渲染登录页面 - 开源版本（一键登录 + 免责声明）"""
    # 从数据库读取用户状态（持久化）
    bot_config = actions.get("get_bot_config", lambda: {})()
    db_disclaimer_accepted = bot_config.get("disclaimer_accepted", 0) == 1
    db_onboarding_completed = bot_config.get("onboarding_completed", 0) == 1
    
    # 同步到 session_state
    if db_disclaimer_accepted:
        st.session_state.disclaimer_accepted = True
    if db_onboarding_completed:
        st.session_state.onboarding_completed = True
    
    # 检查是否已同意免责声明
    if not st.session_state.get("disclaimer_accepted", False):
        _render_disclaimer_page(actions)
        return
    
    # 检查是否已完成引导
    if not st.session_state.get("onboarding_completed", False):
        _render_onboarding_page(actions)
        return
    
    # 已完成所有流程，自动登录
    if not st.session_state.get("logged_in", False):
        _auto_login(actions)


def _render_disclaimer_page(actions):
    """渲染免责声明页面"""
    st.markdown(DISCLAIMER_STYLES, unsafe_allow_html=True)
    
    st.markdown('<div class="login-icon">⚡</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-title">何以为势</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-subtitle">QUANTITATIVE TRADING SYSTEM</div>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        st.markdown(DISCLAIMER_CONTENT, unsafe_allow_html=True)
        
        agree = st.checkbox(
            "我已阅读并同意上述免责声明，了解交易风险并自愿承担",
            key="agree_disclaimer"
        )
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("(◕‿◕) 我已了解，继续", disabled=not agree, use_container_width=True):
            st.session_state.disclaimer_accepted = True
            # 持久化到数据库
            actions.get("update_bot_config", lambda **kw: None)(disclaimer_accepted=1)
            st.rerun()
        
        st.markdown(CONTACT_FOOTER_HTML, unsafe_allow_html=True)
    
    st.stop()


def _render_onboarding_page(actions):
    """渲染引导页面"""
    st.markdown(ONBOARDING_STYLES, unsafe_allow_html=True)
    
    st.markdown('<div style="text-align:center; font-size:48px; margin-bottom:10px;">🚀</div>', unsafe_allow_html=True)
    st.markdown('<h2 style="text-align:center; color:#ff6b9d; margin-bottom:30px;">欢迎使用何以为势</h2>', unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([1, 3, 1])
    with c2:
        for step in ONBOARDING_STEPS:
            st.markdown(render_onboarding_step(step), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        if st.button("(≧▽≦) 开始使用", use_container_width=True):
            st.session_state.onboarding_completed = True
            # 持久化到数据库
            actions.get("update_bot_config", lambda **kw: None)(onboarding_completed=1)
            st.rerun()
        
        st.markdown(CONTACT_FOOTER_HTML, unsafe_allow_html=True)
    
    st.stop()


def _auto_login(actions):
    """自动登录（无需密码）"""
    st.session_state.logged_in = True
    st.session_state.username = "user"
    st.session_state.login_time = time.time()
    
    # 从数据库加载配置
    bot_config = actions.get("get_bot_config", lambda: {})()
    
    # 转换run_mode为UI显示模式
    run_mode_map = {
        "live": "● 实盘",
        "paper": "○ 测试",
        "sim": "○ 测试"
    }
    
    # 设置session_state
    st.session_state.trading_active = bot_config.get("enable_trading", 0) == 1
    st.session_state.auto_symbols = bot_config.get("symbols", "").split(",") if bot_config.get("symbols") else []
    st.session_state.open_positions = {}
    st.session_state.hedge_positions = {}
    st.session_state.env_mode = run_mode_map.get(bot_config.get("run_mode", "sim"), "○ 测试")
    st.session_state.strategy_module = "strategy_v2"
    st.session_state.position_sizes = {
        "primary": bot_config.get("position_size", 0.05), 
        "secondary": bot_config.get("position_size", 0.05) / 2
    }
    
    # 设置入场动画标志
    st.session_state.show_intro_animation = True
    st.rerun()


# 联系方式签名（使用模板）
CONTACT_FOOTER = MAIN_FOOTER_HTML


def render_contact_footer():
    """渲染联系方式签名（在主界面角落）"""
    st.markdown(MAIN_FOOTER_HTML, unsafe_allow_html=True)


def _render_advanced_strategy_config(strategy_id: str, actions):
    """渲染高级策略配置面板（动态止盈止损、时间过滤等）"""
    from strategies.strategy_registry import get_strategy_risk_config, get_strategy_registry
    
    # 获取保存的配置
    saved_config = get_strategy_risk_config(strategy_id) or {}
    
    # 初始化 session_state 中的配置
    config_key = f"advanced_config_{strategy_id}"
    if config_key not in st.session_state:
        st.session_state[config_key] = saved_config.copy()
    
    current_config = st.session_state[config_key]
    
    with st.expander("🎯 高级策略参数（动态止盈止损）", expanded=False):
        st.caption("💡 高级策略支持 ATR 动态止损、分批止盈、追踪止损、时间过滤等功能")
        
        # 风控参数
        st.markdown("##### 🛡️ 风控参数")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            risk_per_trade = st.number_input(
                "单笔风险比例",
                min_value=0.001,
                max_value=0.05,
                value=float(current_config.get('risk_per_trade', 0.008)),
                step=0.001,
                format="%.3f",
                help="每笔交易最大风险占账户权益的比例",
                key=f"adv_risk_{strategy_id}"
            )
        
        with col2:
            max_leverage = st.number_input(
                "最大杠杆",
                min_value=1,
                max_value=20,
                value=int(current_config.get('max_leverage', 5)),
                step=1,
                help="正常情况下的最大杠杆倍数",
                key=f"adv_lev_{strategy_id}"
            )
        
        with col3:
            high_vol_leverage = st.number_input(
                "高波动杠杆",
                min_value=1,
                max_value=10,
                value=int(current_config.get('high_volatility_leverage', 2)),
                step=1,
                help="高波动时自动降低到此杠杆",
                key=f"adv_hvlev_{strategy_id}"
            )
        
        col4, col5 = st.columns(2)
        with col4:
            atr_sl_mult = st.number_input(
                "ATR止损倍数",
                min_value=1.0,
                max_value=5.0,
                value=float(current_config.get('atr_sl_multiplier', 2.2)),
                step=0.1,
                help="止损距离 = ATR × 此倍数",
                key=f"adv_atrsl_{strategy_id}"
            )
        
        # 止盈止损参数
        st.markdown("##### 📊 分批止盈参数")
        col_tp1, col_tp2, col_tp3 = st.columns(3)
        
        with col_tp1:
            tp1_r = st.number_input(
                "TP1 R倍数",
                min_value=0.5,
                max_value=3.0,
                value=float(current_config.get('tp1_r_multiple', 1.0)),
                step=0.1,
                help="第一止盈目标的R倍数",
                key=f"adv_tp1r_{strategy_id}"
            )
            tp1_pct = st.number_input(
                "TP1 平仓比例",
                min_value=0.1,
                max_value=0.5,
                value=float(current_config.get('tp1_close_pct', 0.30)),
                step=0.05,
                help="TP1触发时平仓的比例",
                key=f"adv_tp1pct_{strategy_id}"
            )
        
        with col_tp2:
            tp2_r = st.number_input(
                "TP2 R倍数",
                min_value=1.0,
                max_value=5.0,
                value=float(current_config.get('tp2_r_multiple', 2.0)),
                step=0.1,
                help="第二止盈目标的R倍数",
                key=f"adv_tp2r_{strategy_id}"
            )
            tp2_pct = st.number_input(
                "TP2 平仓比例",
                min_value=0.1,
                max_value=0.5,
                value=float(current_config.get('tp2_close_pct', 0.30)),
                step=0.05,
                help="TP2触发时平仓的比例",
                key=f"adv_tp2pct_{strategy_id}"
            )
        
        with col_tp3:
            tp3_trail = st.number_input(
                "追踪止损ATR倍数",
                min_value=1.0,
                max_value=4.0,
                value=float(current_config.get('tp3_trailing_atr', 2.0)),
                step=0.1,
                help="TP2后追踪止损距离 = ATR × 此倍数",
                key=f"adv_tp3trail_{strategy_id}"
            )
        
        # 时间过滤参数
        st.markdown("##### 🕐 时间过滤（UTC）")
        
        enable_time_filter = st.checkbox(
            "启用时间过滤",
            value=current_config.get('enable_time_filter', True),
            help="是否启用交易时段过滤",
            key=f"adv_timefilt_{strategy_id}"
        )
        
        if enable_time_filter:
            st.caption("北京时间 = UTC + 8 小时")
            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
            
            with col_t1:
                t1_start = st.number_input(
                    "时段1开始",
                    min_value=0,
                    max_value=23,
                    value=int(current_config.get('trading_start_hour_1', 0)),
                    key=f"adv_t1s_{strategy_id}"
                )
            with col_t2:
                t1_end = st.number_input(
                    "时段1结束",
                    min_value=0,
                    max_value=24,
                    value=int(current_config.get('trading_end_hour_1', 8)),
                    key=f"adv_t1e_{strategy_id}"
                )
            with col_t3:
                t2_start = st.number_input(
                    "时段2开始",
                    min_value=0,
                    max_value=23,
                    value=int(current_config.get('trading_start_hour_2', 12)),
                    key=f"adv_t2s_{strategy_id}"
                )
            with col_t4:
                t2_end = st.number_input(
                    "时段2结束",
                    min_value=0,
                    max_value=24,
                    value=int(current_config.get('trading_end_hour_2', 20)),
                    key=f"adv_t2e_{strategy_id}"
                )
        else:
            t1_start, t1_end, t2_start, t2_end = 0, 24, 0, 0
        
        # 冷却参数
        st.markdown("##### ⏱️ 冷却参数")
        col_cd1, col_cd2 = st.columns(2)
        
        with col_cd1:
            cooldown_bars = st.number_input(
                "入场冷却K线数",
                min_value=1,
                max_value=10,
                value=int(current_config.get('cooldown_bars', 3)),
                help="入场后禁止加仓的K线数",
                key=f"adv_cd_{strategy_id}"
            )
        
        with col_cd2:
            post_sl_cooldown = st.number_input(
                "止损后冷却K线数",
                min_value=5,
                max_value=20,
                value=int(current_config.get('post_sl_cooldown', 10)),
                help="止损后需要更强信号的K线数",
                key=f"adv_slcd_{strategy_id}"
            )
        
        # 保存按钮
        if st.button("💾 保存高级策略参数", key=f"save_adv_{strategy_id}"):
            new_config = {
                'risk_per_trade': risk_per_trade,
                'max_leverage': max_leverage,
                'high_volatility_leverage': high_vol_leverage,
                'atr_sl_multiplier': atr_sl_mult,
                'tp1_r_multiple': tp1_r,
                'tp1_close_pct': tp1_pct,
                'tp2_r_multiple': tp2_r,
                'tp2_close_pct': tp2_pct,
                'tp3_trailing_atr': tp3_trail,
                'enable_time_filter': enable_time_filter,
                'trading_start_hour_1': t1_start,
                'trading_end_hour_1': t1_end,
                'trading_start_hour_2': t2_start,
                'trading_end_hour_2': t2_end,
                'cooldown_bars': cooldown_bars,
                'post_sl_cooldown': post_sl_cooldown,
            }
            
            # 保存到 manifest.json
            try:
                import os
                import json
                strategies_dir = os.path.join(os.path.dirname(__file__), 'strategies')
                manifest_path = os.path.join(strategies_dir, strategy_id, 'manifest.json')
                
                if os.path.isfile(manifest_path):
                    with open(manifest_path, 'r', encoding='utf-8') as f:
                        manifest = json.load(f)
                    
                    manifest['risk_config'] = new_config
                    
                    with open(manifest_path, 'w', encoding='utf-8') as f:
                        json.dump(manifest, f, ensure_ascii=False, indent=2)
                    
                    # 更新 session_state
                    st.session_state[config_key] = new_config
                    
                    # 刷新策略注册表
                    from strategies.strategy_registry import get_strategy_registry
                    # 强制重新加载
                    import strategies.strategy_registry as strategy_registry
                    strategy_registry._registry_instance = None
                    get_strategy_registry()
                    
                    st.success("(≧▽≦) 高级策略参数已保存！")
                else:
                    st.error(f"找不到策略配置文件: {manifest_path}")
            except Exception as e:
                st.error(f"保存失败: {str(e)}")


@st.fragment(run_every=5)
def _render_sidebar_balance_fragment(actions, view_model):
    """
     侧边栏余额 Fragment - 每5秒自动刷新
    
    使用 @st.fragment(run_every=5) 实现局部自动刷新
    只刷新余额显示，不影响其他组件
    """
    # 根据运行模式显示不同的余额
    current_env_mode = st.session_state.get('env_mode', '● 实盘')
    
    if current_env_mode == "○ 测试":
        # 实盘测试模式: 从数据库读取模拟账户余额
        try:
            paper_balance = actions.get("get_paper_balance", lambda: {})()
            if paper_balance and paper_balance.get('equity'):
                equity_val = paper_balance.get('equity', 10000)
                equity = f"${equity_val:,.2f}"
                # 计算浮动盈亏
                wallet_balance = paper_balance.get('wallet_balance', 0) or 0
                unrealized_pnl = paper_balance.get('unrealized_pnl', 0) or 0
                if wallet_balance > 0 and unrealized_pnl != 0:
                    pnl_pct = (unrealized_pnl / wallet_balance) * 100
                    delta_str = f"{unrealized_pnl:+.2f} ({pnl_pct:+.1f}%)"
                else:
                    delta_str = None
            else:
                equity_val = 10000.0
                equity = "$10,000.00"
                delta_str = None
        except Exception:
            equity_val = 10000.0
            equity = "$10,000.00"
            delta_str = None
        
        st.metric("模拟净值(USDT)", equity, delta=delta_str)
        st.caption("📌 模拟账户余额(非真实资金)")
    else:
        # 实盘模式: 显示 OKX 真实余额
        live_balance = st.session_state.get('live_balance', {})
        if live_balance and live_balance.get('equity'):
            equity = f"${live_balance.get('equity', 0):,.2f}"
        else:
            equity = view_model.get("equity", "----")
        
        st.metric("账户净值(USDT)", equity)
        st.caption(" OKX 真实账户余额")


def render_sidebar(view_model, actions):
    """渲染侧边栏"""
    with st.sidebar:
        # 系统标题
        st.markdown("""
        <style>
        @keyframes glow-pulse {
            0%, 100% { text-shadow: 0 0 10px #667eea, 0 0 20px #667eea, 0 0 30px #764ba2, 0 0 40px #764ba2; }
            50% { text-shadow: 0 0 20px #667eea, 0 0 30px #667eea, 0 0 40px #764ba2, 0 0 50px #764ba2, 0 0 60px #f093fb; }
        }
        .glow-title {
            font-size: 22px;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            animation: glow-pulse 3s ease-in-out infinite;
            letter-spacing: 2px;
        }
        </style>
        <div style="
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px 8px;
            margin-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        ">
            <div class="glow-title">何以为势</div>
            <div style="color: #718096; font-size: 11px; margin-top: 4px; letter-spacing: 1px;">Quantitative Trading System</div>
        </div>
        <div style="text-align: center; font-size: 10px; color: rgba(255,255,255,0.4); margin-bottom: 12px; line-height: 1.5;">
            📧 hey345437@gmail.com | QQ: 3269180865<br>
            ⚠️ 投资有风险，入市需谨慎 | AGPL-3.0
        </div>
        """, unsafe_allow_html=True)
        
        # 后端状态
        engine_status = view_model.get("engine_status", {})
        runner_alive = engine_status.get("alive", 0) == 1
        status_color = "#48bb78" if runner_alive else "#f56565"
        status_text = "🟢 后端在线" if runner_alive else "🔴 后端离线"
        st.markdown(f"""
        <div style="
            display: flex;
            align-items: center;
            padding: 8px 12px;
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            margin-bottom: 15px;
        ">
            <div style="
                width: 8px;
                height: 8px;
                background: {status_color};
                border-radius: 50%;
                margin-right: 10px;
                box-shadow: 0 0 10px {status_color};
            "></div>
            <span style="color: {status_color}; font-size: 13px; font-weight: 500;">{status_text}</span>
        </div>
        """, unsafe_allow_html=True)
        
        # AI 决策交易模式切换
        arena_mode = st.session_state.get('arena_mode', False)
        
        st.markdown("""
        <style>
        .ai-arena-btn {
            background: linear-gradient(135deg, #ff6b9d 0%, #c44569 50%, #ff6b9d 100%);
            background-size: 200% 200%;
            animation: pinkGradient 3s ease infinite;
            border: none;
            border-radius: 12px;
            padding: 12px 16px;
            margin-bottom: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(255, 107, 157, 0.4);
        }
        .ai-arena-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 25px rgba(255, 107, 157, 0.6);
        }
        @keyframes pinkGradient {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        .ai-arena-btn-text {
            color: white;
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 1px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        .ai-arena-btn-icon {
            font-size: 18px;
        }
        .ai-arena-btn.active {
            background: linear-gradient(135deg, #00d4aa 0%, #00b894 50%, #00d4aa 100%);
            box-shadow: 0 4px 20px rgba(0, 212, 170, 0.4);
        }
        .ai-arena-btn.active:hover {
            box-shadow: 0 6px 25px rgba(0, 212, 170, 0.6);
        }
        </style>
        """, unsafe_allow_html=True)
        
        btn_key = "ai_arena_switch_btn"
        
        if st.button("AI 决策交易", key=btn_key, width="stretch", type="primary"):
            st.session_state.arena_mode = True
            st.rerun()
        
        st.markdown("""
        <div style="
            text-align: center;
            margin-top: -8px;
            margin-bottom: 12px;
        ">
            <span style="color: #718096; font-size: 11px;">点击后切换为 AI 交易</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 资产概览
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 10px 16px;
            border-radius: 10px;
            margin-bottom: 12px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <span style="color: white; font-size: 16px; font-weight: 600;">✦ 资产看板</span>
        </div>
        """, unsafe_allow_html=True)
        
        _render_sidebar_balance_fragment(actions, view_model)
        
        if "strategy_module" not in st.session_state:
            st.session_state.strategy_module = "strategy"
        if "env_mode" not in st.session_state:
            st.session_state.env_mode = "● 实盘"
        
        # 环境模式切换(session_state.env_mode 为 UI 缓存, DB 为权威)
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(17, 153, 142, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">◈ 运行模式</span>
        </div>
        """, unsafe_allow_html=True)
        
        # P0修复: 实盘模式二次确认状态
        if "live_mode_confirm_pending" not in st.session_state:
            st.session_state.live_mode_confirm_pending = False

        def _execute_mode_change(run_mode_db: str, sel: str):
            """实际执行模式切换"""
            db_write_success = False
            try:
                current_config = actions.get("get_bot_config", lambda: {})()
                current_version = current_config.get('version', 1)
                actions.get("update_bot_config", lambda **kw: None)(
                    run_mode=run_mode_db,
                    enable_trading=0,
                    version=current_version + 1
                )
                actions.get("set_control_flags", lambda **kw: None)(
                    reload_config=1,
                    pause_trading=1
                )
                db_write_success = True
            except Exception:
                pass
            
            if db_write_success:
                st.session_state.trading_active = False
                try:
                    cred = actions.get('get_credentials_status', lambda: {})()
                    if cred.get('okx_bound'):
                        verify_result = actions.get('verify_credentials_and_snapshot', lambda **kw: {'ok': False})()
                        if verify_result.get('ok'):
                            summary = verify_result.get('account_summary', {})
                            balance = summary.get('balance', {})
                            total_usdt = balance.get('total', {}).get('USDT', 0) if isinstance(balance, dict) else 0
                            free_usdt = balance.get('free', {}).get('USDT', 0) if isinstance(balance, dict) else 0
                            st.session_state.live_balance = {
                                'equity': total_usdt,
                                'available': free_usdt
                            }
                except Exception:
                    pass
                st.session_state.env_mode = sel

        def _on_env_mode_change():
            """运行模式切换回调 - P0修复: 实盘模式需要二次确认"""
            sel = st.session_state.get('env_mode_selector')
            run_mode_db = RUN_MODE_UI_TO_DB.get(sel, 'paper')
            
            # P0修复: 切换到实盘模式需要二次确认
            if run_mode_db == 'live' and st.session_state.env_mode != "● 实盘":
                st.session_state.live_mode_confirm_pending = True
                st.session_state.pending_live_mode_sel = sel
                return  # 不立即执行, 等待确认
            
            # 非实盘模式直接执行
            _execute_mode_change(run_mode_db, sel)

        # selectbox 使用 key + on_change 回调
        st.selectbox(
            "运行模式",
            RUN_MODE_UI,
            index=RUN_MODE_UI.index(st.session_state.env_mode) if st.session_state.env_mode in RUN_MODE_UI else 0,
            key='env_mode_selector',
            on_change=_on_env_mode_change,
            label_visibility="collapsed"
        )

        env_cfg = actions.get("get_env_config", lambda m: {"api_source": "live", "is_sandbox": False})(st.session_state.env_mode)
        
        # P0修复: 实盘模式二次确认弹窗
        if st.session_state.get('live_mode_confirm_pending', False):
            st.warning("⚠️ **警告: 您正在切换到实盘模式!**")
            st.error("实盘模式下所有交易将使用真实资金执行, 可能造成资金损失!")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("⚠️ 确认切换到实盘", type="primary", width="stretch"):
                    sel = st.session_state.get('pending_live_mode_sel', "● 实盘")
                    _execute_mode_change('live', sel)
                    st.session_state.live_mode_confirm_pending = False
                    st.success("✅ 已切换到实盘模式")
                    time.sleep(0.5)
                    st.rerun()
            with col_cancel:
                if st.button("❌ 取消", width="stretch"):
                    st.session_state.live_mode_confirm_pending = False
                    st.info("已取消切换")
                    st.rerun()
        
        # P2-8修复: 明确说明运行模式
        if st.session_state.env_mode == "○ 测试":
            st.caption("读取真实行情, 但不会真实下单")
        elif st.session_state.env_mode == "● 实盘":
            st.caption("⚠️ 实盘模式: 所有交易将真实执行")
        
        # 显示 OKX_SANDBOX 环境变量状态(帮助用户理解配置)
        okx_sandbox = os.getenv('OKX_SANDBOX', 'false').lower() == 'true'
        if okx_sandbox:
            st.warning("⚠️ 当前 OKX_SANDBOX=true, 使用 OKX 模拟盘 API(非真实资金)")
        
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">◇ 策略切换</span>
        </div>
        """, unsafe_allow_html=True)
        # 获取所有可用策略((display_name, strategy_id) 元组)
        strategy_options = view_model.get("strategy_options", [("默认策略", "strategy_default")])
        strategy_ids = [opt[1] for opt in strategy_options]  # 按顺序的 strategy_id 列表
        
        # 当前会话中的 strategy_id(来自 DB bootstrap)
        current_strategy_id = st.session_state.get('selected_strategy_id', strategy_ids[0] if strategy_ids else 'strategy_default')
        
        # 如果当前 strategy_id 无效则回退到第一个
        if current_strategy_id not in strategy_ids:
            current_strategy_id = strategy_ids[0] if strategy_ids else 'strategy_default'
            st.session_state.selected_strategy_id = current_strategy_id
        
        # 找到当前 strategy_id 的索引
        try:
            current_idx = strategy_ids.index(current_strategy_id)
        except ValueError:
            current_idx = 0
        
        def _on_strategy_change():
            """
            用户切换策略时的回调 - P2-10修复: 并发安全
            
            设计原则: DB 为 SSOT, 先写 DB 再更新 session_state
            """
            sel_tuple = st.session_state.get('strategy_selectbox')
            if sel_tuple:
                # selectbox 返回的是元组 (display_name, strategy_id)
                sel_strategy_id = sel_tuple[1] if isinstance(sel_tuple, tuple) else sel_tuple
                if sel_strategy_id != st.session_state.get('selected_strategy_id'):
                    # P2-10: 先写 DB(SSOT)
                    db_write_success = False
                    try:
                        actions.get("update_bot_config", lambda **kw: None)(selected_strategy_id=sel_strategy_id)
                        actions.get("set_control_flags", lambda **kw: None)(reload_config=1)
                        db_write_success = True
                    except Exception:
                        pass
                    
                    # P2-10: 只有 DB 写入成功后才更新 session_state
                    if db_write_success:
                        st.session_state.selected_strategy_id = sel_strategy_id
                    # 注意: 不要在回调中调用 st.rerun(), Streamlit 会自动刷新
        
        # selectbox 使用稳定 strategy_id, 不用下拉索引
        selected_strategy_tuple = st.selectbox(
            "策略选择",
            strategy_options,
            index=current_idx,
            key='strategy_selectbox',
            format_func=lambda x: x[0],
            on_change=_on_strategy_change,
            label_visibility="collapsed"
        )
        # 同步 session_state(为了兼容其他代码访问 strategy_module)
        if selected_strategy_tuple[1] != st.session_state.get('selected_strategy_id'):
            st.session_state.selected_strategy_id = selected_strategy_tuple[1]
        
        # AI 策略助手入口 / 返回按钮
        if st.session_state.get('strategy_builder_mode', False):
            # 当前在策略助手模式，显示返回按钮
            if st.button("← 返回主界面", key="sidebar_back_to_main", use_container_width=True, type="primary"):
                st.session_state.strategy_builder_mode = False
                st.rerun()
        else:
            # 正常模式，显示进入策略助手按钮
            if st.button("◈ AI 策略助手", key="strategy_builder_btn", use_container_width=True):
                st.session_state.strategy_builder_mode = True
                st.rerun()
        
        # 双 Key API 配置面板
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(250, 112, 154, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">⬡ API 密钥</span>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            from core.config_manager import get_config_manager, save_api_credentials, get_api_status, mask_key
            config_mgr = get_config_manager()
            api_status = get_api_status()
            HAS_CONFIG_MANAGER = True
        except ImportError:
            HAS_CONFIG_MANAGER = False
            api_status = {}
        
        with st.expander("API 密钥配置（双 Key 机制）", expanded=False):
            if not HAS_CONFIG_MANAGER:
                st.error("❌ config_manager 模块未找到")
            else:
                st.markdown("##### 当前配置状态")
                col_trade, col_market = st.columns(2)
                
                with col_trade:
                    if api_status.get('has_trade_key'):
                        st.success(f"✅ 交易 Key: ****{api_status.get('trade_key_tail', '')}")
                    else:
                        st.warning("⚠️ 交易 Key: 未配置")
                
                with col_market:
                    if api_status.get('has_market_key'):
                        st.success(f"✅ 行情 Key: ****{api_status.get('market_key_tail', '')}")
                    else:
                        st.info("ℹ️ 行情 Key: 未配置（使用交易 Key）")
                
                if api_status.get('updated_at') and api_status.get('updated_at') != 'from_env':
                    st.caption(f"📅 上次更新: {api_status.get('updated_at', '')[:19]}")
                elif api_status.get('source') == 'env':
                    st.caption("📁 配置来源: 环境变量")
                
                st.divider()
                
                # 交易专用 Key
                st.markdown("##### 交易专用 Key（用于下单）")
                st.caption("需要交易权限，用于策略下单、撤单、查询持仓")
                
                trade_key = st.text_input(
                    "Trade API Key",
                    key='ui_trade_key_input',
                    type='password',
                    placeholder="输入交易 API Key（留空则不更新）"
                )
                trade_secret = st.text_input(
                    "Trade API Secret",
                    key='ui_trade_secret_input',
                    type='password',
                    placeholder="输入交易 API Secret（留空则不更新）"
                )
                trade_passphrase = st.text_input(
                    "Trade API Passphrase",
                    key='ui_trade_passphrase_input',
                    type='password',
                    placeholder="输入交易 API Passphrase（留空则不更新）"
                )
                
                st.divider()
                
                # 行情专用 Key
                st.markdown("##### 📈 行情专用 Key（可选，推荐）")
                st.caption("建议只读权限，用于 K线图、实时行情，与交易接口隔离避免 Rate Limit 冲突")
                
                market_key = st.text_input(
                    "Market API Key",
                    key='ui_market_key_input',
                    type='password',
                    placeholder="输入行情 API Key（可选，留空则使用交易 Key）"
                )
                market_secret = st.text_input(
                    "Market API Secret",
                    key='ui_market_secret_input',
                    type='password',
                    placeholder="输入行情 API Secret（可选）"
                )
                market_passphrase = st.text_input(
                    "Market API Passphrase",
                    key='ui_market_passphrase_input',
                    type='password',
                    placeholder="输入行情 API Passphrase（可选）"
                )
                
                st.divider()
                
                # 保存按钮
                def _save_dual_key_config():
                    """保存双 Key 配置"""
                    t_key = st.session_state.get('ui_trade_key_input', '')
                    t_secret = st.session_state.get('ui_trade_secret_input', '')
                    t_pass = st.session_state.get('ui_trade_passphrase_input', '')
                    m_key = st.session_state.get('ui_market_key_input', '')
                    m_secret = st.session_state.get('ui_market_secret_input', '')
                    m_pass = st.session_state.get('ui_market_passphrase_input', '')
                    
                    has_trade_input = bool(t_key or t_secret or t_pass)
                    has_market_input = bool(m_key or m_secret or m_pass)
                    
                    if not has_trade_input and not has_market_input:
                        st.session_state._dual_key_save_empty = True
                        return
                    
                    try:
                        success = save_api_credentials(
                            trade_key=t_key if t_key else None,
                            trade_secret=t_secret if t_secret else None,
                            trade_passphrase=t_pass if t_pass else None,
                            market_key=m_key if m_key else None,
                            market_secret=m_secret if m_secret else None,
                            market_passphrase=m_pass if m_pass else None
                        )
                        
                        if success:
                            st.session_state._dual_key_save_success = True
                            if t_key:
                                actions.get("update_bot_config", lambda **kw: None)(okx_api_key=t_key)
                            if t_secret:
                                actions.get("update_bot_config", lambda **kw: None)(okx_api_secret=t_secret)
                            if t_pass:
                                actions.get("update_bot_config", lambda **kw: None)(okx_api_passphrase=t_pass)
                            actions.get("set_control_flags", lambda **kw: None)(reload_config=1)
                        else:
                            st.session_state._dual_key_save_error = "保存失败"
                    except Exception as e:
                        st.session_state._dual_key_save_error = str(e)[:60]
                
                col_save, col_clear = st.columns([3, 1])
                with col_save:
                    st.button("💾 保存 API 配置", key="save_dual_key_btn", 
                              on_click=_save_dual_key_config)
                with col_clear:
                    if st.button("🗑️", key="clear_key_btn", help="清除已保存的配置"):
                        config_mgr.clear_credentials()
                        st.success("已清除保存的配置")
                        time.sleep(0.5)
                        st.rerun()
                
                # 处理保存结果
                if st.session_state.pop('_dual_key_save_success', False):
                    st.success("✅ API 配置已保存！环境变量已热更新，无需重启服务")
                    # 验证交易 Key
                    verify_result = actions.get('verify_credentials_and_snapshot', lambda **kw: {'ok': False})()
                    if verify_result.get('ok'):
                        st.success("✅ 交易 Key 验证成功!")
                        summary = verify_result.get('account_summary', {})
                        balance = summary.get('balance', {})
                        total_usdt = balance.get('total', {}).get('USDT', 0) if isinstance(balance, dict) else 0
                        st.session_state.live_balance = {'equity': total_usdt, 'available': total_usdt}
                    else:
                        st.warning(f"⚠️ 交易 Key 验证失败: {verify_result.get('error', '未知错误')[:50]}")
                    time.sleep(1)
                    st.rerun()
                
                if st.session_state.pop('_dual_key_save_empty', False):
                    st.warning("⚠️ 请至少输入一个字段")
                
                if '_dual_key_save_error' in st.session_state:
                    st.error(f"❌ 保存失败: {st.session_state.pop('_dual_key_save_error')}")
                
                # 帮助信息
                with st.expander("💡 双 Key 机制说明", expanded=False):
                    st.markdown("""
                    **为什么需要双 Key？**
                    
                    OKX API 有请求频率限制（Rate Limit）。如果 K线图高频刷新和交易下单共用同一个 Key，
                    可能导致交易请求被限流，错过最佳入场时机。
                    
                    **推荐配置：**
                    1. **交易 Key**：需要交易权限，用于下单
                    2. **行情 Key**：只读权限即可，用于 K线图
                    
                    **如何创建只读 Key？**
                    1. 登录 OKX 官网 → API 管理
                    2. 创建新 API Key
                    3. 权限只勾选"读取"，不勾选"交易"
                    4. 将新 Key 填入"行情专用 Key"
                    """)
        
        # 交易池配置
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">⬢ 交易池</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 【A】修复: 使用 robust symbol 规范化函数
        from utils.symbol_utils import normalize_symbol, parse_symbol_input
        
        # 设置默认交易池(使用规范化格式)
        default_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
        if "auto_symbols" not in st.session_state:
            st.session_state.auto_symbols = default_symbols
        
        # 动态交易池设置
        st.caption("💡 输入币种：btc, eth, sol...")
        symbol_input = st.text_area(
            "交易对列表(每行一个)",
            value="\n".join(st.session_state.auto_symbols),
            height=100
        )
        
        # 预览格式化后的交易池（不再显示白名单警告，白名单已改为动态获取）
        
        if st.button("💾 保存交易池", width="stretch"):
            # 【A】修复: 使用 parse_symbol_input 进行规范化
            new_symbols = parse_symbol_input(symbol_input)
            if new_symbols:
                # P2-10: 先写DB(SSOT)
                db_write_success = False
                try:
                    symbols_str = ",".join(new_symbols)
                    actions.get("update_bot_config", lambda **kwargs: None)(symbols=symbols_str)
                    actions.get("set_control_flags", lambda **kwargs: None)(reload_config=1)
                    db_write_success = True
                except Exception as e:
                    st.error(f"保存失败: {str(e)[:50]}")
                
                # P2-10: 只有 DB 写入成功后才更新 session_state
                if db_write_success:
                    st.session_state.auto_symbols = new_symbols
                    st.success(f"交易池已更新: {', '.join(new_symbols)}")
            else:
                st.warning("⚠️ 交易池不能为空, 请输入有效的交易对")
        
        # 交易参数配置
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(168, 237, 234, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">◎ 交易参数</span>
        </div>
        """, unsafe_allow_html=True)
        
        bot_config = actions.get("get_bot_config", lambda: {})()
        
        # 扫描周期配置
        import json
        ALL_TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1D']
        DEFAULT_TIMEFRAMES = ['1m', '3m', '5m', '15m', '30m', '1h']
        
        scan_tf_json = bot_config.get('scan_timeframes', '[]')
        try:
            current_scan_tfs = json.loads(scan_tf_json) if scan_tf_json else DEFAULT_TIMEFRAMES
        except:
            current_scan_tfs = DEFAULT_TIMEFRAMES
        
        with st.expander("(・ω・) 扫描周期设置", expanded=False):
            st.caption("选择需要扫描的时间周期")
            
            selected_tfs = st.multiselect(
                "选择扫描周期",
                options=ALL_TIMEFRAMES,
                default=[tf for tf in current_scan_tfs if tf in ALL_TIMEFRAMES],
                help="勾选需要扫描的周期，取消勾选的周期不会被扫描"
            )
            
            if st.button("(≧▽≦) 保存周期", key="save_scan_tf"):
                if not selected_tfs:
                    st.warning("(・_・;) 至少选择一个周期")
                else:
                    try:
                        actions.get("update_bot_config", lambda **kwargs: None)(
                            scan_timeframes=json.dumps(selected_tfs)
                        )
                        actions.get("set_control_flags", lambda **kwargs: None)(reload_config=1)
                        st.success(f"(◕‿◕) 扫描周期已保存: {', '.join(selected_tfs)}")
                    except Exception as e:
                        st.error(f"保存失败: {str(e)[:50]}")
            
            # 说明信息
            st.markdown("""
            <div style="
                background: rgba(255, 193, 7, 0.1);
                border-left: 3px solid #ffc107;
                padding: 10px;
                margin-top: 10px;
                border-radius: 4px;
                font-size: 12px;
            ">
                <b>(・ω・) 说明</b><br>
                • 必须勾选至少一个周期才能正常扫描信号<br>
                • 策略只会在勾选的周期上产生信号<br>
                • 建议根据策略特性选择合适的周期<br>
                • <b>实时策略</b>请在侧边栏切换到 WebSocket 模式
            </div>
            """, unsafe_allow_html=True)
            
            st.caption(f"当前扫描: {', '.join(selected_tfs) if selected_tfs else '无'}")
        current_leverage = bot_config.get('leverage', 20)
        current_main_pct = bot_config.get('main_position_pct', 0.03)
        current_sub_pct = bot_config.get('sub_position_pct', 0.01)
        current_hedge_pct = bot_config.get('hedge_position_pct', 0.03)
        current_hard_tp = bot_config.get('hard_tp_pct', 0.02)
        current_hedge_tp = bot_config.get('hedge_tp_pct', 0.005)
        current_max_pos_pct = bot_config.get('max_position_pct', 0.10)
        # 新增：自定义策略仓位比例
        current_custom_pct = bot_config.get('custom_position_pct', 0.02)
        
        # 判断当前策略类型，并获取策略默认参数
        try:
            from strategies.strategy_registry import is_custom_strategy, get_strategy_default_params
            current_strategy_id = st.session_state.get('selected_strategy_id', 'strategy_v2')
            is_custom = is_custom_strategy(current_strategy_id)
            
            # 获取策略的默认参数（用于显示推荐值）
            strategy_defaults = get_strategy_default_params(current_strategy_id)
        except ImportError:
            is_custom = False
            strategy_defaults = {}
        
        with st.expander("交易参数设置", expanded=False):
            st.caption("💡 调整杠杆、仓位比例和止盈参数")
            
            # 如果是自定义策略且有默认参数，显示提示
            if is_custom and strategy_defaults:
                st.info(f"(◕‿◕) 当前策略推荐: 仓位 {strategy_defaults.get('position_pct', 2)}% | 杠杆 {strategy_defaults.get('leverage', 50)}x")
            
            st.markdown("##### 杠杆与仓位")
            
            # P2修复: 杠杆设置(限制最大倍数)
            MAX_LEVERAGE = 50  # 安全上限
            new_leverage = st.slider(
                "杠杆倍数",
                min_value=1,
                max_value=MAX_LEVERAGE,
                value=min(current_leverage, MAX_LEVERAGE),
                step=1,
                help="默认20倍杠杆"
            )
            
            # 最大仓位比例（风控）
            new_max_pos_pct = st.number_input(
                "最大仓位比例(%)",
                min_value=1.0,
                max_value=100.0,
                value=current_max_pos_pct * 100,
                step=1.0,
                help="风控限制：已用保证金不能超过权益的此比例，默认10%"
            ) / 100
            
            # 根据策略类型显示不同的仓位配置
            if is_custom:
                # 自定义策略：只显示单一仓位比例
                st.info("(◕‿◕) 当前使用自定义策略，只需配置单一仓位比例")
                new_custom_pct = st.number_input(
                    "开仓仓位(%)",
                    min_value=0.1,
                    max_value=20.0,
                    value=current_custom_pct * 100,
                    step=0.5,
                    help="自定义策略的开仓仓位比例"
                ) / 100
                # 自定义策略不使用主次仓位，设为相同值
                new_main_pct = new_custom_pct
                new_sub_pct = new_custom_pct
                new_hedge_pct = current_hedge_pct  # 保持对冲仓不变
            else:
                # 内置策略：显示主次仓位配置
                new_custom_pct = current_custom_pct  # 保持不变
                # 仓位比例设置（三列：主仓、次仓、对冲仓）
                col_pos1, col_pos2, col_pos3 = st.columns(3)
                with col_pos1:
                    new_main_pct = st.number_input(
                        "主信号仓(%)",
                        min_value=0.1,
                        max_value=20.0,
                        value=current_main_pct * 100,
                        step=0.5,
                        help="主周期信号的仓位比例"
                    ) / 100
                with col_pos2:
                    new_sub_pct = st.number_input(
                        "次信号仓(%)",
                        min_value=0.1,
                        max_value=10.0,
                        value=current_sub_pct * 100,
                        step=0.5,
                        help="次周期信号的仓位比例"
                    ) / 100
                with col_pos3:
                    new_hedge_pct = st.number_input(
                        "对冲仓(%)",
                        min_value=0.1,
                        max_value=20.0,
                        value=current_hedge_pct * 100,
                        step=0.5,
                        help="反向对冲信号的仓位比例"
                    ) / 100
            
            # 止盈/止损设置（根据策略类型显示不同选项）
            if is_custom:
                st.markdown("##### 止盈止损参数")
                col_tp1, col_tp2 = st.columns(2)
                with col_tp1:
                    new_hard_tp = st.number_input(
                        "止盈(%)",
                        min_value=0.1,
                        max_value=50.0,
                        value=current_hard_tp * 100,
                        step=0.5,
                        help="盈利达到此比例自动止盈"
                    ) / 100
                with col_tp2:
                    # 自定义策略显示止损而不是对冲止盈
                    current_stop_loss = bot_config.get('custom_stop_loss_pct', 0.02)
                    new_stop_loss = st.number_input(
                        "止损(%)",
                        min_value=0.1,
                        max_value=20.0,
                        value=current_stop_loss * 100,
                        step=0.1,
                        help="亏损达到此比例自动止损"
                    ) / 100
                new_hedge_tp = current_hedge_tp  # 保持不变
            else:
                st.markdown("##### 止盈参数")
                col_tp1, col_tp2 = st.columns(2)
                with col_tp1:
                    new_hard_tp = st.number_input(
                        "硬止(%)",
                        min_value=0.1,
                        max_value=50.0,
                        value=current_hard_tp * 100,
                        step=0.5,
                        help="仅主仓时, 本金盈利达到此比例自动止盈"
                    ) / 100
                with col_tp2:
                    new_hedge_tp = st.number_input(
                        "对冲止盈 (%)",
                        min_value=0.1,
                        max_value=20.0,
                        value=current_hedge_tp * 100,
                        step=0.1,
                        help="有对冲仓时, 净收益率达到此比例全仓止盈"
                    ) / 100
                new_stop_loss = bot_config.get('custom_stop_loss_pct', 0.02)  # 保持不变
            
            # 保存按钮
            if st.button("💾 保存交易参数", width="stretch"):
                try:
                    actions.get("update_bot_config", lambda **kwargs: None)(
                        leverage=new_leverage,
                        main_position_pct=new_main_pct,
                        sub_position_pct=new_sub_pct,
                        hedge_position_pct=new_hedge_pct,
                        hard_tp_pct=new_hard_tp,
                        hedge_tp_pct=new_hedge_tp,
                        max_position_pct=new_max_pos_pct,
                        custom_position_pct=new_custom_pct,
                        custom_stop_loss_pct=new_stop_loss  # 保存自定义策略止损
                    )
                    actions.get("set_control_flags", lambda **kwargs: None)(reload_config=1)
                    st.success("交易参数已保存")
                except Exception as e:
                    st.error(f"保存失败: {str(e)[:50]}")
            
            # 显示当前参数摘要
            if is_custom:
                st.caption(f"当前: {new_leverage}x杠杆 | 最大仓位{new_max_pos_pct*100:.0f}% | 开仓{new_custom_pct*100:.1f}% | 止盈{new_hard_tp*100:.1f}% | 止损{new_stop_loss*100:.1f}%")
            else:
                st.caption(f"当前: {new_leverage}x杠杆 | 最大仓位{new_max_pos_pct*100:.0f}% | 主仓{new_main_pct*100:.1f}% | 次仓{new_sub_pct*100:.1f}% | 对冲{new_hedge_pct*100:.1f}%")
        
        # 高级策略配置面板
        try:
            from strategies.strategy_registry import is_advanced_strategy, get_strategy_risk_config
            is_advanced = is_advanced_strategy(current_strategy_id)
        except ImportError:
            is_advanced = False
        
        if is_advanced:
            _render_advanced_strategy_config(current_strategy_id, actions)
        
        # 数据源模式选择器
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin: 20px 0 12px 0;
            box-shadow: 0 4px 15px rgba(137, 247, 254, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">◉ 数据源</span>
        </div>
        """, unsafe_allow_html=True)
        
        if "data_source_mode" not in st.session_state:
            try:
                bot_config = actions.get("get_bot_config", lambda: {})()
                saved_mode = bot_config.get('data_source_mode', 'REST')
                st.session_state.data_source_mode = saved_mode if saved_mode in ['REST', 'WebSocket'] else 'REST'
            except Exception:
                st.session_state.data_source_mode = "REST"
        
        DATA_SOURCE_MODES = {
            "REST": "○ REST 轮询",
            "WebSocket": "● WebSocket"
        }
        
        def _on_data_source_change():
            """数据源模式切换回调"""
            sel = st.session_state.get('data_source_selector')
            if sel:
                st.session_state.data_source_mode = sel
                try:
                    actions.get("update_bot_config", lambda **kw: None)(data_source_mode=sel)
                    actions.get("set_control_flags", lambda **kw: None)(reload_config=1)
                except Exception:
                    pass
        
        current_mode = st.session_state.data_source_mode
        mode_options = list(DATA_SOURCE_MODES.keys())
        current_idx = mode_options.index(current_mode) if current_mode in mode_options else 0
        
        st.selectbox(
            "数据源模式",
            mode_options,
            index=current_idx,
            key='data_source_selector',
            format_func=lambda x: DATA_SOURCE_MODES.get(x, x),
            on_change=_on_data_source_change,
            label_visibility="collapsed"
        )
        
        # 模式说明
        if st.session_state.data_source_mode == "REST":
            st.caption("📌 收盘信号策略推荐，每分钟00秒扫描，稳定可靠")
        else:
            st.caption("⚡ 实时信号策略推荐，毫秒级推送，适合突破/动量策略")
            # 显示 WebSocket 连接状态
            try:
                from database.db_bridge import get_ws_status
                ws_status = get_ws_status()
                if ws_status and ws_status.get('connected'):
                    st.success("(◕‿◕) WebSocket 已连接")
                else:
                    st.warning("(・_・;) WebSocket 连接中...")
            except ImportError:
                pass
        
        # 数据源模式说明
        with st.expander("(・ω・) 数据源模式说明", expanded=False):
            st.markdown("""
            **REST 轮询模式**
            - 每分钟00秒扫描一次
            - 使用已收盘的K线数据
            - 适合：均线交叉、MACD、RSI 等趋势策略
            - 优点：信号稳定，不会假突破
            
            **WebSocket 实时模式**
            - 毫秒级实时推送
            - 使用最新的价格数据
            - 适合：突破策略、动量策略、网格策略
            - 优点：响应快，抓住瞬间机会
            
            **💡 如何选择？**
            - 新手建议使用 REST 模式
            - 策略需要实时价格时切换 WebSocket
            """)
        
        # 资产概览已移至侧边栏顶部, 此处不再重复显示
        # API 隔离状态已整合到"API 密钥管理"面板中

@st.fragment
def _render_kline_section_fragment(view_model, actions):
    """
     K线图区域 Fragment - 包含 expander 和自动刷新逻辑
    
    使用 @st.fragment（无 run_every）将整个区域封装为独立 fragment：
    1. expander 状态在 fragment 内部管理，不受外部刷新影响
    2. 只有当用户勾选"自动刷新"且 expander 展开时，才启动定时刷新
    3. 折叠时跳过图表渲染，节省资源
    """
    # 使用 session_state 记录展开状态
    if 'kline_expanded' not in st.session_state:
        st.session_state.kline_expanded = False
    
    # expander 展开状态检测 - expanded 参数控制初始状态
    expanded = st.expander("展开K线图", expanded=st.session_state.kline_expanded)
    with expanded:
        # 更新 session_state 中的展开状态（用于下次渲染）
        # 注意：Streamlit 的 expander 不直接返回当前展开状态
        # 我们通过 checkbox 来让用户控制是否启用自动刷新
        
        # 只有当 expander 内容被渲染时才执行
        if not HAS_PLOTLY and not HAS_LIGHTWEIGHT_CHARTS:
            st.warning("⚠️ 请安装 plotly 或 streamlit-lightweight-charts 库以显示K线图")
            return
        
        # 渲染 K线图
        _render_kline_chart(view_model, actions)


def _render_kline_chart(view_model, actions):
    """渲染K线图分析窗口 - TradingView Lightweight Charts 风格
    
     K线图完全独立模块：
    1. 使用独立缓存，只显示收盘K线
    2. 独立计算策略信号（不读数据库）
    3. 支持自动刷新（使用 @st.fragment 局部刷新）
    """
    symbols = st.session_state.get('auto_symbols', ['BTC/USDT:USDT'])
    if not symbols:
        st.info("请先在侧边栏配置交易池")
        return
    
    timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1D']
    
    # 控制栏（固定自动刷新，无手动刷新按钮）
    col_sym, col_tf, col_interval, col_status = st.columns([3, 1, 1, 1])
    with col_sym:
        selected_symbol = st.selectbox("币种", symbols, key="kline_symbol_selector")
    with col_tf:
        selected_tf = st.selectbox("周期", timeframes, index=2, key="kline_tf_selector")
    with col_interval:
        # 刷新间隔选择
        refresh_interval = st.selectbox(
            "间隔",
            options=[1, 2, 5, 10],
            index=0,
            key="kline_refresh_interval",
            format_func=lambda x: f"{x}秒"
        )
    with col_status:
        api_status = check_market_api_status()
        if api_status:
            st.caption("🟢 API")
        else:
            st.caption("🟡 直连")
    
    # 固定使用自动刷新模式
    _render_kline_chart_realtime(selected_symbol, selected_tf, api_status, refresh_interval)


def _render_kline_chart_realtime(selected_symbol, selected_tf, api_status, refresh_interval):
    """
     实时 K线图 - 使用自定义 HTML 组件实现 TradingView 风格的实时更新
    
    特点：
    1. 使用 JavaScript 直接操作 Lightweight Charts API
    2. 增量更新数据，不重建图表
    3. 保持用户的缩放/拖动位置
    """
    import streamlit.components.v1 as components
    import json
    
    BEIJING_OFFSET_SEC = 8 * 3600
    
    # 获取当前策略ID
    current_strategy_id = st.session_state.get('selected_strategy_id', 'strategy_v2')
    
    # 获取 K线数据（统一使用 1000 条，满足策略计算需求）
    ohlcv_data = []
    markers = []
    
    # 优先尝试 WebSocket（实时数据）
    ws_data = _fetch_ohlcv_via_websocket(selected_symbol, selected_tf, limit=1000)
    if ws_data and len(ws_data) >= 50:
        ohlcv_data = ws_data
    elif api_status:
        # 回退到 Market API
        result = fetch_kline_from_api(selected_symbol, selected_tf, limit=1000, strategy_id=current_strategy_id)
        if result.get('ok'):
            ohlcv_data = result.get('data', [])
            markers = result.get('markers', [])
    
    if not ohlcv_data:
        # 最后回退到直接 REST 获取
        ohlcv_data = _fetch_ohlcv_for_chart(selected_symbol, selected_tf, limit=1000)
    
    if not ohlcv_data:
        st.warning("⚠️ 无法获取K线数据")
        return
    
    # 转换数据格式
    candle_data = []
    volume_data = []
    for row in ohlcv_data:
        ts_ms, open_p, high_p, low_p, close_p, volume = row
        ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
        candle_data.append({
            "time": ts_sec,
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(close_p)
        })
        volume_data.append({
            "time": ts_sec,
            "value": float(volume),
            "color": "#26a69a80" if float(close_p) >= float(open_p) else "#ef535080"
        })
    
    # 构建 API URL
    api_url = f"{MARKET_API_URL}/kline?symbol={selected_symbol}&tf={selected_tf}&limit=5"
    
    # 生成自定义 HTML 组件
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #131722; }}
            #chart {{ width: 100%; height: 500px; }}
            #status {{ 
                color: #d1d4dc; 
                font-size: 12px; 
                padding: 5px 10px; 
                background: #1e222d;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .price-up {{ color: #26a69a; }}
            .price-down {{ color: #ef5350; }}
        </style>
    </head>
    <body>
        <div id="chart"></div>
        <div id="status">
            <span id="price-info">加载中...</span>
            <span id="update-time">--</span>
        </div>
        <script>
            // 初始化图表
            const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
                width: document.getElementById('chart').clientWidth,
                height: 500,
                layout: {{
                    background: {{ type: 'solid', color: '#131722' }},
                    textColor: '#d1d4dc'
                }},
                grid: {{
                    vertLines: {{ color: '#363a45' }},
                    horzLines: {{ color: '#363a45' }}
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal
                }},
                rightPriceScale: {{
                    borderColor: '#363a45'
                }},
                timeScale: {{
                    borderColor: '#363a45',
                    timeVisible: true,
                    secondsVisible: false
                }}
            }});
            
            // 创建蜡烛图系列
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderUpColor: '#26a69a',
                borderDownColor: '#ef5350',
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350'
            }});
            
            // 创建成交量系列
            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: 'volume'
            }});
            volumeSeries.priceScale().applyOptions({{
                scaleMargins: {{ top: 0.8, bottom: 0 }}
            }});
            
            // 加载初始数据
            const initialCandles = {json.dumps(candle_data)};
            const initialVolumes = {json.dumps(volume_data)};
            const markers = {json.dumps(markers)};
            
            candleSeries.setData(initialCandles);
            volumeSeries.setData(initialVolumes);
            
            // 设置信号标记
            if (markers && markers.length > 0) {{
                candleSeries.setMarkers(markers);
            }}
            
            // 自适应大小
            window.addEventListener('resize', () => {{
                chart.applyOptions({{ width: document.getElementById('chart').clientWidth }});
            }});
            
            // 更新状态栏
            function updateStatus(candle) {{
                const priceInfo = document.getElementById('price-info');
                const updateTime = document.getElementById('update-time');
                
                const price = candle.close.toLocaleString('en-US', {{style: 'currency', currency: 'USD'}});
                const change = ((candle.close / initialCandles[0].open - 1) * 100).toFixed(2);
                const changeClass = change >= 0 ? 'price-up' : 'price-down';
                const changeIcon = change >= 0 ? '🟢' : '🔴';
                
                priceInfo.innerHTML = ` ${{price}} | <span class="${{changeClass}}">${{changeIcon}} ${{change}}%</span>`;
                
                const now = new Date();
                updateTime.textContent = `🔄 ${{now.toLocaleTimeString()}}`;
            }}
            
            // 初始状态
            if (initialCandles.length > 0) {{
                updateStatus(initialCandles[initialCandles.length - 1]);
            }}
            
            //  实时更新函数
            async function fetchAndUpdate() {{
                try {{
                    const response = await fetch('{api_url}');
                    const result = await response.json();
                    
                    if (result.data && result.data.length > 0) {{
                        // 获取最新的几根K线
                        const newCandles = result.data.map(row => ({{
                            time: Math.floor(row[0] / 1000) + {BEIJING_OFFSET_SEC},
                            open: parseFloat(row[1]),
                            high: parseFloat(row[2]),
                            low: parseFloat(row[3]),
                            close: parseFloat(row[4])
                        }}));
                        
                        const newVolumes = result.data.map(row => ({{
                            time: Math.floor(row[0] / 1000) + {BEIJING_OFFSET_SEC},
                            value: parseFloat(row[5]),
                            color: parseFloat(row[4]) >= parseFloat(row[1]) ? '#26a69a80' : '#ef535080'
                        }}));
                        
                        //  增量更新：只更新最后一根K线
                        const latestCandle = newCandles[newCandles.length - 1];
                        const latestVolume = newVolumes[newVolumes.length - 1];
                        
                        candleSeries.update(latestCandle);
                        volumeSeries.update(latestVolume);
                        
                        updateStatus(latestCandle);
                    }}
                }} catch (e) {{
                    console.error('更新失败:', e);
                }}
            }}
            
            //  定时刷新
            setInterval(fetchAndUpdate, {refresh_interval * 1000});
        </script>
    </body>
    </html>
    '''
    
    # 渲染组件
    components.html(html_content, height=550)


def _render_kline_chart_core(selected_symbol, selected_tf, fetch_btn, api_status, is_auto_refresh=False):
    """
     K线图核心渲染逻辑
    """
    # 获取当前选择的策略ID（用于计算信号标记）
    current_strategy_id = st.session_state.get('selected_strategy_id', 'strategy_v2')
    
    # 获取 K线数据 - 优先 Market API，回退直连 OKX
    ohlcv_data = []
    api_markers = []  # API 返回的策略信号标记
    data_source = ""
    
    # 自动刷新时不计算策略信号（性能优化）
    use_strategy_markers = not is_auto_refresh
    
    # 方案1: 尝试 Market API
    if api_status:
        strategy_param = current_strategy_id if use_strategy_markers else None
        result = fetch_kline_from_api(selected_symbol, selected_tf, limit=1000, strategy_id=strategy_param)
        if result.get('ok'):
            ohlcv_data = result.get('data', [])
            api_markers = result.get('markers', [])
            data_source = "API" if not result.get('cached') else "API(缓存)"
    
    # 方案2: 回退直连 OKX
    if not ohlcv_data:
        ohlcv_data = _fetch_ohlcv_for_chart(selected_symbol, selected_tf, limit=1000)
        if ohlcv_data:
            data_source = "OKX直连"
    
    # 刷新按钮强制拉取（包含策略信号）
    if fetch_btn:
        _UI_KLINE_CACHE.clear()
        if api_status:
            result = fetch_kline_from_api(selected_symbol, selected_tf, limit=1000, strategy_id=current_strategy_id)
            if result.get('ok'):
                ohlcv_data = result.get('data', [])
                api_markers = result.get('markers', [])
                data_source = "API(刷新)"
        if not ohlcv_data:
            ohlcv_data = _fetch_ohlcv_for_chart(selected_symbol, selected_tf, limit=1000)
            data_source = "OKX直连(刷新)"
    
    if not ohlcv_data:
        st.warning("⚠️ 无法获取K线数据，请检查网络连接")
        return
    
    # 转换数据为 Lightweight Charts 格式
    # UTC 时间戳 + 8小时 = 北京时间
    BEIJING_OFFSET_SEC = 8 * 3600
    
    # 准备蜡烛图数据 (Lightweight Charts 需要 time 为秒级时间戳)
    candle_data = []
    for row in ohlcv_data:
        ts_ms, open_p, high_p, low_p, close_p, volume = row
        # 转换为北京时间的秒级时间戳
        ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
        candle_data.append({
            "time": ts_sec,
            "open": float(open_p),
            "high": float(high_p),
            "low": float(low_p),
            "close": float(close_p)
        })
    
    # 准备成交量数据
    volume_data = []
    for row in ohlcv_data:
        ts_ms, open_p, high_p, low_p, close_p, volume = row
        ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
        color = '#26a69a80' if close_p >= open_p else '#ef535080'
        volume_data.append({
            "time": ts_sec,
            "value": float(volume),
            "color": color
        })
    
    # 使用 API 返回的策略信号标记（已在后端计算完成）
    markers = api_markers if api_markers else []
    signal_info = None  # 最新信号信息
    
    # 信号标记缓存（自动刷新时复用之前的信号，避免重复计算）
    markers_cache_key = f"markers_{selected_symbol}_{selected_tf}_{current_strategy_id}"
    if markers:
        # 有新的信号标记，更新缓存
        st.session_state[markers_cache_key] = markers
    elif is_auto_refresh and markers_cache_key in st.session_state:
        # 自动刷新时，复用缓存的信号标记
        markers = st.session_state[markers_cache_key]
    
    # 如果 API 没有返回 markers（直连模式或自动刷新），尝试本地计算或使用缓存
    if not markers and ohlcv_data and not is_auto_refresh:
        try:
            # 动态加载策略模块
            from strategies.strategy_registry import get_strategy_registry
            registry = get_strategy_registry()
            strategy_class = registry.get_strategy_class(current_strategy_id)
            
            if strategy_class:
                strategy = strategy_class()
                
                # 将 OHLCV 数据转换为 DataFrame
                df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # 检查数据量是否足够（统一要求 1000 条）
                min_bars = 1000
                if len(df) >= min_bars:
                    # 计算技术指标
                    try:
                        df_with_indicators = strategy.calculate_indicators(df)
                    except ValueError:
                        df_with_indicators = None
                    
                    if df_with_indicators is not None:
                        # 遍历最近 100 根 K线，检查信号
                        start_idx = max(min_bars, len(df) - 100)
                        
                        for i in range(start_idx, len(df) - 1):
                            sub_df = df_with_indicators.iloc[:i+2].copy()
                            try:
                                signal = strategy.check_signals(sub_df, timeframe=selected_tf)
                                if signal and signal.get('action') in ['LONG', 'SHORT']:
                                    action = signal['action']
                                    signal_type = signal.get('type', 'UNKNOWN')
                                    
                                    ts_ms = int(df.iloc[i]['timestamp'])
                                    ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
                                    
                                    if action == 'LONG':
                                        markers.append({
                                            "time": ts_sec,
                                            "position": "belowBar",
                                            "shape": "arrowUp",
                                            "color": "#26a69a",
                                            "text": f"BUY\n{signal_type}"
                                        })
                                    elif action == 'SHORT':
                                        markers.append({
                                            "time": ts_sec,
                                            "position": "aboveBar",
                                            "shape": "arrowDown",
                                            "color": "#ef5350",
                                            "text": f"SELL\n{signal_type}"
                                        })
                            except Exception:
                                continue
        except Exception as e:
            # 策略计算失败时静默处理
            pass
    
    # 提取最新信号信息（用于底部显示）
    if markers:
        latest_marker = markers[-1]
        signal_info = {
            'signal': 'BUY' if 'BUY' in latest_marker.get('text', '') else 'SELL',
            'price': candle_data[-1]['close'] if candle_data else 0,
            'reason': latest_marker.get('text', '').replace('\n', ' ')
        }
    
    # 渲染 Lightweight Charts
    if HAS_LIGHTWEIGHT_CHARTS:
        # TradingView Lightweight Charts 配置
        chart_options = {
            "height": 500,
            "layout": {
                "background": {"type": "solid", "color": "#131722"},
                "textColor": "#d1d4dc"
            },
            "grid": {
                "vertLines": {"color": "#363a45"},
                "horzLines": {"color": "#363a45"}
            },
            "crosshair": {
                "mode": 0,  # Normal crosshair
                "vertLine": {
                    "color": "#758696",
                    "width": 1,
                    "style": 2,
                    "labelBackgroundColor": "#2B2B43"
                },
                "horzLine": {
                    "color": "#758696",
                    "width": 1,
                    "style": 2,
                    "labelBackgroundColor": "#2B2B43"
                }
            },
            "rightPriceScale": {
                "borderColor": "#363a45",
                "scaleMargins": {"top": 0.1, "bottom": 0.2}
            },
            "timeScale": {
                "borderColor": "#363a45",
                "timeVisible": True,
                "secondsVisible": False
            },
            "handleScroll": {"vertTouchDrag": False},
            "handleScale": {"axisPressedMouseMove": True}
        }
        
        # 蜡烛图系列配置
        candlestick_series = {
            "type": "Candlestick",
            "data": candle_data,
            "options": {
                "upColor": "#26a69a",
                "downColor": "#ef5350",
                "borderUpColor": "#26a69a",
                "borderDownColor": "#ef5350",
                "wickUpColor": "#26a69a",
                "wickDownColor": "#ef5350"
            },
            "markers": markers if markers else []
        }
        
        # 成交量系列配置
        volume_series = {
            "type": "Histogram",
            "data": volume_data,
            "options": {
                "priceFormat": {"type": "volume"},
                "priceScaleId": "volume"
            },
            "priceScale": {
                "scaleMargins": {"top": 0.8, "bottom": 0}
            }
        }
        
        # 渲染图表
        try:
            renderLightweightCharts([
                {
                    "chart": chart_options,
                    "series": [candlestick_series, volume_series]
                }
            ], key=f"kline_{selected_symbol}_{selected_tf}")
        except Exception as e:
            st.error(f"K线图渲染失败: {e}")
            # 回退到 Plotly
            if HAS_PLOTLY:
                _render_kline_chart_plotly(ohlcv_data, selected_symbol, selected_tf, data_source, markers)
        
    else:
        # 回退到 Plotly
        if HAS_PLOTLY:
            _render_kline_chart_plotly(ohlcv_data, selected_symbol, selected_tf, data_source, markers)
        else:
            st.warning("⚠️ 请安装 streamlit-lightweight-charts 或 plotly")
    
    # 数据统计 - TradingView 风格底部信息栏
    if candle_data:
        latest = candle_data[-1]
        first = candle_data[0]
        price_change = ((latest['close'] / first['open']) - 1) * 100 if first['open'] > 0 else 0
        change_icon = "🟢" if price_change >= 0 else "🔴"
        
        # 转换时间戳为北京时间字符串
        latest_dt = datetime.fromtimestamp(latest['time'])
        latest_time_str = latest_dt.strftime('%m/%d %H:%M')
        
        # 统计买卖信号数量
        buy_count = len([m for m in markers if 'BUY' in m.get('text', '')])
        sell_count = len([m for m in markers if 'SELL' in m.get('text', '')])
        signal_summary = f" {buy_count}买/{sell_count}卖" if markers else " 无信号"
        
        # 实时价格显示
        latest_price = latest['close']
        price_display = f"${latest_price:,.2f}" if latest_price < 1000 else f"${latest_price:,.0f}"
        
        col_stat1, col_stat2, col_stat3, col_stat4, col_stat5, col_stat6 = st.columns(6)
        with col_stat1:
            st.caption(f" {price_display}")
        with col_stat2:
            st.caption(f"🕐 {latest_time_str}")
        with col_stat3:
            st.caption(f"{change_icon} {price_change:+.2f}%")
        with col_stat4:
            st.caption(f" {data_source}")
        with col_stat5:
            st.caption(signal_summary)
        with col_stat6:
            st.caption(f" {len(candle_data)} bars")
    
    # 显示最新信号状态
    if signal_info:
        sig_color = "#26a69a" if signal_info['signal'] == 'BUY' else "#ef5350"
        sig_icon = "🟢 买入" if signal_info['signal'] == 'BUY' else "🔴 卖出"
        st.markdown(f"""
        <div style="background: #1e222d; padding: 10px; border-radius: 5px; margin: 5px 0;">
            <span style="color: {sig_color}; font-weight: bold; font-size: 16px;">
                📌 最新信号: {sig_icon} @ {signal_info['price']:.2f}
            </span>
            <span style="color: #888; font-size: 12px; margin-left: 10px;">
                {signal_info.get('reason', '')}
            </span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.caption("📌 当前无信号（基于收盘K线独立计算）")


def _render_kline_chart_plotly(ohlcv_data, selected_symbol, selected_tf, data_source, markers):
    """Plotly 回退方案 - 当 Lightweight Charts 不可用时使用"""
    BEIJING_OFFSET_SEC = 8 * 3600
    
    df = pd.DataFrame(ohlcv_data, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['datetime'] = pd.to_datetime(df['ts'] + BEIJING_OFFSET_SEC * 1000, unit='ms')
    df.set_index('datetime', inplace=True)
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        name='K线',
        increasing_line_color='#26a69a',
        decreasing_line_color='#ef5350',
        increasing_fillcolor='#26a69a',
        decreasing_fillcolor='#ef5350'
    ))
    
    fig.update_layout(
        height=500,
        plot_bgcolor='#131722',
        paper_bgcolor='#131722',
        font=dict(color='#d1d4dc'),
        margin=dict(l=10, r=60, t=40, b=30),
        xaxis=dict(
            rangeslider=dict(visible=True, thickness=0.04, bgcolor='#1e222d'),
            gridcolor='#363a45',
            showgrid=True
        ),
        yaxis=dict(side='right', gridcolor='#363a45', showgrid=True),
        dragmode='pan'
    )
    
    config = {'scrollZoom': True, 'displayModeBar': True, 'displaylogo': False}
    st.plotly_chart(fig, config=config)


@st.fragment(run_every=2)
def _render_dashboard_cards_fragment(view_model, actions):
    """
     实盘监控卡片 Fragment - 每2秒自动刷新
    
    使用 @st.fragment(run_every=2) 实现局部自动刷新
    只刷新价格和状态，不影响其他组件
    """
    c1, c2, c3, c4 = st.columns(4)
    
    # session_state 获取 env_mode
    env_mode = st.session_state.get('env_mode', view_model.get("env_mode", "● 实盘"))
    trading_active = view_model.get("trading_active", False)
    open_positions = view_model.get("open_positions", {})
    
    # 实时获取 BTC 价格（每次 fragment 刷新都会重新获取）
    btc_price = fetch_btc_ticker_cached()
    if btc_price == "----":
        btc_price = view_model.get("btc_price", "----")
    
    engine_status = view_model.get("engine_status", {})
    runner_alive = engine_status.get("alive", 0) == 1
    last_error = engine_status.get("last_error")
    
    with c1: st.metric("BTC", btc_price)
    with c2: st.metric("状态", "运行中" if trading_active else "待机")
    with c3: st.metric("持仓", len(open_positions))
    with c4: st.metric("模式", env_mode)


@st.fragment(run_every=5)
def _render_position_analysis_fragment(view_model, actions):
    """
     持仓分析 Fragment - 每5秒自动刷新
    """
    # 实时获取持仓数据
    open_positions = actions.get("get_open_positions", lambda: {})()
    hedge_positions = actions.get("get_hedge_positions", lambda: {})()
    
    has_positions = open_positions or hedge_positions
    
    if has_positions:
        pos_data = []
        
        # 主仓数据
        for symbol, pos in open_positions.items():
            if pos.get("size", 0) > 0:
                pos_data.append({
                    "币种": symbol,
                    "类型": "主仓",
                    "方向": pos.get("side", "LONG"),
                    "保证金": f"${pos.get('margin', pos.get('size', 0)/20):.2f}",
                    "名义价值": f"${pos.get('size', 0):.2f}",
                    "入场价": f"${pos.get('entry_price', 0):.8g}",
                    "浮盈": f"${pos.get('pnl', 0):+.2f}"
                })
        
        # 对冲仓数据
        for symbol, hedge_list in hedge_positions.items():
            for idx, pos in enumerate(hedge_list):
                if pos.get("size", 0) > 0:
                    pos_data.append({
                        "币种": symbol,
                        "类型": f"对冲仓{idx+1}",
                        "方向": pos.get("side", "SHORT"),
                        "保证金": f"${pos.get('margin', pos.get('size', 0)/20):.2f}",
                        "名义价值": f"${pos.get('size', 0):.2f}",
                        "入场价": f"${pos.get('entry_price', 0):.8g}",
                        "浮盈": f"${pos.get('pnl', 0):+.2f}"
                    })
        
        if pos_data:
            df_positions = pd.DataFrame(pos_data)
            st.dataframe(df_positions, hide_index=True)
    else:
        st.info("暂无持仓数据")


@st.fragment(run_every=5)
def _render_trade_stats_fragment(view_model, actions):
    """
     交易统计 Fragment - 每5秒自动刷新
    """
    try:
        trade_stats = actions.get("get_trade_stats", lambda: {})()
        paper_balance = actions.get("get_paper_balance", lambda: {})()
        
        current_equity = float(paper_balance.get('equity', 200) or 200) if paper_balance else 200
        
        stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
        with stat_col1:
            st.metric("模拟净值", f"${current_equity:.2f}")
        with stat_col2:
            total_trades = trade_stats.get('total_trades', 0) if trade_stats else 0
            win_rate = trade_stats.get('win_rate', 0) if trade_stats else 0
            st.metric("总交易", f"{total_trades}", delta=f"胜率 {win_rate:.1f}%")
        with stat_col3:
            total_pnl = trade_stats.get('total_pnl', 0) if trade_stats else 0
            st.metric("总盈亏", f"${total_pnl:+.2f}")
        with stat_col4:
            max_dd = trade_stats.get('max_drawdown', 0) if trade_stats else 0
            st.metric("最大回撤", f"${max_dd:.2f}")
    except Exception as e:
        st.info("暂无交易统计数据")


def render_dashboard(view_model, actions):
    """渲染主仪表盘"""
    # 统一metric卡片样式
    st.markdown("""
    <style>
    /* 统一所有metric卡片的样式 */
    [data-testid="stMetric"] {
        background: rgba(28, 31, 38, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
    }
    [data-testid="stMetric"] label {
        color: rgba(255, 255, 255, 0.6) !important;
        font-size: 12px !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 600 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 从 view_model 获取关键变量
    open_positions = view_model.get("open_positions", {})
    env_mode = st.session_state.get('env_mode', view_model.get("env_mode", "● 实盘"))
    
    # 主页面布局
    col_main, col_right = st.columns([7, 3])
    
    # 右侧装饰图片
    st.markdown("""
    <style>
    /* 右侧装饰图片容器 - 固定定位覆盖右侧空白区域 */
    .deco-image-wrapper {
        position: fixed;
        top: 0;
        right: 0;
        width: 18%;
        height: 100vh;
        overflow: hidden;
        z-index: 0;
        pointer-events: none;
    }
    
    /* 装饰图片 */
    .deco-image-wrapper .deco-image {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center top;
        opacity: 0.9;
    }
    
    /* 左侧黑色渐变遮罩 */
    .deco-image-wrapper .deco-overlay-left {
        position: absolute;
        top: 0;
        left: 0;
        width: 60%;
        height: 100%;
        background: linear-gradient(to right, 
            rgba(14, 17, 23, 1) 0%,
            rgba(14, 17, 23, 0.95) 30%,
            rgba(14, 17, 23, 0.7) 60%,
            transparent 100%);
        z-index: 2;
        pointer-events: none;
    }
    
    /* 顶部黑色渐变 */
    .deco-image-wrapper .deco-overlay-top {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 80px;
        background: linear-gradient(to bottom, 
            rgba(14, 17, 23, 1) 0%, 
            rgba(14, 17, 23, 0.5) 60%,
            transparent 100%);
        z-index: 3;
        pointer-events: none;
    }
    
    /* 底部黑色渐变 */
    .deco-image-wrapper .deco-overlay-bottom {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 120px;
        background: linear-gradient(to top, 
            rgba(14, 17, 23, 1) 0%, 
            rgba(14, 17, 23, 0.6) 50%,
            transparent 100%);
        z-index: 3;
        pointer-events: none;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 加载并显示装饰图片
    import base64
    import os
    
    deco_image_path = "assets/deco_samurai.png"
    if os.path.exists(deco_image_path):
        with open(deco_image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <div class="deco-image-wrapper">
            <img class="deco-image" src="data:image/png;base64,{img_data}" alt=""/>
            <div class="deco-overlay-left"></div>
            <div class="deco-overlay-top"></div>
            <div class="deco-overlay-bottom"></div>
        </div>
        """, unsafe_allow_html=True)
    
    # 右侧列保持空白（图片已通过固定定位显示）
    with col_right:
        pass
    
    with col_main:
        # 实盘监控卡片（使用 fragment 局部刷新）
        st.markdown("#### ◈ 实盘监控")
        _render_dashboard_cards_fragment(view_model, actions)
        
        st.divider()
        
        # 【C】修复: 系统控制精简为 3 个按钮
        st.markdown("#### ◎ 系统控制")
        
        # 从数据库读取真实的交易状态
        bot_config = actions.get("get_bot_config", lambda: {})()
        db_enable_trading = bot_config.get("enable_trading", 0) == 1
        
        # 显示当前交易状态(基于数据库)
        if db_enable_trading:
            st.success("🟢 交易已启用")
        else:
            st.info("🔴 交易已关闭")
        
        # 炫酷按钮样式
        st.markdown("""
        <style>
        .stButton > button {
            border-radius: 10px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .stButton > button:hover {
            transform: scale(1.02);
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }
        div[data-testid="column"]:nth-child(1) .stButton > button {
            background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
            border: none;
            color: white;
        }
        div[data-testid="column"]:nth-child(2) .stButton > button {
            background: linear-gradient(135deg, #424242 0%, #616161 100%);
            border: none;
            color: white;
        }
        div[data-testid="column"]:nth-child(3) .stButton > button {
            background: linear-gradient(135deg, #ff5722 0%, #ff9800 100%);
            border: none;
            color: white;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 三个核心控制按钮
        control_cols = st.columns(3)
        
        with control_cols[0]:
            if st.button(" 启用交易", width="stretch", disabled=db_enable_trading):
                # 启用交易 - 写入数据库
                actions.get("update_bot_config", lambda **kwargs: None)(enable_trading=1)
                actions.get("set_control_flags", lambda **kwargs: None)(pause_trading=0, reload_config=1)
                st.session_state.trading_active = True
                st.success("交易已启用")
                time.sleep(0.5)
                st.rerun()
        
        with control_cols[1]:
            if st.button("⏹️ 关闭交易", width="stretch", disabled=not db_enable_trading):
                # 关闭交易 - 写入数据库
                actions.get("update_bot_config", lambda **kwargs: None)(enable_trading=0)
                actions.get("set_control_flags", lambda **kwargs: None)(pause_trading=1, reload_config=1)
                st.session_state.trading_active = False
                st.success("交易已关闭")
                time.sleep(0.5)
                st.rerun()
        
        with control_cols[2]:
            # P1修复: 一键平仓二次确认
            if "flatten_confirm_pending" not in st.session_state:
                st.session_state.flatten_confirm_pending = False
            
            if st.button(" 一键平仓", width="stretch"):
                if len(open_positions) > 0:
                    st.session_state.flatten_confirm_pending = True
                else:
                    st.info("ℹ️ 当前无持仓")
        
        # P1修复: 一键平仓确认弹窗
        if st.session_state.get('flatten_confirm_pending', False):
            st.error(f"⚠️ **确认平仓所有 {len(open_positions)} 个持仓?此操作不可撤销**")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("确认平仓", type="primary", width="stretch"):
                    flatten_start = time.time()
                    
                    # 即时平仓：直接执行，不等待扫描周期
                    try:
                        from database.db_bridge import execute_immediate_flatten, get_bot_config
                        
                        # 获取运行模式
                        bot_config = get_bot_config()
                        run_mode = bot_config.get('run_mode', 'paper')
                        
                        if run_mode == 'live':
                            # 实盘模式：仍然使用标志位，让后端处理（后端有交易所适配器）
                            # 但同时也清理数据库记录，确保 UI 立即更新
                            actions.get("set_control_flags", lambda **kwargs: None)(emergency_flatten=1)
                            flatten_time = time.time() - flatten_start
                            st.session_state.flatten_confirm_pending = False
                            st.warning(f"⚠️ [实盘] 已发送平仓信号到后端 | 持仓 {len(open_positions)} | 耗时: {flatten_time:.2f}s")
                        else:
                            # 测试模式：直接执行即时平仓
                            flatten_result = execute_immediate_flatten(
                                run_mode=run_mode,
                                exchange_adapter=None,
                                leverage=20
                            )
                            
                            flatten_time = time.time() - flatten_start
                            st.session_state.flatten_confirm_pending = False
                            
                            if flatten_result['success']:
                                closed_count = len(flatten_result['closed_positions'])
                                total_pnl = flatten_result['total_pnl']
                                new_equity = flatten_result['new_equity']
                                
                                st.success(f"✅ 即时平仓完成 | 平仓: {closed_count} | PnL: ${total_pnl:.2f} | 新权益: ${new_equity:.2f} | 耗时: {flatten_time:.2f}s")
                            else:
                                st.error(f"❌ 平仓失败: {'; '.join(flatten_result['errors'][:3])}")
                        
                    except Exception as e:
                        st.session_state.flatten_confirm_pending = False
                        st.error(f"❌ 平仓异常: {str(e)}")
                    
                    time.sleep(0.5)
                    st.rerun()
            with col_cancel:
                if st.button("取消", width="stretch"):
                    st.session_state.flatten_confirm_pending = False
                    st.rerun()
        
        st.caption("交易模式通过侧边栏设置")
        
        st.divider()
        
        # K线图展开窗口（使用独立 fragment，支持折叠状态检测）
        st.markdown("#### ✦ K线图")
        _render_kline_section_fragment(view_model, actions)
        
        st.divider()
        
        # 持仓分析（使用 fragment 局部刷新）
        st.markdown("#### ⬢ 持仓分析")
        _render_position_analysis_fragment(view_model, actions)
        
        st.divider()
        
        # 交易统计（测试模式显示，使用 fragment 局部刷新）
        if env_mode == "○ 测试":
            st.markdown("#### ◉ 交易统计")
            _render_trade_stats_fragment(view_model, actions)
            
            # 资金曲线图 - NOFX 金色渐变风格
            with st.expander("📈 资金曲线", expanded=False):
                trade_history = actions.get("get_trade_history", lambda limit=50: [])()
                if trade_history and len(trade_history) > 0:
                    from datetime import datetime
                    
                    # 获取真实权益，反推初始资金
                    paper_balance_init = actions.get("get_paper_balance", lambda: {})()
                    current_equity = float(paper_balance_init.get('equity', 208) or 208) if paper_balance_init else 208
                    
                    sorted_trades = sorted(trade_history, key=lambda x: x.get('ts', 0))
                    
                    # 从交易历史反推初始资金
                    total_pnl = sum(float(t.get('pnl', 0) or 0) for t in sorted_trades)
                    initial_equity = current_equity - total_pnl
                    
                    # 准备数据
                    timestamps = []
                    pnl_values = []
                    equity_values = []
                    cumulative_equity = initial_equity
                    
                    for trade in sorted_trades:
                        pnl = float(trade.get('pnl', 0) or 0)
                        cumulative_equity += pnl
                        ts = trade.get('ts', 0)
                        if ts > 0:
                            timestamps.append(datetime.fromtimestamp(ts / 1000))
                        else:
                            timestamps.append(datetime.now())
                        pnl_values.append(pnl)
                        equity_values.append(cumulative_equity)
                    
                    # 使用 NOFX 金色渐变风格渲染资金曲线
                    plot_nofx_equity_curve(timestamps, equity_values, initial_equity)
                    
                    # 底部统计
                    real_return = ((current_equity - initial_equity) / initial_equity) * 100 if initial_equity > 0 else 0
                    win_trades = sum(1 for p in pnl_values if p > 0)
                    win_rate = (win_trades / len(pnl_values) * 100) if pnl_values else 0
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.caption(f" 共 {len(sorted_trades)} 笔")
                    with col2:
                        color = "green" if real_return >= 0 else "red"
                        st.caption(f"📈 收益: :{color}[{real_return:+.2f}%]")
                    with col3:
                        st.caption(f" 胜率: {win_rate:.1f}%")
                    with col4:
                        st.caption(f" 净值: ${current_equity:.2f}")
                else:
                    st.info("暂无交易记录，完成首笔交易后将显示资金曲线")
            
            st.divider()
        
        # 情绪模块 - expander 展开时加载，fragment 局部刷新
        st.markdown("#### ◇ 市场情绪")
        with st.expander("情绪分析 & 新闻 & 链上数据", expanded=False):
            from ui.ui_sentiment import _render_sentiment_tab, _render_news_tab_fragment, _render_onchain_tab_fragment
            tab1, tab2, tab3 = st.tabs(["◈ 情绪指数", "◈ 新闻流", "◈ 链上数据"])
            with tab1:
                _render_sentiment_tab()
            with tab2:
                _render_news_tab_fragment()
            with tab3:
                _render_onchain_tab_fragment()


def render_main(view_model, actions):
    """主渲染函数"""
    # 注意: set_page_config 已在 app.py 中调用，此处不再重复调用
    # 否则会导致 StreamlitAPIException: set_page_config() can only be called once
    
    # 使用 @st.fragment 局部刷新，避免整个页面重绘
    # 实盘监控卡片和 K线图各自独立刷新，互不影响
    
    # 确保必要的session_state变量存在
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    # Bootstrap: 从后端一次性获取初始化数据并写session_state
    try:
        bootstrap = actions.get('get_bootstrap_state', lambda: {})()
        if bootstrap is None:
            bootstrap = {}
        # 使用与顶部定义一致的映射
        db_run_mode = bootstrap.get('run_mode', 'paper')
        if db_run_mode:
            st.session_state.env_mode = RUN_MODE_DB_TO_UI.get(db_run_mode, '🛰实盘测试')
        # selected strategy: validate and fallback
        from strategies.strategy_registry import validate_and_fallback_strategy
        db_strategy_id = bootstrap.get('selected_strategy_id')
        valid_strategy_id = validate_and_fallback_strategy(db_strategy_id)
        st.session_state.selected_strategy_id = valid_strategy_id
        st.session_state.strategy_module = valid_strategy_id  # 兼容旧代码
        # paper balance
        st.session_state.paper_balance = bootstrap.get('paper_balance', {'equity': None, 'available': None})
        # credential status
        cred = actions.get('get_credentials_status', lambda: {'okx_bound': False, 'okx_key_tail': None})()
        st.session_state.okx_bound = cred.get('okx_bound', False)
        st.session_state.okx_key_tail = cred.get('okx_key_tail')
    except Exception:
        # ignore bootstrap errors and let UI function with defaults
        pass

    # 渲染登录页面
    render_login(view_model, actions)
    
    # 登录成功后显示入场动画
    if st.session_state.get("show_intro_animation", False):
        st.markdown("""
        <style>
        @keyframes fadeOut { 
            0% { opacity: 1; z-index: 999999; } 
            70% { opacity: 1; } 
            100% { opacity: 0; z-index: -1; visibility: hidden; pointer-events: none; } 
        }
        @keyframes textShine { 
            0% { background-position: 0% 50%; } 
            100% { background-position: 100% 50%; } 
        }
        @keyframes slideUp {
            0% { transform: translateY(30px); opacity: 0; }
            100% { transform: translateY(0); opacity: 1; }
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.05); }
        }
        #intro-overlay-main { 
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100vw; 
            height: 100vh; 
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #0a0a0a 100%);
            display: flex; 
            flex-direction: column;
            justify-content: center; 
            align-items: center; 
            animation: fadeOut 3s forwards; 
            z-index: 999999; 
        }
        .intro-text-main { 
            font-size: 72px; 
            font-weight: 900; 
            background: linear-gradient(90deg, #ff6b6b, #feca57, #48dbfb, #ff9ff3, #ff6b6b); 
            background-size: 400% auto; 
            color: transparent; 
            -webkit-background-clip: text; 
            background-clip: text; 
            animation: textShine 3s linear infinite, pulse 2s ease-in-out infinite; 
            letter-spacing: 12px;
            text-shadow: 0 0 30px rgba(255, 107, 107, 0.5);
        }
        .intro-sub-main { 
            margin-top: 30px; 
            font-size: 18px; 
            color: #888 !important; 
            text-align: center; 
            font-family: 'Courier New', monospace; 
            letter-spacing: 4px;
            animation: slideUp 1s ease-out 0.5s both;
        }
        .intro-icon {
            font-size: 48px;
            margin-bottom: 20px;
            animation: slideUp 0.8s ease-out both;
        }
        .intro-line {
            width: 100px;
            height: 2px;
            background: linear-gradient(90deg, transparent, #ff6b6b, transparent);
            margin: 20px 0;
            animation: slideUp 1.2s ease-out 0.3s both;
        }
        </style>
        <div id="intro-overlay-main">
            <div class="intro-icon">⚡</div>
            <div class="intro-line"></div>
            <div class="intro-text-main">何以为势</div>
            <div class="intro-line"></div>
            <div class="intro-sub-main">TRADING SYSTEM ACTIVATED</div>
        </div>
        """, unsafe_allow_html=True)
        # 清除标志，只显示一次
        st.session_state.show_intro_animation = False
    
    # 注入抖音风格CSS
    try:
        with open('assets/theme_tiktok.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"CSS文件加载失败: {e}")
    
    # 🌸 樱花飘落粒子效果（斜向飘落，柔和发光）
    st.markdown("""
    <style>
    /* 樱花容器 */
    .sakura-container {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: 0;
        overflow: hidden;
    }
    
    /* 樱花花瓣 - 真实花瓣形状 + 柔和发光 */
    .sakura {
        position: absolute;
        top: -30px;
        width: 12px;
        height: 12px;
        background: linear-gradient(135deg, #ffc0cb 0%, #ffb6c1 40%, #ff69b4 100%);
        border-radius: 50% 0 50% 50%;
        box-shadow: 0 0 8px rgba(255, 182, 193, 0.6), 0 0 15px rgba(255, 105, 180, 0.3);
        opacity: 0.35;
        animation: sakura-drift linear infinite;
    }
    
    /* 第二层花瓣 - 更小更淡 */
    .sakura::before {
        content: '';
        position: absolute;
        top: 2px;
        left: 2px;
        width: 60%;
        height: 60%;
        background: rgba(255, 255, 255, 0.4);
        border-radius: 50% 0 50% 50%;
    }
    
    /* 斜向飘落 + 旋转 + 摇摆 */
    @keyframes sakura-drift {
        0% {
            transform: translateY(0) translateX(0) rotate(0deg);
            opacity: 0;
        }
        5% {
            opacity: 0.35;
        }
        25% {
            transform: translateY(25vh) translateX(8vw) rotate(90deg);
        }
        50% {
            transform: translateY(50vh) translateX(15vw) rotate(180deg);
            opacity: 0.3;
        }
        75% {
            transform: translateY(75vh) translateX(22vw) rotate(270deg);
        }
        95% {
            opacity: 0.2;
        }
        100% {
            transform: translateY(105vh) translateX(30vw) rotate(360deg);
            opacity: 0;
        }
    }
    
    /* 25片樱花 - 错落分布 */
    .sakura:nth-child(1) { left: 2%; width: 10px; height: 10px; animation-duration: 15s; animation-delay: 0s; }
    .sakura:nth-child(2) { left: 10%; width: 8px; height: 8px; animation-duration: 18s; animation-delay: 2s; opacity: 0.3; }
    .sakura:nth-child(3) { left: 18%; width: 12px; height: 12px; animation-duration: 14s; animation-delay: 4s; }
    .sakura:nth-child(4) { left: 26%; width: 9px; height: 9px; animation-duration: 17s; animation-delay: 1s; opacity: 0.25; }
    .sakura:nth-child(5) { left: 34%; width: 11px; height: 11px; animation-duration: 16s; animation-delay: 3s; }
    .sakura:nth-child(6) { left: 42%; width: 7px; height: 7px; animation-duration: 19s; animation-delay: 5s; opacity: 0.28; }
    .sakura:nth-child(7) { left: 50%; width: 10px; height: 10px; animation-duration: 15s; animation-delay: 6s; }
    .sakura:nth-child(8) { left: 58%; width: 8px; height: 8px; animation-duration: 18s; animation-delay: 7s; opacity: 0.32; }
    .sakura:nth-child(9) { left: 66%; width: 13px; height: 13px; animation-duration: 14s; animation-delay: 8s; }
    .sakura:nth-child(10) { left: 74%; width: 9px; height: 9px; animation-duration: 17s; animation-delay: 9s; opacity: 0.26; }
    .sakura:nth-child(11) { left: 82%; width: 11px; height: 11px; animation-duration: 16s; animation-delay: 10s; }
    .sakura:nth-child(12) { left: 90%; width: 8px; height: 8px; animation-duration: 19s; animation-delay: 11s; opacity: 0.3; }
    .sakura:nth-child(13) { left: 6%; width: 10px; height: 10px; animation-duration: 20s; animation-delay: 12s; }
    .sakura:nth-child(14) { left: 22%; width: 7px; height: 7px; animation-duration: 16s; animation-delay: 13s; opacity: 0.28; }
    .sakura:nth-child(15) { left: 38%; width: 12px; height: 12px; animation-duration: 15s; animation-delay: 14s; }
    .sakura:nth-child(16) { left: 54%; width: 9px; height: 9px; animation-duration: 18s; animation-delay: 15s; opacity: 0.32; }
    .sakura:nth-child(17) { left: 70%; width: 10px; height: 10px; animation-duration: 17s; animation-delay: 16s; }
    .sakura:nth-child(18) { left: 86%; width: 8px; height: 8px; animation-duration: 14s; animation-delay: 17s; opacity: 0.25; }
    .sakura:nth-child(19) { left: 14%; width: 11px; height: 11px; animation-duration: 19s; animation-delay: 18s; }
    .sakura:nth-child(20) { left: 30%; width: 9px; height: 9px; animation-duration: 16s; animation-delay: 19s; opacity: 0.3; }
    .sakura:nth-child(21) { left: 46%; width: 10px; height: 10px; animation-duration: 15s; animation-delay: 20s; }
    .sakura:nth-child(22) { left: 62%; width: 7px; height: 7px; animation-duration: 18s; animation-delay: 21s; opacity: 0.28; }
    .sakura:nth-child(23) { left: 78%; width: 12px; height: 12px; animation-duration: 17s; animation-delay: 22s; }
    .sakura:nth-child(24) { left: 94%; width: 8px; height: 8px; animation-duration: 14s; animation-delay: 23s; opacity: 0.32; }
    .sakura:nth-child(25) { left: 4%; width: 9px; height: 9px; animation-duration: 20s; animation-delay: 24s; }
    </style>
    
    <!-- 樱花花瓣 -->
    <div class="sakura-container">
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div><div class="sakura"></div><div class="sakura"></div>
        <div class="sakura"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # 渲染侧边栏
    render_sidebar(view_model, actions)
    
    # 渲染主仪表盘
    render_dashboard(view_model, actions)



