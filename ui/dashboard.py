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

# 导入项目模块
from database.db_bridge import (
    get_engine_status, get_control_flags, get_bot_config,
    get_recent_performance_metrics, init_db,
    load_ohlcv, load_signals,
    get_paper_balance, get_paper_positions,
    set_control_flags, update_bot_config
)

def load_ohlcv_from_db(symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """从数据库加载OHLCV数据并转换为DataFrame
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        limit: 加载的数量限制
        
    Returns:
        pd.DataFrame: OHLCV数据DataFrame
    """
    ohlcv_data = load_ohlcv(symbol, timeframe, limit)
    if not ohlcv_data:
        return pd.DataFrame()
    
    df = pd.DataFrame(ohlcv_data, columns=['ts', 'open', 'high', 'low', 'close', 'volume'])
    df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    df.set_index('ts', inplace=True)
    return df


def load_signals_from_db(symbol: str, timeframe: str, ts_from: int = None) -> pd.DataFrame:
    """从数据库加载信号事件并转换为DataFrame
    
    Args:
        symbol: 交易对符号
        timeframe: 时间周期
        ts_from: 起始时间戳（毫秒），如果为None则加载所有
        
    Returns:
        pd.DataFrame: 信号事件DataFrame
    """
    signals = load_signals(symbol, timeframe, ts_from)
    if not signals:
        return pd.DataFrame()
    
    df = pd.DataFrame(signals)
    if 'ts' in df.columns:
        df['ts'] = pd.to_datetime(df['ts'], unit='ms')
    return df


def build_candlestick_fig(df_ohlcv: pd.DataFrame, df_signals: pd.DataFrame) -> go.Figure:
    """构建蜡烛图和信号点的Plotly图表
    
    Args:
        df_ohlcv: OHLCV数据DataFrame
        df_signals: 信号事件DataFrame
        
    Returns:
        go.Figure: Plotly图表对象
    """
    fig = go.Figure()
    
    # 绘制K线图
    fig.add_trace(go.Candlestick(
        x=df_ohlcv.index,
        open=df_ohlcv['open'],
        high=df_ohlcv['high'],
        low=df_ohlcv['low'],
        close=df_ohlcv['close'],
        name='K线',
        increasing_line_color='green',
        decreasing_line_color='red',
        increasing_fillcolor='rgba(0, 255, 0, 0.3)',
        decreasing_fillcolor='rgba(255, 0, 0, 0.3)'
    ))
    
    # 添加 BUY 信号点
    if not df_signals.empty and 'signal_type' in df_signals.columns:
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
                hovertemplate='<b>BUY信号</b><br>时间: %{x}<br>价格: %{y}<br>原因: %{customdata[0]}<extra></extra>',
                customdata=buy_signals[['reason']].fillna('无')
            ))
        
        # 添加 SELL 信号点
        sell_signals = df_signals[df_signals['signal_type'] == 'SELL']
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
                hovertemplate='<b>SELL信号</b><br>时间: %{x}<br>价格: %{y}<br>原因: %{customdata[0]}<extra></extra>',
                customdata=sell_signals[['reason']].fillna('无')
            ))
        
        # 添加 EXIT 信号点
        exit_signals = df_signals[df_signals['signal_type'] == 'EXIT']
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
                hovertemplate='<b>EXIT信号</b><br>时间: %{x}<br>价格: %{y}<br>原因: %{customdata[0]}<extra></extra>',
                customdata=exit_signals[['reason']].fillna('无')
            ))
    
    # 配置图表布局
    fig.update_layout(
        template='plotly_dark',
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=40, b=20),
        height=700,
        title='K线图与交易信号',
        xaxis_title='时间',
        yaxis_title='价格',
        plot_bgcolor='#0F1115',
        paper_bgcolor='#0F1115',
        font=dict(color='#E6E6E6'),
        legend=dict(
            bgcolor='#151823',
            bordercolor='#333',
            borderwidth=1
        )
    )
    
    # 配置坐标轴
    fig.update_xaxes(
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
    """仪表盘主函数"""
    st.set_page_config(
        page_title="交易系统仪表盘",
        page_icon="📊",
        layout="wide"
    )
    
    # 注入CSS样式，确保深色主题
    st.markdown("""
        <style>
        /* 全局样式 */
        body {
            background-color: #0F1115;
            color: #E6E6E6;
        }
        
        /* Streamlit容器样式 */
        .stApp {
            background-color: #0F1115;
        }
        
        /* 标题样式 */
        h1, h2, h3, h4, h5, h6 {
            color: #E6E6E6 !important;
            background-color: transparent !important;
        }
        
        /* 卡片样式 */
        .stMetric {
            background-color: #151823;
            border: 1px solid #333;
            border-radius: 8px;
            padding: 10px;
        }
        
        /* 画布容器样式 */
        .tiktok-canvas-container {
            background-color: #151823;
            border-radius: 8px;
            padding: 10px;
            margin: 10px 0;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # 初始化数据库
    init_db()
    
    st.title("交易系统仪表盘")
    
    # 获取最新数据
    engine_status = get_engine_status()
    control_flags = get_control_flags()
    bot_config = get_bot_config()
    
    # 侧边栏 - 运行模式选择
    st.sidebar.header("运行模式")
    run_mode_options = ["模拟", "实盘测试", "实盘"]
    run_mode_map_ui_to_db = {"模拟": "sim", "实盘测试": "paper", "实盘": "live"}
    run_mode_map_db_to_ui = {v: k for k, v in run_mode_map_ui_to_db.items()}
    
    # 获取当前DB中的run_mode
    current_run_mode_db = bot_config.get("run_mode", "sim")
    current_run_mode_ui = run_mode_map_db_to_ui.get(current_run_mode_db, "模拟")
    
    # 创建选择框
    selected_run_mode = st.sidebar.selectbox(
        "选择运行模式",
        run_mode_options,
        index=run_mode_options.index(current_run_mode_ui)
    )
    
    # 如果用户选择了不同的模式，更新到DB
    if run_mode_map_ui_to_db[selected_run_mode] != current_run_mode_db:
        from database.db_bridge import update_bot_config, set_control_flags
        update_bot_config(run_mode=run_mode_map_ui_to_db[selected_run_mode])
        set_control_flags(reload_config=1)
        st.rerun()
    recent_metrics = get_recent_performance_metrics(limit=100)
    
    # 系统概览卡片
    st.header("系统概览")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        status = "✅ 活跃" if engine_status.get("alive") == 1 else "❌ 停止"
        st.metric("运行状态", status)
    
    with col2:
        # 统一使用DB的bot_config.run_mode作为唯一数据源
        mode = bot_config.get("run_mode", "未知")
        mode_map = {
            "sim": "模拟",
            "paper": "实盘测试",
            "live": "实盘"
        }
        display_mode = mode_map.get(mode, mode)
        st.metric("交易模式", display_mode)
    
    with col3:
        pause_status = "⏸️ 已暂停" if engine_status.get("pause_trading") == 1 or control_flags.get("pause_trading") == 1 else "▶️ 运行中"
        st.metric("交易状态", pause_status)
    
    with col4:
        allow_live_status = "✅ 允许" if control_flags.get("allow_live", 0) == 1 else "❌ 禁止"
        st.metric("允许LIVE下单", allow_live_status)
    
    with col5:
        if engine_status.get("alive") == 1 and engine_status.get("ts"):
            last_heartbeat = datetime.fromtimestamp(engine_status.get("ts") / 1000)
            st.metric("最后心跳", last_heartbeat.strftime("%H:%M:%S"))
        else:
            st.metric("最后心跳", "-" if not engine_status.get("ts") else datetime.fromtimestamp(engine_status.get("ts") / 1000).strftime("%H:%M:%S"))

    
    # 性能指标图表
    st.header("性能指标")
    
    if recent_metrics:
        df = pd.DataFrame(recent_metrics)
        df['timestamp'] = pd.to_datetime(df['ts'], unit='ms')
        df = df.set_index('timestamp')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("循环耗时")
            if 'cycle_ms' in df.columns:
                st.line_chart(df['cycle_ms'])
            else:
                st.info("暂无循环耗时数据")
        
        with col2:
            st.subheader("API调用次数")
            if 'api_calls' in df.columns:
                st.line_chart(df['api_calls'])
            else:
                st.info("暂无API调用次数数据")
        
        col3, col4 = st.columns(2)
        
        with col3:
            st.subheader("API平均延迟")
            if 'avg_api_latency_ms' in df.columns:
                st.line_chart(df['avg_api_latency_ms'])
            else:
                st.info("暂无API平均延迟数据")
        
        with col4:
            st.subheader("缓存命中率")
            if 'cache_hit_rate' in df.columns:
                st.line_chart(df['cache_hit_rate'] * 100)
            else:
                st.info("暂无缓存命中率数据")
        
        # 性能统计
        st.subheader("性能统计")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if 'cycle_ms' in df.columns:
                avg_cycle = df['cycle_ms'].mean()
                st.metric("平均循环耗时", f"{avg_cycle:.0f} ms")
            else:
                st.metric("平均循环耗时", "- ms")
        
        with col2:
            if 'api_calls' in df.columns:
                avg_api_calls = df['api_calls'].mean()
                st.metric("平均API调用", f"{avg_api_calls:.1f} 次")
            else:
                st.metric("平均API调用", "- 次")
        
        with col3:
            if 'cache_hit_rate' in df.columns:
                avg_cache_hit = df['cache_hit_rate'].mean() * 100
                st.metric("平均缓存命中率", f"{avg_cache_hit:.1f}%")
            else:
                st.metric("平均缓存命中率", "-%")
        
        with col4:
            if 'errors' in df.columns:
                total_errors = df['errors'].sum()
                st.metric("总错误数", f"{total_errors}")
            else:
                st.metric("总错误数", "-")
    else:
        st.info("暂无性能指标数据")

    
    # K线图表显示区域
    st.header("K线图与交易信号")
    
    # 获取当前交易对和时间周期
    symbols = bot_config.get("symbols", "")
    if symbols:
        # 使用第一个交易对作为默认显示
        default_symbol = symbols.split(",")[0].strip()
        timeframe = "1m"  # 默认使用1分钟K线
        
        # 从数据库加载OHLCV数据和信号
        df_ohlcv = load_ohlcv_from_db(default_symbol, timeframe, limit=200)
        df_signals = load_signals_from_db(default_symbol, timeframe)
        
        if not df_ohlcv.empty:
            # 构建图表
            fig = build_candlestick_fig(df_ohlcv, df_signals)
            # 设置图表高度为 600
            fig.update_layout(height=600)
            
            # 在中间大画布区域显示图表
            st.markdown('<div class="tiktok-canvas-container">', unsafe_allow_html=True)
            st.plotly_chart(fig, width="stretch")
            st.markdown('</div>', unsafe_allow_html=True)
            # 显示数据统计
            st.caption(f"📊 K线数据: {len(df_ohlcv)} 条 | 最新: {df_ohlcv.index[-1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(df_ohlcv.index[-1], 'strftime') else df_ohlcv.index[-1]}")
        else:
            # 数据为空时自动拉取
            st.warning(f"📉 {default_symbol} 的K线为空，正在拉取...")
            try:
                from database.db_bridge import fetch_and_cache_ohlcv
                result = fetch_and_cache_ohlcv(default_symbol, timeframe, limit=200)
                if result.get('ok'):
                    st.success(f"✅ 成功拉取 {result.get('rows', 0)} 条K线")
                    # 重新加载数据
                    df_ohlcv = load_ohlcv_from_db(default_symbol, timeframe, limit=200)
                    if not df_ohlcv.empty:
                        df_signals = load_signals_from_db(default_symbol, timeframe)
                        fig = build_candlestick_fig(df_ohlcv, df_signals)
                        fig.update_layout(height=600)
                        st.markdown('<div class="tiktok-canvas-container">', unsafe_allow_html=True)
                        st.plotly_chart(fig, width="stretch")
                        st.markdown('</div>', unsafe_allow_html=True)
                        st.caption(f"📊 K线数据: {len(df_ohlcv)} 条 | 最新: {df_ohlcv.index[-1].strftime('%Y-%m-%d %H:%M:%S') if hasattr(df_ohlcv.index[-1], 'strftime') else df_ohlcv.index[-1]}")
                else:
                    st.error(f"❌ K线拉取失败: {result.get('error', '未知错误')[:100]}")
                    st.info(f"💡 请确保交易所已配置，API 已绑定，且交易引擎正在运行")
            except Exception as e:
                st.error(f"❌ K线拉取异常: {str(e)[:100]}")
                st.info(f"暂无 {default_symbol} 的K线数据，请确保交易引擎已启动并正常运行")
    else:
        st.info("请先配置交易所，添加交易对")

    
    # 当前配置和状态
    st.header("当前配置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("运行配置")
        
        config_data = {
            "运行模式": {"sim": "模拟", "paper": "实盘测试", "live": "实盘"}.get(bot_config.get("run_mode"), bot_config.get("run_mode")),
            "交易所": bot_config.get("symbols", ""),
            "基础仓位": f"{bot_config.get('position_size', 0):.3f}",
            "交易状态": "启用" if bot_config.get("enable_trading") == 1 else "禁用"
        }
        
        for key, value in config_data.items():
            st.text(f"{key}: {value}")
    
    with col2:
        st.subheader("控制标志")
        
        control_data = {
            "停止信号": "已发送" if control_flags.get("stop_signal") == 1 else "未发送",
            "暂停交易": "已暂停" if control_flags.get("pause_trading") == 1 else "运行中",
            "重载配置": "需要重载" if control_flags.get("reload_config") == 1 else "无需重载",
            "允许LIVE": "允许" if control_flags.get("allow_live") == 1 else "禁止",
            "紧急平仓": "已触发" if control_flags.get("emergency_flatten") == 1 else "未触发"
        }
        
        for key, value in control_data.items():
            st.text(f"{key}: {value}")

    # 交易控制按钮
    st.header("交易控制")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("一键启动交易", type="primary"):
            # 设置enable_trading=1，pause_trading=0
            update_bot_config({"enable_trading": 1})
            update_control_flags({"pause_trading": 0})
            st.success("交易已启动！")
            # 重新加载数据以更新UI
            st.experimental_rerun()
    
    with col2:
        if st.button("暂停交易"):
            # 设置pause_trading=1
            update_control_flags({"pause_trading": 1})
            st.warning("交易已暂停！")
            # 重新加载数据以更新UI
            st.experimental_rerun()
    
    with col3:
        if st.button("恢复交易"):
            # 设置pause_trading=0
            update_control_flags({"pause_trading": 0})
            st.success("交易已恢复！")
            # 重新加载数据以更新UI
            st.experimental_rerun()

    
    # 最近计划订单
    st.header("最近计划订单")
    
    if engine_status.get("last_plan_order_json"):
        try:
            plan_order = json.loads(engine_status.get("last_plan_order_json"))
            if plan_order:
                st.json(plan_order)
            else:
                st.info("暂无计划订单")
        except json.JSONDecodeError:
            st.error("计划订单解析失败")
    else:
        st.info("暂无计划订单")
    
    # 当前持仓
    st.header("当前持仓")
    
    # 根据运行模式显示不同的持仓数据
    current_run_mode_db = bot_config.get("run_mode", "sim")
    
    if current_run_mode_db == "paper":
        # 显示实盘测试模式的模拟持仓
        paper_positions = get_paper_positions()
        paper_balance = get_paper_balance()
        
        # 显示模拟余额
        if paper_balance:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("模拟余额 (USDT)", f"{paper_balance.get('equity', 0):.2f}")
            with col2:
                st.metric("可用余额 (USDT)", f"{paper_balance.get('available', 0):.2f}")
        
        # 显示模拟持仓
        if paper_positions:
            # 创建DataFrame来更美观地显示持仓
            positions_df = pd.DataFrame(paper_positions)
            st.dataframe(positions_df, width="stretch")
        else:
            st.info("暂无实盘测试持仓")
    else:
        # 显示其他模式的持仓
        if engine_status.get("positions_json"):
            try:
                positions = json.loads(engine_status.get("positions_json"))
                if positions:
                    st.json(positions)
                else:
                    st.info("暂无持仓")
            except json.JSONDecodeError:
                st.error("持仓数据解析失败")
        else:
            st.info("暂无持仓")
    
    # 自动刷新控制
    auto_refresh = st.checkbox("自动刷新", value=True)
    refresh_interval = st.slider("刷新间隔(秒)", min_value=1, max_value=10, value=2)
    
    # 刷新按钮
    if st.button("刷新数据"):
        st.rerun()
    
    # 自动刷新逻辑
    if auto_refresh:
        time.sleep(refresh_interval)
        st.rerun()

if __name__ == "__main__":
    main()
