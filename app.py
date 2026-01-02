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
"""
主应用入口 - Streamlit Web UI
"""
import sys
import os
import io

# Windows UTF-8 编码修复
# 必须在所有其他导入之前执行，防止 UnicodeEncodeError
def _fix_windows_encoding():
    """修复 Windows 控制台 GBK 编码问题，强制使用 UTF-8"""
    if sys.platform.startswith('win'):
        try:
            # Python 3.7+ 推荐方式
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except AttributeError:
            # Python 3.6 兼容方式
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )

_fix_windows_encoding()

import streamlit as st
import time
import json
import pandas as pd
from datetime import datetime

# 加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 启动前检查
try:
    from utils.startup_validator import StartupValidator
    pkg_ok, missing_req, missing_opt = StartupValidator.check_packages(verbose=False)
    if not pkg_ok:
        st.error("❌ 启动检查失败")
        st.error(f"缺失 Python 依赖: {', '.join(missing_req)}")
        st.info("请运行: pip install -r requirements.txt")
        st.stop()
except ImportError:
    pass
except Exception as e:
    print(f"启动检查警告: {e}")

# 导入项目模块
try:
    from database.db_bridge import (
        get_engine_status, get_control_flags, 
        get_bot_config, update_bot_config, set_control_flags,
        init_db,
        get_paper_balance, get_paper_positions, get_hedge_positions,
        get_trade_stats, get_trade_history  # 交易统计
    )
    from database.db_bridge import get_bootstrap_state, get_credentials_status, verify_credentials_and_snapshot
except ImportError as e:
    st.error(f"❌ 导入数据库模块失败: {str(e)[:200]}")
    st.info("请检查所有 Python 依赖是否已安装")
    st.stop()

# 导入UI模块
try:
    from ui.ui_legacy import render_main
except ImportError as e:
    st.error(f"❌ 导入 UI 模块失败: {str(e)[:200]}")
    st.stop()

# 导入 Arena UI 模块（可选）
try:
    from ui.ui_arena import render_arena_main, get_arena_mock_data
    HAS_ARENA_UI = True
except ImportError:
    HAS_ARENA_UI = False

# ◈ 导入策略助手 UI 模块（可选）
try:
    from ui.ui_strategy_builder import render_strategy_builder
    HAS_STRATEGY_BUILDER = True
except ImportError:
    HAS_STRATEGY_BUILDER = False

# 导入 Arena 调度器模块（可选）
try:
    from ai.arena_scheduler import (
        start_scheduler, stop_scheduler, is_scheduler_running,
        get_latest_battle_result, get_recent_decisions
    )
    HAS_ARENA_SCHEDULER = True
except ImportError:
    HAS_ARENA_SCHEDULER = False

# 自动刷新组件（用于轮询 AI 决策）
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False


def get_env_config(env_mode):
    """根据运行模式获取环境配置
    
    两种模式都使用实盘API：
    - 实盘测试：读取实盘数据，但不真实下单（allow_trading=False）
    - 实盘：读取实盘数据，允许真实下单（allow_trading=True）
    """
    env_map = {
        "🛰️ 实盘测试": {"api_source": "live", "is_sandbox": False, "allow_trading": False},
        " 实盘": {"api_source": "live", "is_sandbox": False, "allow_trading": True}
    }
    return env_map.get(env_mode, {"api_source": "live", "is_sandbox": False, "allow_trading": False})


def discover_strategy_modules():
    """发现可用的策略模块（使用 strategy_registry）"""
    try:
        from strategies.strategy_registry import list_all_strategies
        return list_all_strategies()
    except Exception:
        # 降级到硬编码列表
        return [
            ("趋势策略 v1", "strategy_v1"),
            ("趋势策略 v2", "strategy_v2"),
            ("默认策略", "strategy_default")
        ]


def load_user_state(username):
    """加载用户状态"""
    # 从数据库获取用户状态
    return {
        "trading_active": True,
        "auto_symbols": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT"],
        "open_positions": {},
        "hedge_positions": {},
        "env_mode": " 实盘",
        "strategy_module": "strategy_v2",
        "position_sizes": {"primary": 0.05, "secondary": 0.025}
    }


