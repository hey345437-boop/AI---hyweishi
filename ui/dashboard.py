# -*- coding: utf-8 -*-
# ============================================================================
#
#    _   _  __   __ __        __  _____ ___  ____   _   _  ___ 
#   | | | | \\ \\ / / \\ \\      / / | ____||_ _|/ ___| | | | ||_ _|
#   | |_| |  \\ V /   \\ \\ /\\ / /  |  _|   | | \\___ \\ | |_| | | | 
#   |  _  |   | |     \\ V  V /   | |___  | |  ___) ||  _  | | | 
#   |_| |_|   |_|      \\_/\\_/    |_____||___||____/ |_| |_||___|
#
#                         何 以 为 势
#                  Quantitative Trading System
#
#   Copyright (c) 2024-2025 HyWeiShi. All Rights Reserved.
#   License: AGPL-3.0
#
# ============================================================================
import streamlit as st
import time
import json
import pandas as pd
from datetime import datetime
import plotly.graph_objects as go

# å¯¼å¥é¡¹ç®æ¨¡å
from database.db_bridge import (
    get_engine_status, get_control_flags, get_bot_config,
    get_recent_performance_metrics, init_db,
    load_ohlcv, load_signals,
    get_paper_balance, get_paper_positions,
    update_control_flags, update_bot_config
)

