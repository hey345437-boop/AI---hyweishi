import sys
import os
import io

# ============ Windows UTF-8 编码修复 ============
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
    pass  # dotenv 未安装，跳过

# ============ 启动前检查 ============
# 在导入其他模块前执行启动验证
try:
    from startup_validator import StartupValidator
    all_passed, check_results = StartupValidator.run_full_check(verbose=False)
    if not all_passed:
        st.error("❌ 启动检查失败")
        if check_results.get('packages', {}).get('missing_required'):
            st.error(f"缺失 Python 依赖: {', '.join(check_results['packages']['missing_required'])}")
            st.info("请运行: pip install -r requirements.txt")
        if not check_results.get('config', {}).get('is_valid'):
            config_detail = check_results.get('config', {})
            st.error(f"缺失必需配置: {', '.join(config_detail.get('missing_required', []))}")
            st.info("请设置对应的环境变量或使用 .env 文件")
        if not check_results.get('database', {}).get('ok'):
            st.error(f"数据库检查失败: {check_results['database'].get('message', '未知错误')}")
        st.stop()
except Exception as e:
    st.error(f"❌ 启动检查异常: {str(e)[:200]}")
    st.info("请确保所有依赖已安装，且配置文件正确")
    st.stop()

# 导入项目模块
try:
    from db_bridge import (
        get_engine_status, get_control_flags, 
        get_bot_config, update_bot_config, set_control_flags,
        init_db,
        get_paper_balance, get_paper_positions
    )
    from db_bridge import get_bootstrap_state, get_credentials_status, verify_credentials_and_snapshot
except ImportError as e:
    st.error(f"❌ 导入数据库模块失败: {str(e)[:200]}")
    st.info("请检查所有 Python 依赖是否已安装")
    st.stop()

# 导入UI模块
try:
    from ui_legacy import render_main
except ImportError as e:
    st.error(f"❌ 导入 UI 模块失败: {str(e)[:200]}")
    st.stop()

# ============ 辅助函数 ============

def get_env_config(env_mode):
    """根据运行模式获取环境配置
    
    两种模式都使用实盘API：
    - 实盘测试：读取实盘数据，但不真实下单（allow_trading=False）
    - 实盘：读取实盘数据，允许真实下单（allow_trading=True）
    """
    env_map = {
        "🛰️ 实盘测试": {"api_source": "live", "is_sandbox": False, "allow_trading": False},
        "💰 实盘": {"api_source": "live", "is_sandbox": False, "allow_trading": True}
    }
    return env_map.get(env_mode, {"api_source": "live", "is_sandbox": False, "allow_trading": False})


def discover_strategy_modules():
    """发现可用的策略模块（使用 strategy_registry）"""
    try:
        from strategy_registry import list_all_strategies
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
        "env_mode": "💰 实盘",
        "strategy_module": "strategy_v2",
        "position_sizes": {"primary": 0.05, "secondary": 0.025}
    }


def save_user_state(username):
    """保存用户状态"""
    # 将用户状态保存到数据库
    pass


def manual_scan(symbols, timeframe):
    """手动扫描策略信号"""
    # 这里应该调用策略引擎进行扫描
    return []

# ============ 主页面 ============

def main():
    """交易系统控制面板主函数"""
    # 🔥 设置页面标题
    st.set_page_config(page_title="何以为势の实盘系统", page_icon="⚡", layout="wide")
    
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
        from db_bridge import debug_db_identity
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
        "env_mode": "💰 实盘",  # 应该从view_model获取
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
    
    # 🔥 始终获取模拟账户数据（用于实盘测试模式显示）
    paper_balance = get_paper_balance()
    paper_positions = get_paper_positions()
    view_model["paper_balance"] = paper_balance  # 🔥 添加到view_model
    
    if current_run_mode_db == "paper":
        # 获取实盘测试模式的模拟数据
        # 更新view_model中的数据
        if paper_balance:
            view_model["equity"] = f"{paper_balance.get('equity', 0):.2f}"
            view_model["simulation_stats"]["current_equity"] = paper_balance.get('equity', 200.0)
            view_model["simulation_stats"]["initial_balance"] = paper_balance.get('equity', 200.0)
        
        if paper_positions:
            # 转换paper_positions为view_model需要的格式
            open_positions_dict = {}
            # 检查paper_positions的结构
            if isinstance(paper_positions, list):
                for pos in paper_positions:
                    if isinstance(pos, dict) and "symbol" in pos:
                        symbol = pos["symbol"]
                        # 🔥 转换入场时间戳为可读格式
                        created_ts = pos.get("created_at", 0)
                        entry_time_str = ""
                        if created_ts and created_ts > 0:
                            from datetime import datetime
                            entry_time_str = datetime.fromtimestamp(created_ts).strftime('%m-%d %H:%M')
                        notional = pos["qty"] * pos["entry_price"]
                        open_positions_dict[symbol] = {
                            "side": pos["side"],
                            "size": notional,  # 名义价值
                            "margin": notional / 20,  # 🔥 保证金（假设20x杠杆）
                            "entry_price": pos["entry_price"],
                            "entry_time": entry_time_str  # 🔥 添加入场时间
                        }
            elif isinstance(paper_positions, dict):
                # 如果paper_positions是字典格式，直接使用
                for symbol, pos in paper_positions.items():
                    if isinstance(pos, dict):
                        # 🔥 转换入场时间戳为可读格式
                        created_ts = pos.get("created_at", 0)
                        entry_time_str = ""
                        if created_ts and created_ts > 0:
                            from datetime import datetime
                            entry_time_str = datetime.fromtimestamp(created_ts).strftime('%m-%d %H:%M')
                        notional = pos.get("qty", 0) * pos.get("entry_price", 0)
                        open_positions_dict[symbol] = {
                            "side": pos.get("side", "long"),
                            "size": notional,  # 名义价值
                            "margin": notional / 20,  # 🔥 保证金（假设20x杠杆）
                            "entry_price": pos.get("entry_price", 0),
                            "entry_time": entry_time_str  # 🔥 添加入场时间
                        }
            view_model["open_positions"] = open_positions_dict
    
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
        "get_paper_balance": get_paper_balance
    }
    
    # 调用UI模块
    render_main(view_model, actions)

if __name__ == "__main__":
    main()