def save_user_state(username):
    """保存用户状态"""
    # 将用户状态保存到数据库
    pass


def manual_scan(symbols, timeframe):
    """手动扫描策略信号"""
    return []


def main():
    """交易系统控制面板主函数"""
    # 设置页面标题
    st.set_page_config(page_title="何以为势の实盘系统", page_icon="", layout="wide")
    
    # 初始化数据库，带异常处理
    try:
        init_db()
        st.session_state.db_ready = True
    except Exception as e:
        st.error(f"❌ 数据库初始化失败: {str(e)[:300]}")
        st.info("""
        可能的原因：
        1. 数据库文件损坏或被锁定
        2. 数据库路径权限不足
        3. PostgreSQL 连接失败（若配置了外部数据库）
        
        **解决方案：**
        - 删除 quant_system.db 文件并重启应用（本地 SQLite）
        - 检查 PostgreSQL 连接配置（若使用外部数据库）
        - 检查目录权限
        """)
        st.stop()
    
    # 打印数据库身份信息用于调试（仅在控制台）
    try:
        from database.db_bridge import debug_db_identity
        db_identity = debug_db_identity()
        # 仅在控制台输出，不在 UI 中显示
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"数据库身份信息: {db_identity}")
    except Exception as e:
        # 忽略调试信息的异常
        pass
    
    # 获取最新数据，带容错处理
    try:
        engine_status = get_engine_status()
        control_flags = get_control_flags()
        bot_config = get_bot_config()
    except Exception as e:
        st.error(f"❌ 获取系统状态失败: {str(e)[:200]}")
        st.stop()
    
    # 准备view_model
    view_model = {
        "engine_status": engine_status,
        "control_flags": control_flags,
        "bot_config": bot_config,
        "equity": "----",  # 应该从数据库获取
        "btc_price": "----",  # 应该从数据库获取
        "fear_value": "----",  # 应该从数据库获取
        "fear_level": "----",  # 应该从数据库获取
        "env_mode": " 实盘",  # 应该从view_model获取
        "trading_active": engine_status.get("alive") == 1,
        "open_positions": {},  # 应该从数据库获取
        "hedge_positions": {},  # 应该从数据库获取
        "strategy_options": discover_strategy_modules(),
        "simulation_stats": {
            "current_equity": 200.0,
            "initial_balance": 200.0,
            "total_return": 0.0,
            "total_trades": 0,
            "win_rate": 0.0,
            "max_drawdown": 0.0
        },
        "recent_logs": []  # 应该从数据库获取
    }
    
    # 根据运行模式获取相应的持仓和余额数据
    current_run_mode_db = bot_config.get("run_mode", "sim")
    
    # 始终获取模拟账户数据（用于实盘测试模式显示）
    paper_balance = get_paper_balance()
    paper_positions = get_paper_positions()
    view_model["paper_balance"] = paper_balance  # 添加到view_model
    
    if current_run_mode_db == "paper":
        # 获取实盘测试模式的模拟数据
        # 更新view_model中的数据
        if paper_balance:
            view_model["equity"] = f"{paper_balance.get('equity', 0):.2f}"
            view_model["simulation_stats"]["current_equity"] = paper_balance.get('equity', 200.0)
            view_model["simulation_stats"]["initial_balance"] = paper_balance.get('equity', 200.0)
        
        if paper_positions:
            # 转换paper_positions为view_model需要的格式
            # 同一个symbol如果有两个方向的仓位，需要区分主仓和对冲仓
            open_positions_dict = {}
            hedge_positions_dict = {}
            
            # 辅助函数：格式化入场时间
            def format_entry_time(ts):
                if not ts or ts <= 0:
                    return ""
                from datetime import datetime
                if ts > 1e12:
                    ts_sec = ts / 1000
                    ms_part = int(ts % 1000)
                    return datetime.fromtimestamp(ts_sec).strftime('%m-%d %H:%M:%S') + f".{ms_part:03d}"
                else:
                    return datetime.fromtimestamp(ts).strftime('%m-%d %H:%M:%S')
            
            # 辅助函数：构建仓位数据
            def build_position_data(pos):
                qty = float(pos.get("qty", 0) or 0)
                entry_price = float(pos.get("entry_price", 0) or 0)
                unrealized_pnl = float(pos.get("unrealized_pnl", 0) or 0)
                notional = qty * entry_price
                created_ts = pos.get("created_at", 0) or pos.get("updated_at", 0)
                return {
                    "side": pos.get("pos_side", "long").upper(),
                    "size": notional,
                    "margin": notional / 20,
                    "entry_price": entry_price,
                    "entry_time": format_entry_time(created_ts),
                    "pnl": unrealized_pnl
                }
            
            # 第一步：按 symbol 分组所有仓位
            positions_by_symbol = {}
            if isinstance(paper_positions, dict):
                for pos_key, pos in paper_positions.items():
                    if isinstance(pos, dict):
                        symbol = pos.get("symbol", pos_key.split("_")[0] if "_" in pos_key else pos_key)
                        if symbol not in positions_by_symbol:
                            positions_by_symbol[symbol] = []
                        positions_by_symbol[symbol].append(pos)
            elif isinstance(paper_positions, list):
                for pos in paper_positions:
                    if isinstance(pos, dict) and "symbol" in pos:
                        symbol = pos["symbol"]
                        if symbol not in positions_by_symbol:
                            positions_by_symbol[symbol] = []
                        positions_by_symbol[symbol].append(pos)
            
            # 第二步：区分主仓和对冲仓
            # 规则：同一个symbol如果有两个方向，先开的是主仓，后开的是对冲仓
            for symbol, positions in positions_by_symbol.items():
                if len(positions) == 1:
                    # 只有一个仓位，作为主仓
                    open_positions_dict[symbol] = build_position_data(positions[0])
                elif len(positions) >= 2:
                    # 有两个仓位，按 created_at 排序，先开的是主仓
                    sorted_positions = sorted(positions, key=lambda p: p.get("created_at", 0) or p.get("updated_at", 0))
                    # 第一个是主仓
                    open_positions_dict[symbol] = build_position_data(sorted_positions[0])
                    # 其余是对冲仓
                    if symbol not in hedge_positions_dict:
                        hedge_positions_dict[symbol] = []
                    for hedge_pos in sorted_positions[1:]:
                        hedge_positions_dict[symbol].append(build_position_data(hedge_pos))
            
            view_model["open_positions"] = open_positions_dict
            
            # 同时加载 hedge_positions 表中的对冲仓位（如果有）
            hedge_positions_raw = get_hedge_positions()
            if hedge_positions_raw:
                for hedge_pos in hedge_positions_raw:
                    symbol = hedge_pos.get("symbol", "")
                    if not symbol:
                        continue
                    
                    qty = float(hedge_pos.get("qty", 0) or 0)
                    entry_price = float(hedge_pos.get("entry_price", 0) or 0)
                    unrealized_pnl = float(hedge_pos.get("unrealized_pnl", 0) or 0)
                    notional = qty * entry_price
                    created_ts = hedge_pos.get("created_at", 0) or hedge_pos.get("updated_at", 0)
                    
                    hedge_data = {
                        "side": hedge_pos.get("pos_side", "short").upper(),
                        "size": notional,
                        "margin": notional / 20,
                        "entry_price": entry_price,
                        "entry_time": format_entry_time(created_ts),
                        "pnl": unrealized_pnl
                    }
                    
                    if symbol not in hedge_positions_dict:
                        hedge_positions_dict[symbol] = []
                    hedge_positions_dict[symbol].append(hedge_data)
            
            view_model["hedge_positions"] = hedge_positions_dict
    
    # 实时获取持仓数据的函数（用于 fragment 刷新）
    def get_open_positions_formatted():
        """获取格式化的主仓数据"""
        paper_positions = get_paper_positions()
        if not paper_positions:
            return {}
        
        open_positions_dict = {}
        positions_by_symbol = {}
        
        # 按 symbol 分组
        if isinstance(paper_positions, dict):
            for pos_key, pos in paper_positions.items():
                if isinstance(pos, dict):
                    symbol = pos.get("symbol", pos_key.split("_")[0] if "_" in pos_key else pos_key)
                    if symbol not in positions_by_symbol:
                        positions_by_symbol[symbol] = []
                    positions_by_symbol[symbol].append(pos)
        
        # 构建仓位数据
        for symbol, positions in positions_by_symbol.items():
            if positions:
                pos = positions[0]  # 取第一个作为主仓
                qty = float(pos.get("qty", 0) or 0)
                entry_price = float(pos.get("entry_price", 0) or 0)
                unrealized_pnl = float(pos.get("unrealized_pnl", 0) or 0)
                notional = qty * entry_price
                open_positions_dict[symbol] = {
                    "side": pos.get("pos_side", "long").upper(),
                    "size": notional,
                    "margin": notional / 20,
                    "entry_price": entry_price,
                    "pnl": unrealized_pnl
                }
        
        return open_positions_dict
    
    def get_hedge_positions_formatted():
        """获取格式化的对冲仓数据"""
        hedge_positions_raw = get_hedge_positions()
        if not hedge_positions_raw:
            return {}
        
        hedge_positions_dict = {}
        for hedge_pos in hedge_positions_raw:
            symbol = hedge_pos.get("symbol", "")
            if not symbol:
                continue
            
            qty = float(hedge_pos.get("qty", 0) or 0)
            entry_price = float(hedge_pos.get("entry_price", 0) or 0)
            unrealized_pnl = float(hedge_pos.get("unrealized_pnl", 0) or 0)
            notional = qty * entry_price
            
            hedge_data = {
                "side": hedge_pos.get("pos_side", "short").upper(),
                "size": notional,
                "margin": notional / 20,
                "entry_price": entry_price,
                "pnl": unrealized_pnl
            }
            
            if symbol not in hedge_positions_dict:
                hedge_positions_dict[symbol] = []
            hedge_positions_dict[symbol].append(hedge_data)
        
        return hedge_positions_dict
    
    # 准备actions
    actions = {
        "get_env_config": get_env_config,
        "discover_strategy_modules": discover_strategy_modules,
        "load_user_state": load_user_state,
        "save_user_state": save_user_state,
        "manual_scan": manual_scan,
        "get_bot_config": get_bot_config,  # 添加缺失的action
        "update_bot_config": update_bot_config,
        "set_control_flags": set_control_flags,
        "get_bootstrap_state": get_bootstrap_state,
        "get_credentials_status": get_credentials_status,
        "verify_credentials_and_snapshot": verify_credentials_and_snapshot,
        "get_paper_balance": get_paper_balance,
        "get_trade_stats": get_trade_stats,  # 交易统计
        "get_trade_history": get_trade_history,  # 交易历史（资金曲线）
        "get_open_positions": get_open_positions_formatted,  # 实时持仓
        "get_hedge_positions": get_hedge_positions_formatted  # 实时对冲仓
    }
    
    # UI 模式切换：策略助手 vs Arena 模式 vs 经典模式
    # 切换按钮已移至侧边栏 (ui_legacy.py render_sidebar)
    if HAS_STRATEGY_BUILDER and st.session_state.get('strategy_builder_mode', False):
        # ◈ 策略助手模式
        render_strategy_builder(view_model, actions)
    elif HAS_ARENA_UI and st.session_state.get('arena_mode', False):
        # Arena 模式
        # 移除全局 st_autorefresh，改用 @st.fragment 局部刷新
        # 这样 K 线图不会因为刷新而重置
        
        # 检查是否有新决策（不再依赖全局刷新）
        if HAS_ARENA_SCHEDULER:
            latest_result = get_latest_battle_result()
            last_ts = st.session_state.get('last_decision_ts', 0)
            
            if latest_result and latest_result.timestamp > last_ts:
                st.session_state.last_decision_ts = latest_result.timestamp
                st.session_state.latest_battle_result = latest_result
        
        render_arena_main(view_model, actions)
    else:
        # 经典模式
        render_main(view_model, actions)

if __name__ == "__main__":
    main()