def load_ohlcv_from_db(symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """ä»æ°æ®åºå è½½OHLCVæ°æ®å¹¶è½¬æ¢ä¸ºDataFrame
    
    Args:
        symbol: äº¤æå¯¹ç¬¦å?        timeframe: æ¶é´å¨æ
        limit: å è½½çæ°ééå?        
    Returns:
        pd.DataFrame: OHLCVæ°æ®DataFrame
    """
    ohlcv_data = load_ohlcv(symbol, timeframe, limit)
    if not ohlcv_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlcv_data, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df


def load_signals_from_db(symbol: str, timeframe: str, ts_from: int = None) -> pd.DataFrame:
    """ä»æ°æ®åºå è½½ä¿¡å·äºä»¶å¹¶è½¬æ¢ä¸ºDataFrame
    
    Args:
        symbol: äº¤æå¯¹ç¬¦å?        timeframe: æ¶é´å¨æ
        ts_from: èµ·å§æ¶é´æ³ï¼æ¯«ç§ï¼ï¼å¦æä¸ºNoneåå è½½ææ?        
    Returns:
        pd.DataFrame: ä¿¡å·äºä»¶DataFrame
    """
    signals = load_signals(symbol, timeframe, ts_from)
    if not signals:
        return pd.DataFrame()
    
    df = pd.DataFrame(signals)
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    return df


def build_candlestick_fig(df_ohlcv: pd.DataFrame, df_signals: pd.DataFrame) -> go.Figure:
    """æå»ºè¡çå¾åä¿¡å·ç¹çPlotlyå¾è¡¨
    
    Args:
        df_ohlcv: OHLCVæ°æ®DataFrame
        df_signals: ä¿¡å·äºä»¶DataFrame
        
    Returns:
        go.Figure: Plotlyå¾è¡¨å¯¹è±¡
    """
    fig = go.Figure()
    
    # ç»å¶Kçº¿å¾
    fig.add_trace(go.Candlestick(
        x=df_ohlcv.index,
        open=df_ohlcv['open'],
        high=df_ohlcv['high'],
        low=df_ohlcv['low'],
        close=df_ohlcv['close'],
        name='Kçº?,
        increasing_line_color='green',
        decreasing_line_color='red',
        increasing_fillcolor='rgba(0, 255, 0, 0.3)',
        decreasing_fillcolor='rgba(255, 0, 0, 0.3)'
    ))
    
    # å å BUYä¿¡å·ç?    if not df_signals.empty and 'signal_type' in df_signals.columns:
        buy_signals = df_signals[df_signals['signal_type'] == 'BUY']
        if not buy_signals.empty:
            fig.add_trace(go.Scatter(
                x=buy_signals['ts'],
                y=buy_signals['price'],
                mode='markers',
                marker=dict(
                    symbol='triangle-up',
                    color='green',
                    size=10,
                    line=dict(width=2, color='white')
                ),
                name='BUY',
                hovertemplate='<b>BUYä¿¡å·</b><br>æ¶é´: %{x}<br>ä»·æ ¼: %{y}<br>åå : %{customdata[0]}<extra></extra>',
                customdata=buy_signals[['reason']].fillna('æ?)
            ))
        
        # å å SELLä¿¡å·ç?        sell_signals = df_signals[df_signals['signal_type'] == 'SELL']
        if not sell_signals.empty:
            fig.add_trace(go.Scatter(
                x=sell_signals['ts'],
                y=sell_signals['price'],
                mode='markers',
                marker=dict(
                    symbol='triangle-down',
                    color='red',
                    size=10,
                    line=dict(width=2, color='white')
                ),
                name='SELL',
                hovertemplate='<b>SELLä¿¡å·</b><br>æ¶é´: %{x}<br>ä»·æ ¼: %{y}<br>åå : %{customdata[0]}<extra></extra>',
                customdata=sell_signals[['reason']].fillna('æ?)
            ))
        
        # å å EXITä¿¡å·ç?        exit_signals = df_signals[df_signals['signal_type'] == 'EXIT']
        if not exit_signals.empty:
            fig.add_trace(go.Scatter(
                x=exit_signals['ts'],
                y=exit_signals['price'],
                mode='markers',
                marker=dict(
                    symbol='x',
                    color='yellow',
                    size=10,
                    line=dict(width=2, color='white')
                ),
                name='EXIT',
                hovertemplate='<b>EXITä¿¡å·</b><br>æ¶é´: %{x}<br>ä»·æ ¼: %{y}<br>åå : %{customdata[0]}<extra></extra>',
                customdata=exit_signals[['reason']].fillna('æ?)
            ))
    
    # éç½®å¾è¡¨å¸å±
    fig.update_layout(
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=40, b=20),
        height=700,
        title='Kçº¿å¾ä¸äº¤æä¿¡å?,
        xaxis_title='æ¶é´',
        yaxis_title='ä»·æ ¼',
        plot_bgcolor='#0F1115',
        paper_bgcolor='#0F1115',
        font=dict(color='#E6E6E6'),
        legend=dict(
            bgcolor='#151823',
            bordercolor='#333',
            borderwidth=1
        )
    )
    
    # éç½®åæ è½?    fig.update_xaxes(
        gridcolor='#222',
        showline=True,
        linecolor='#444',
        linewidth=2,
        ticks='inside'
    )
    
    fig.update_yaxes(
        gridcolor='#222',
        showline=True,
        linecolor='#444',
        linewidth=2,
        ticks='inside',
        side='right'
    )
    
    return fig

def main():
    """ä»ªè¡¨çä¸»å½æ°"""
    st.set_page_config(
        page_title="äº¤æç³»ç»ä»ªè¡¨ç?,
        page_icon="ð",
        layout="wide"
    )
    
    # æ³¨å¥CSSæ ·å¼ï¼ç¡®ä¿æ·±è²ä¸»é¢?    st.markdown("""
        <style>
        /* å¨å±æ ·å¼ */
        body {
            background-color: #0F1115;
            color: #E6E6E6;
        }
        
        /* Streamlitå®¹å¨æ ·å¼ */
        .stApp {
            background-color: #0F1115;
        }
        
        /* æ é¢æ ·å¼ */
        h1, h2, h3, h4, h5, h6 {
            color: #E6E6E6 !important;
            background-color: transparent !important;
        }
        
        /* å¡çæ ·å¼ */
        .stMetric {
            background-color: #151823;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 10px;
        }
        
        /* ç»å¸å®¹å¨æ ·å¼ */
        .tiktok-canvas-container {
            background-color: #151823;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # åå§åæ°æ®åº
    init_db()
    
    st.title("äº¤æç³»ç»ä»ªè¡¨ç?)
    
    # è·åææ°æ°æ?    engine_status = get_engine_status()
    control_flags = get_control_flags()
    bot_config = get_bot_config()
    
    # ä¾§è¾¹æ ?- è¿è¡æ¨¡å¼éæ©
    st.sidebar.header("è¿è¡æ¨¡å¼")
    run_mode_options = ["æ¨¡æ", "å®çæµè¯", "å®ç"]
    run_mode_map_ui_to_db = {"æ¨¡æ": "sim", "å®çæµè¯": "paper", "å®ç": "live"}
    run_mode_map_db_to_ui = {v: k for k, v in run_mode_map_ui_to_db.items()}
    
    # è·åå½åDBä¸­çrun_mode
    current_run_mode_db = bot_config.get("run_mode", "sim")
    current_run_mode_ui = run_mode_map_db_to_ui.get(current_run_mode_db, "æ¨¡æ")
    
    # åå»ºéæ©æ¡?    selected_run_mode = st.sidebar.selectbox(
        "éæ©è¿è¡æ¨¡å¼",
        run_mode_options,
        index=run_mode_options.index(current_run_mode_ui)
    )
    
    # å¦æç¨æ·éæ©äºä¸åçæ¨¡å¼ï¼æ´æ°å°DB
    if run_mode_map_ui_to_db[selected_run_mode] != current_run_mode_db:
        from database.db_bridge import update_bot_config, set_control_flags
        update_bot_config(run_mode=run_mode_map_ui_to_db[selected_run_mode])
        set_control_flags(reload_config=1)
        st.rerun()
    recent_metrics = get_recent_performance_metrics(limit=100)
    
    # ç³»ç»æ¦è§å¡ç
    st.header("ç³»ç»æ¦è§")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        status = "â?æ´»è·" if engine_status.get("alive") == 1 else "â?åæ­¢"
        st.metric("è¿è¡ç¶æ?, status)
    
    with col2:
        # ç»ä¸ä½¿ç¨DBçbot_config.run_modeä½ä¸ºå¯ä¸æ°æ®æº?        mode = bot_config.get("run_mode", "æªç¥")
        mode_map = {
            "sim": "æ¨¡æ",
            "paper": "å®çæµè¯",
            "live": "å®ç"
        }
        display_mode = mode_map.get(mode, mode)
        st.metric("äº¤ææ¨¡å¼", display_mode)
    
    with col3:
        pause_status = "â¸ï¸ å·²æå? if engine_status.get("pause_trading") == 1 or control_flags.get("pause_trading") == 1 else "â¶ï¸ è¿è¡ä¸?
        st.metric("äº¤æç¶æ?, pause_status)
    
    with col4:
        allow_live_status = "â?åè®¸" if control_flags.get("allow_live", 0) == 1 else "â?ç¦æ­¢"
        st.metric("åè®¸LIVEä¸å", allow_live_status)
    
    with col5:
        if engine_status.get("alive") == 1 and engine_status.get("ts"):
            last_heartbeat = datetime.fromtimestamp(engine_status.get("ts") / 1000)
            st.metric("æåå¿è·?, last_heartbeat.strftime("%H:%M:%S"))
        else:
            st.metric("æåå¿è·?, "-" if not engine_status.get("ts") else datetime.fromtimestamp(engine_status.get("ts") / 1000).strftime("%H:%M:%S"))
    
    # æ§è½ææ å¾è¡¨
    st.header("æ§è½ææ ")
    
    if recent_metrics:
        df = pd.DataFrame(recent_metrics)
        df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('timestamp')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("å¾ªç¯èæ¶")
            if 'cycle_ms' in df.columns:
                st.line_chart(df['cycle_ms'])
            else:
                st.info("ææ å¾ªç¯èæ¶æ°æ®")
        
        with col2:
            st.subheader("APIè°ç¨æ¬¡æ°")
            if 'api_calls' in df.columns:
                st.line_chart(df['api_calls'])
            else:
                st.info("ææ APIè°ç¨æ¬¡æ°æ°æ®")
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("APIå¹³åå»¶è¿")
            if 'avg_api_latency_ms' in df.columns:
                st.line_chart(df['avg_api_latency_ms'])
            else:
                st.info("ææ APIå¹³åå»¶è¿æ°æ®")
        
        with col4:
            st.subheader("ç¼å­å½ä¸­ç?)
            if 'cache_hit_rate' in df.columns:
                st.line_chart(df['cache_hit_rate'] * 100)
            else:
                st.info("ææ ç¼å­å½ä¸­çæ°æ?)
        
        # æ§è½ç»è®¡
        st.subheader("æ§è½ç»è®¡")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'cycle_ms' in df.columns:
                avg_cycle = df['cycle_ms'].mean()
                st.metric("å¹³åå¾ªç¯èæ¶", f"{avg_cycle:.0f} ms")
            else:
                st.metric("å¹³åå¾ªç¯èæ¶", "- ms")
        
        with col2:
            if 'api_calls' in df.columns:
                avg_api_calls = df['api_calls'].mean()
                st.metric("å¹³åAPIè°ç¨", f"{avg_api_calls:.1f} æ¬?)
            else:
                st.metric("å¹³åAPIè°ç¨", "- æ¬?)
        
        with col3:
            if 'cache_hit_rate' in df.columns:
                avg_cache_hit = df['cache_hit_rate'].mean() * 100
                st.metric("å¹³åç¼å­å½ä¸­ç?, f"{avg_cache_hit:.1f}%")
            else:
                st.metric("å¹³åç¼å­å½ä¸­ç?, "-%")
        
        with col4:
            if 'errors' in df.columns:
                total_errors = df['errors'].sum()
                st.metric("æ»éè¯¯æ°", f"{total_errors}")
            else:
                st.metric("æ»éè¯¯æ°", "-")
    else:
        st.info("ææ æ§è½ææ æ°æ®")
    
    # Kçº¿å¾è¡¨æ¾ç¤ºåºå?    st.header("Kçº¿å¾ä¸äº¤æä¿¡å?)
    
    # è·åå½åäº¤æå¯¹åæ¶é´å¨æ
    symbols = bot_config.get("symbols", "")
    if symbols:
        # ä½¿ç¨ç¬¬ä¸ä¸ªäº¤æå¯¹ä½ä¸ºé»è®¤æ¾ç¤º
        default_symbol = symbols.split(",")[0].strip()
        timeframe = "1m"  # é»è®¤ä½¿ç¨1åéKçº?        
        # ä»æ°æ®åºå è½½OHLCVæ°æ®åä¿¡å?        df_ohlcv = load_ohlcv_from_db(default_symbol, timeframe, limit=200)
        df_signals = load_signals_from_db(default_symbol, timeframe)
        
        if not df_ohlcv.empty:
            # æå»ºå¾è¡¨
            fig = build_candlestick_fig(df_ohlcv, df_signals)
            # æ°å¢ï¼è®¾ç½®å¾è¡¨é«åº¦ä¸º 600
            fig.update_layout(height=600)
            
            # å¨ä¸­é´å¤§ç»å¸åºåæ¾ç¤ºå¾è¡¨
            st.markdown('<div class="tiktok-canvas-container">', unsafe_allow_html=True)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)
            # æ°å¢ï¼æ¾ç¤ºæ°æ®ç»è®?            st.caption(f"ð Kçº¿æ°æ? {len(df_ohlcv)} æ? ææ? {df_ohlcv.index[-1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(df_ohlcv.index[-1], 'strftime') else df_ohlcv.index[-1]}")
        else:
            # æ°å¢ï¼æ°æ®ä¸ºç©ºæ¶èªå¨æå
            st.warning(f"ð {default_symbol} çKçº¿ä¸ºç©ºï¼æ­£å¨æå...")
            try:
                from database.db_bridge import fetch_and_cache_ohlcv
                result = fetch_and_cache_ohlcv(default_symbol, timeframe, limit=200)
                if result.get('ok'):
                    st.success(f"â?æåæå {result.get('rows', 0)} æ¡Kçº?)
                    # éæ°å è½½æ°æ®
                    df_ohlcv = load_ohlcv_from_db(default_symbol, timeframe, limit=200)
                    if not df_ohlcv.empty:
                        df_signals = load_signals_from_db(default_symbol, timeframe)
                        fig = build_candlestick_fig(df_ohlcv, df_signals)
                        fig.update_layout(height=600)
                        st.markdown('<div class="tiktok-canvas-container">', unsafe_allow_html=True)
                        st.plotly_chart(fig, width="stretch")
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.caption(f"ð Kçº¿æ°æ? {len(df_ohlcv)} æ? ææ? {df_ohlcv.index[-1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(df_ohlcv.index[-1], 'strftime') else df_ohlcv.index[-1]}")
                else:
                    st.error(f"â?Kçº¿æåå¤±è´? {result.get('error', 'æªç¥éè¯¯')[:100]}")
                    st.info(f"ð¡ è¯·ç¡®ä¿äº¤ææ± å·²éç½®ï¼API å·²ç»å®ï¼ä¸äº¤æå¼ææ­£å¨è¿è¡?)
            except Exception as e:
                st.error(f"â?Kçº¿æåå¼å¸? {str(e)[:100]}")
                st.info(f"ææ  {default_symbol} çKçº¿æ°æ®ï¼è¯·ç¡®ä¿äº¤æå¼æå·²å¯å¨å¹¶æ­£å¸¸è¿è¡?)
    else:
        st.info("è¯·åéç½®äº¤ææ± ï¼æ·»å äº¤æå¯?)
    
    # å½åéç½®åç¶æ?    st.header("å½åéç½®")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("è¿è¡éç½®")
        
        config_data = {
            "è¿è¡æ¨¡å¼": {"sim": "æ¨¡æ", "paper": "å®çæµè¯", "live": "å®ç"}.get(bot_config.get("run_mode"), bot_config.get("run_mode")),
            "äº¤ææ±?: bot_config.get("symbols", ""),
            "åºç¡ä»ä½": f"{bot_config.get('position_size', 0):.3f}",
            "äº¤æç¶æ?: "å¯ç¨" if bot_config.get("enable_trading") == 1 else "ç¦ç¨"
        }
        
        for key, value in config_data.items():
            st.text(f"{key}: {value}")
    
    with col2:
        st.subheader("æ§å¶æ å¿")
        
        control_data = {
            "åæ­¢ä¿¡å·": "å·²åé? if control_flags.get("stop_signal") == 1 else "æªåé?,
            "æåäº¤æ": "å·²æå? if control_flags.get("pause_trading") == 1 else "è¿è¡ä¸?,
            "éè½½éç½®": "éè¦éè½? if control_flags.get("reload_config") == 1 else "æ ééè½½",
            "åè®¸LIVE": "åè®¸" if control_flags.get("allow_live") == 1 else "ç¦æ­¢",
            "ç´§æ¥å¹³ä»?: "å·²è§¦å? if control_flags.get("emergency_flatten") == 1 else "æªè§¦å?
        }
        
        for key, value in control_data.items():
            st.text(f"{key}: {value}")

    # äº¤ææ§å¶æé®
    st.header("äº¤ææ§å¶")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("ä¸é®å¯å¨äº¤æ?, type="primary"):
            # è®¾ç½®enable_trading=1ï¼pause_trading=0
            update_bot_config({"enable_trading": 1})
            update_control_flags({"pause_trading": 0})
            st.success("äº¤æå·²å¯å¨ï¼")
            # éæ°å è½½æ°æ®ä»¥æ´æ°UI
            st.experimental_rerun()
    
    with col2:
        if st.button("æåäº¤æ"):
            # è®¾ç½®pause_trading=1
            update_control_flags({"pause_trading": 1})
            st.warning("äº¤æå·²æåï¼")
            # éæ°å è½½æ°æ®ä»¥æ´æ°UI
            st.experimental_rerun()
    
    with col3:
        if st.button("æ¢å¤äº¤æ"):
            # è®¾ç½®pause_trading=0
            update_control_flags({"pause_trading": 0})
            st.success("äº¤æå·²æ¢å¤ï¼")
            # éæ°å è½½æ°æ®ä»¥æ´æ°UI
            st.experimental_rerun()
    
    # æè¿è®¡åè®¢å?    st.header("æè¿è®¡åè®¢å?)
    
    if engine_status.get("last_plan_order_json"):
        try:
            plan_order = json.loads(engine_status.get("last_plan_order_json"))
            if plan_order:
                st.json(plan_order)
            else:
                st.info("ææ è®¡åè®¢å")
        except json.JSONDecodeError:
            st.error("è®¡åè®¢åè§£æå¤±è´¥")
    else:
        st.info("ææ è®¡åè®¢å")
    
    # å½åæä»
    st.header("å½åæä»")
    
    # æ ¹æ®è¿è¡æ¨¡å¼æ¾ç¤ºä¸åçæä»æ°æ?    current_run_mode_db = bot_config.get("run_mode", "sim")
    
    if current_run_mode_db == "paper":
        # æ¾ç¤ºå®çæµè¯æ¨¡å¼çæ¨¡ææä»?        paper_positions = get_paper_positions()
        paper_balance = get_paper_balance()
        
        # æ¾ç¤ºæ¨¡æä½é¢
        if paper_balance:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("æ¨¡æä½é¢ (USDT)", f"{paper_balance.get('equity', 0):.2f}")
            with col2:
                st.metric("å¯ç¨ä½é¢ (USDT)", f"{paper_balance.get('available', 0):.2f}")
        
        # æ¾ç¤ºæ¨¡ææä»
        if paper_positions:
            # åå»ºDataFrameæ¥æ´ç¾è§å°æ¾ç¤ºæä»?            positions_df = pd.DataFrame(paper_positions)
            st.dataframe(positions_df, width="stretch")
        else:
            st.info("ææ å®çæµè¯æä»")
    else:
        # æ¾ç¤ºå¶ä»æ¨¡å¼çæä»?        if engine_status.get("positions_json"):
            try:
                positions = json.loads(engine_status.get("positions_json"))
                if positions:
                    st.json(positions)
                else:
                    st.info("ææ æä»")
            except json.JSONDecodeError:
                st.error("æä»æ°æ®è§£æå¤±è´¥")
        else:
            st.info("ææ æä»")
    
    # èªå¨å·æ°æ§å¶
    auto_refresh = st.checkbox("èªå¨å·æ°", value=True)
    refresh_interval = st.slider("å·æ°é´é(ç§?", min_value=1, max_value=10, value=2)
    
    # å·æ°æé®
    if st.button("å·æ°æ°æ®"):
        st.rerun()
    
    # èªå¨å·æ°é»è¾
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
