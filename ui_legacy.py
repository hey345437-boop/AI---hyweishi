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

# 🔥 双通道信号系统支持
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
# 只保留两种模式: 实盘测试(读取实盘数据但不下单)和实盘(真实交易)
RUN_MODE_UI = ["🛰️ 实盘测试", "💰 实盘"]
RUN_MODE_UI_TO_DB = {"🛰️ 实盘测试": "paper", "💰 实盘": "live"}  # paper模式用于实盘测试
RUN_MODE_DB_TO_UI = {v: k for k, v in RUN_MODE_UI_TO_DB.items()}
# 兼容旧的sim模式, 映射到实盘测试
RUN_MODE_DB_TO_UI['sim'] = "🛰️ 实盘测试"


# ============ Market API 客户端 ============
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
        
        # 🔥 如果指定了策略，添加到请求参数
        if strategy_id:
            params["strategy"] = strategy_id
        
        response = requests.get(url, params=params, timeout=15)  # 增加超时时间（策略计算需要时间）
        
        if response.status_code == 200:
            result = response.json()
            return {
                "ok": True,
                "data": result.get("data", []),
                "markers": result.get("markers", []),  # 🔥 新增：策略信号标记
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


# ============ K线图专用缓存（与交易引擎完全隔离）============
# 🔥 UI K线图使用独立缓存，只显示收盘K线，不影响交易引擎
_UI_KLINE_CACHE = {}  # {(symbol, tf): {'data': [...], 'ts': timestamp}}
_UI_KLINE_CACHE_TTL = 10  # 10秒缓存


def _fetch_ohlcv_for_chart(symbol: str, timeframe: str, limit: int = 500) -> list:
    """
    🔥 K线图专用数据获取（与交易引擎完全隔离）
    
    特点：
    1. 使用独立缓存字典 _UI_KLINE_CACHE
    2. 强制返回收盘K线（去掉最后一根正在形成的K线）
    3. 不影响交易引擎的数据
    """
    import time as time_module
    cache_key = (symbol, timeframe)
    now = time_module.time()
    
    # 检查缓存
    if cache_key in _UI_KLINE_CACHE:
        cached = _UI_KLINE_CACHE[cache_key]
        if now - cached['ts'] < _UI_KLINE_CACHE_TTL:
            return cached['data']
    
    # 从交易所获取数据
    try:
        import ccxt
        from dotenv import load_dotenv
        load_dotenv()
        
        # 获取代理配置
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        config = {
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        }
        
        if https_proxy:
            config['proxies'] = {
                'http': http_proxy or https_proxy,
                'https': https_proxy
            }
        
        exchange = ccxt.okx(config)
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit + 1)  # 多拉一根
        
        # 🔥 强制去掉最后一根（正在形成的K线），只保留收盘K线
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
        print(f"[_fetch_ohlcv_for_chart] Error: {e}")
        # 返回旧缓存（如果有）
        if cache_key in _UI_KLINE_CACHE:
            return _UI_KLINE_CACHE[cache_key]['data']
        return []


# 保留旧函数兼容性（但不再使用）
@st.cache_data(ttl=5)
def _fetch_ohlcv_direct(symbol: str, timeframe: str, limit: int = 500) -> list:
    """旧函数，保留兼容性，内部调用新函数"""
    return _fetch_ohlcv_for_chart(symbol, timeframe, limit)


# Sentiment fetcher (cached 60s)
@st.cache_data(ttl=60)
def fetch_sentiment_cached():
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = response.json()
        item = data.get("data", [])[0]
        value = item.get("value")
        classification = item.get("value_classification")
        ts = int(time.time())
        return {'value': value, 'classification': classification, 'ts': ts}
    except Exception:
        return {'value': None, 'classification': None, 'ts': int(time.time())}


# ============ 实时数据获取函数(短 TTL 缓存)============
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
    """获取账户余额(3秒缓存)
    
    _actions_hash 用于在 API 配置变更后强制刷新缓存
    """
    try:
        # 这里返回占位符, 实际数据由 view_model 提供
        # 此函数主要用于触发缓存刷新机制
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

# ACCESS_PASSWORD 从环境变量读取, 支持开发模式默认密码
from env_validator import EnvironmentValidator

# 验证访问密码配置
_pwd_valid, _pwd_warning, ACCESS_PASSWORD = EnvironmentValidator.validate_access_password()
if not _pwd_valid:
    raise RuntimeError(f"❌ {_pwd_warning}")

# 标记是否使用了开发模式默认密码(用于UI警告显示)
USING_DEV_PASSWORD = bool(_pwd_warning)


def render_login(view_model, actions):
    """渲染登录页面"""
    # P1修复: 会话超时检查(4小时)
    SESSION_TIMEOUT_SECONDS = 4 * 60 * 60  # 4小时
    if st.session_state.get("logged_in", False):
        login_time = st.session_state.get("login_time", 0)
        if login_time > 0 and (time.time() - login_time) > SESSION_TIMEOUT_SECONDS:
            st.session_state.logged_in = False
            st.session_state.login_time = 0
            st.warning("⚠️ 会话已超时, 请重新登录")
    
    if not st.session_state.get("logged_in", False):
        # 🔥 何以为势 入场动画
        st.markdown("""<style>.auth-box {max-width:400px;margin:auto;padding:20px}
        @keyframes fadeOut { 0% { opacity: 1; z-index: 999999; } 80% { opacity: 1; } 100% { opacity: 0; z-index: -1; visibility: hidden; }}
        @keyframes textShine { 0% { background-position: 0% 50%; } 100% { background-position: 100% 50%; }}
        #intro-overlay { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: #000; display: flex; justify-content: center; align-items: center; animation: fadeOut 2.5s forwards; z-index: 999999; }
        .intro-text { font-size: 60px; font-weight: 900; background: linear-gradient(to right, #4d4d4d 0%, #fff 50%, #4d4d4d 100%); background-size: 200% auto; color: transparent; -webkit-background-clip: text; background-clip: text; animation: textShine 2s linear infinite; letter-spacing: 8px; }
        .intro-sub { margin-top: 20px; font-size: 16px; color: #999 !important; text-align: center; font-family: 'Courier New'; letter-spacing: 2px; }
        </style>
        <div id="intro-overlay"><div style="text-align: center;"><div class="intro-text">何以为势</div><div class="intro-sub">SYSTEM ONLINE...</div></div></div>
        """, unsafe_allow_html=True)
        
        st.title("🔐 何以为势の实盘系统")
        
        # 显示开发模式警告
        if USING_DEV_PASSWORD:
            st.warning("⚠️ 当前使用开发模式默认密码, 请勿在生产环境使用!请设置 STREAMLIT_ACCESS_PASSWORD 环境变量. ")
        
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.markdown("### 请输入访问密码")
            password_input = st.text_input("🔑 访问密码", type="password", placeholder="请输入访问密码")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("✅ 进入系统", width="stretch"):
                    # 忽略用户输入两端的意外空白字符后比较
                    if (password_input or '').strip() == ACCESS_PASSWORD:
                        st.session_state.logged_in = True
                        st.session_state.username = "admin"  # 默认用户
                        # P1修复: 记录登录时间用于会话超时
                        st.session_state.login_time = time.time()
                        
                        # 从数据库加载配置
                        bot_config = actions.get("get_bot_config", lambda: {})()
                        
                        # 转换run_mode为UI显示模式(与顶部定义一致)
                        run_mode_map = {
                            "live": "💰 实盘",
                            "paper": "🛰️ 实盘测试",  # paper模式对应实盘测试
                            "sim": "🛰️ 实盘测试"  # 兼容旧的sim模式
                        }
                        
                        # 设置session_state
                        st.session_state.trading_active = bot_config.get("enable_trading", 0) == 1
                        st.session_state.auto_symbols = bot_config.get("symbols", "").split(",") if bot_config.get("symbols") else []
                        st.session_state.open_positions = {}
                        st.session_state.hedge_positions = {}
                        st.session_state.env_mode = run_mode_map.get(bot_config.get("run_mode", "sim"), "💰 实盘")
                        st.session_state.strategy_module = "strategy_v2"  # 🔥 默认趋势2
                        st.session_state.position_sizes = {
                            "primary": bot_config.get("position_size", 0.05), 
                            "secondary": bot_config.get("position_size", 0.05) / 2
                        }
                        
                        st.success("✅ 登录成功!")
                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error("❌ 密码错误, 请重试")
            
            with col_btn2:
                st.caption("📞 忘记密码请联系管理员")
            
            st.divider()
            st.info("🛡️ 安全提示: 请保管好您的访问密码, 不要分享给他人")
        
        st.stop()  # 阻止未登录用户访问后续内容

def render_sidebar(view_model, actions):
    """渲染侧边栏"""
    with st.sidebar:
        # ============ 后端状态(放在最上方)============
        engine_status = view_model.get("engine_status", {})
        runner_alive = engine_status.get("alive", 0) == 1
        if runner_alive:
            st.success("🟢 后端在线")
        else:
            st.error("🔴 后端离线")
        
        # ============ 资产概览 ============
        st.markdown("## 💎 资产看板")
        
        # 🔥 根据运行模式显示不同的余额
        # 实盘测试模式 -> 显示模拟仓位余额
        # 实盘模式 -> 显示 OKX 真实余额
        current_env_mode = st.session_state.get('env_mode', '💰 实盘')
        
        if current_env_mode == "🛰️ 实盘测试":
            # 实盘测试模式: 从数据库读取模拟账户余额
            try:
                paper_balance = actions.get("get_paper_balance", lambda: {})()
                if paper_balance and paper_balance.get('equity'):
                    equity_val = paper_balance.get('equity', 10000)
                    equity = f"${equity_val:,.2f}"
                else:
                    # 默认模拟账户初始余额
                    equity_val = 10000.0
                    equity = "$10,000.00"
            except Exception:
                equity_val = 10000.0
                equity = "$10,000.00"
            
            st.metric("模拟净值(USDT)", equity)
            st.caption("📌 模拟账户余额(非真实资金)")
        else:
            # 实盘模式: 显示 OKX 真实余额
            live_balance = st.session_state.get('live_balance', {})
            if live_balance and live_balance.get('equity'):
                equity = f"${live_balance.get('equity', 0):,.2f}"
            else:
                # 回退到 view_model 中的数据
                equity = view_model.get("equity", "----")
            
            st.metric("账户净值(USDT)", equity)
            st.caption("💰 OKX 真实账户余额")
        
        # 初始化必要的session_state变量
        if "strategy_module" not in st.session_state:
            st.session_state.strategy_module = "strategy"
        if "env_mode" not in st.session_state:
            st.session_state.env_mode = "💰 实盘"  # 默认实盘
        
        # 环境模式切换(session_state.env_mode 为 UI 缓存, DB 为权威)
        st.markdown("### 🎛️ 运行模式")
        
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
            if run_mode_db == 'live' and st.session_state.env_mode != "💰 实盘":
                st.session_state.live_mode_confirm_pending = True
                st.session_state.pending_live_mode_sel = sel
                return  # 不立即执行, 等待确认
            
            # 非实盘模式直接执行
            _execute_mode_change(run_mode_db, sel)

        # selectbox 使用 key + on_change 回调
        st.selectbox(
            "选择运行模式",
            RUN_MODE_UI,
            index=RUN_MODE_UI.index(st.session_state.env_mode) if st.session_state.env_mode in RUN_MODE_UI else 0,
            key='env_mode_selector',
            on_change=_on_env_mode_change
        )

        env_cfg = actions.get("get_env_config", lambda m: {"api_source": "live", "is_sandbox": False})(st.session_state.env_mode)
        
        # P0修复: 实盘模式二次确认弹窗
        if st.session_state.get('live_mode_confirm_pending', False):
            st.warning("⚠️ **警告: 您正在切换到实盘模式!**")
            st.error("实盘模式下所有交易将使用真实资金执行, 可能造成资金损失!")
            col_confirm, col_cancel = st.columns(2)
            with col_confirm:
                if st.button("✅ 确认切换到实盘", type="primary", width="stretch"):
                    sel = st.session_state.get('pending_live_mode_sel', "💰 实盘")
                    _execute_mode_change('live', sel)
                    st.session_state.live_mode_confirm_pending = False
                    st.success("已切换到实盘模式")
                    time.sleep(0.5)
                    st.rerun()
            with col_cancel:
                if st.button("❌ 取消", width="stretch"):
                    st.session_state.live_mode_confirm_pending = False
                    st.info("已取消切换")
                    st.rerun()
        
        # P2-8修复: 明确说明运行模式
        if st.session_state.env_mode == "🛰️ 实盘测试":
            st.caption("📌 读取真实行情, 但不会真实下单")
        elif st.session_state.env_mode == "💰 实盘":
            st.caption("⚠️ 实盘模式: 所有交易将真实执行")
        
        # 显示 OKX_SANDBOX 环境变量状态(帮助用户理解配置)
        okx_sandbox = os.getenv('OKX_SANDBOX', 'false').lower() == 'true'
        if okx_sandbox:
            st.warning("⚠️ 当前 OKX_SANDBOX=true, 使用 OKX 模拟盘 API(非真实资金)")
        
        st.markdown("### 📐 策略切换")
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
            "选择策略模块",
            strategy_options,
            index=current_idx,
            key='strategy_selectbox',
            format_func=lambda x: x[0],
            on_change=_on_strategy_change
        )
        # 同步 session_state(为了兼容其他代码访问 strategy_module)
        if selected_strategy_tuple[1] != st.session_state.get('selected_strategy_id'):
            st.session_state.selected_strategy_id = selected_strategy_tuple[1]
        
        # API配置界面
        st.markdown("### 🔑 API配置")
        with st.expander("API密钥配置", expanded=False):
            # 使用后端提供bootstrap / credential status
            cred_status = actions.get("get_credentials_status", lambda: {"okx_bound": False, "okx_key_tail": None})()

            # 展示绑定状态(脱敏)
            if cred_status.get('okx_bound'):
                st.success(f"[OK] API 状态: 已绑定(****{cred_status.get('okx_key_tail')})")
                st.caption("如需更换密钥, 请重新输入所有字段")
            else:
                st.warning("[!] API 状态: 未绑定, 请配置API密钥")

            # ============ 修复 session_state 问题 ============
            # 使用 "输入key / 保存key" 分离模式
            # - widget key: ui_api_key_input / ui_api_secret_input / ui_api_passphrase_input
            # - 内部状态: api_key_saved / api_secret_saved / api_passphrase_saved (不直接使用)
            # 
            # 关键: 不要在 widget 创建后修改 widget key 对应的 session_state
            
            # 密钥输入 - 不使用 value 参数, 让 Streamlit 自动管理
            # 每次页面刷新后输入框自动清空(这是期望的安全行为)
            api_key = st.text_input(
                "API Key", 
                key='ui_api_key_input',  # 使用 _input 后缀区分
                type='password', 
                placeholder="输入新的API Key(留空则不更新)"
            )
            api_secret = st.text_input(
                "API Secret", 
                key='ui_api_secret_input',  # 使用 _input 后缀区分
                type='password',
                placeholder="输入新的API Secret(留空则不更新)"
            )
            api_password = st.text_input(
                "API Password", 
                key='ui_api_passphrase_input',  # 使用 _input 后缀区分
                type='password',
                placeholder="输入新的API Password(留空则不更新)"
            )

            # 定义保存回调函数
            def _save_api_config():
                """
                保存API配置的回调函- P2-10修复: 并发安全
                
                设计原则: DB SSOT, 先DB 再更session_state
                """
                # widget key 读取值(不修widget key                key_val = st.session_state.get('ui_api_key_input', '')
                secret_val = st.session_state.get('ui_api_secret_input', '')
                pass_val = st.session_state.get('ui_api_passphrase_input', '')
                
                kwargs = {}
                if key_val:
                    kwargs['okx_api_key'] = key_val
                if secret_val:
                    kwargs['okx_api_secret'] = secret_val
                if pass_val:
                    kwargs['okx_api_passphrase'] = pass_val
                
                if kwargs:
                    # P2-10: 先写DB(SSOT)
                    try:
                        actions.get("update_bot_config", lambda **kw: None)(**kwargs)
                        actions.get("set_control_flags", lambda **kw: None)(reload_config=1)
                        # 标记保存成功, 用于后续验证
                        st.session_state._api_save_pending = True
                        st.session_state._api_save_kwargs = kwargs
                    except Exception as e:
                        st.session_state._api_save_error = str(e)[:60]
                else:
                    st.session_state._api_save_empty = True

            # 保存API配置按钮 - 使用 on_click 回调
            st.button("💾 保存API配置", width="stretch", on_click=_save_api_config)
            
            # 处理保存结果(在回调之后执行)
            if st.session_state.get('_api_save_pending'):
                # 清除标记
                st.session_state._api_save_pending = False
                kwargs = st.session_state.pop('_api_save_kwargs', {})
                
                # 校验凭证有效性
                st.info("正在验证 API 凭证...")
                verify_result = actions.get('verify_credentials_and_snapshot', lambda **kw: {'ok': False})()
                
                if verify_result.get('ok'):
                    st.success("[OK] API配置已保存!凭证验证成功, 账户信息已更新")
                    # 清除实时数据缓存, 确保下次刷新获取最新数据
                    clear_realtime_cache()
                    # 更新 session_state 中的余额信息
                    summary = verify_result.get('account_summary', {})
                    # balance ccxt 返回的格式, 需要从中提取 USDT 余额
                    balance = summary.get('balance', {})
                    # ccxt 返回格式: {'total': {'USDT': xxx}, 'free': {'USDT': xxx}, ...}
                    total_usdt = balance.get('total', {}).get('USDT', 0) if isinstance(balance, dict) else 0
                    free_usdt = balance.get('free', {}).get('USDT', 0) if isinstance(balance, dict) else 0
                    st.session_state.live_balance = {
                        'equity': total_usdt,
                        'available': free_usdt
                    }
                    time.sleep(0.5)
                    st.rerun()
                else:
                    error_msg = verify_result.get('error', '未知错误')
                    st.error(f"[X] 凭证验证失败: {error_msg[:100]}")
                    st.info("请检API Key、Secret Passphrase 是否正确")
            
            if st.session_state.pop('_api_save_empty', False):
                st.warning('无变更要保存')
            
            if '_api_save_error' in st.session_state:
                st.error(f"保存API配置失败: {st.session_state.pop('_api_save_error')}")
        
        # 交易池配置
        st.markdown("### 🤖 交易池")
        
        # 【A】修复: 使用 robust symbol 规范化函数
        from symbol_utils import normalize_symbol, parse_symbol_input
        
        # 设置默认交易池(使用规范化格式)
        default_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
        if "auto_symbols" not in st.session_state:
            st.session_state.auto_symbols = default_symbols
        
        # 动态交易池设置
        st.caption("💡 支持输入: btc, BTCUSDT, BTC-USDT, BTC/USDT, BTC-USDT-SWAP 等格式")
        symbol_input = st.text_area(
            "交易对列表(每行一个)",
            value="\n".join(st.session_state.auto_symbols),
            height=100
        )
        
        # 【A】修复: 预览自动格式化后的交易池(与实际保存内容一致)
        # P2修复: 添加白名单检查
        from symbol_utils import is_symbol_whitelisted, SYMBOL_WHITELIST
        if symbol_input:
            preview_symbols = parse_symbol_input(symbol_input)
            if preview_symbols:
                st.info(f"格式化后将保存为: {', '.join(preview_symbols)}")
                # P2修复: 检查是否有非白名单币种
                non_whitelist = []
                for sym in preview_symbols:
                    base = sym.split('/')[0] if '/' in sym else sym
                    if not is_symbol_whitelisted(base):
                        non_whitelist.append(base)
                if non_whitelist:
                    st.warning(f"⚠️ 以下币种不在白名单中(可能流动性较低): {', '.join(non_whitelist)}")
                    st.caption(f"白名单币 {', '.join(sorted(SYMBOL_WHITELIST)[:15])}...")
            else:
                st.warning("⚠️ 未识别到有效的交易对")
        
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
        
        # 🔥 交易参数配置
        st.markdown("### ⚙️ 交易参数")
        
        # 从数据库获取当前交易参数
        bot_config = actions.get("get_bot_config", lambda: {})()
        current_leverage = bot_config.get('leverage', 20)
        current_main_pct = bot_config.get('main_position_pct', 0.03)
        current_sub_pct = bot_config.get('sub_position_pct', 0.01)
        current_hard_tp = bot_config.get('hard_tp_pct', 0.02)
        current_hedge_tp = bot_config.get('hedge_tp_pct', 0.005)
        
        with st.expander("交易参数设置", expanded=False):
            st.caption("💡 调整杠杆、仓位比例和止盈参数")
            
            # 🔥 执行模式固定为 59 秒抢跑（不再提供 UI 选择，不显示）
            new_exec_mode = 'intrabar'  # 固定值
            
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
            
            # 仓位比例设置
            col_pos1, col_pos2 = st.columns(2)
            with col_pos1:
                new_main_pct = st.number_input(
                    "主信号仓(%)",
                    min_value=0.1,
                    max_value=20.0,
                    value=current_main_pct * 100,
                    step=0.5,
                    help="主趋势信号的仓位比例(占权益百分比)"
                ) / 100
            with col_pos2:
                new_sub_pct = st.number_input(
                    "次信号仓(%)",
                    min_value=0.1,
                    max_value=10.0,
                    value=current_sub_pct * 100,
                    step=0.5,
                    help="次信号/对冲信号的仓位比例"
                ) / 100
            
            # 止盈设置
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
            
            # 保存按钮
            if st.button("💾 保存交易参数", width="stretch"):
                try:
                    actions.get("update_bot_config", lambda **kwargs: None)(
                        leverage=new_leverage,
                        main_position_pct=new_main_pct,
                        sub_position_pct=new_sub_pct,
                        hard_tp_pct=new_hard_tp,
                        hedge_tp_pct=new_hedge_tp,
                        execution_mode=new_exec_mode  # 🔥 保存执行模式
                    )
                    actions.get("set_control_flags", lambda **kwargs: None)(reload_config=1)
                    st.success("交易参数已保存")
                except Exception as e:
                    st.error(f"保存失败: {str(e)[:50]}")
            
            # 显示当前参数摘要
            exec_mode_short = {"intrabar": "抢跑", "confirmed": "收线", "both": "双通道"}.get(new_exec_mode, new_exec_mode)
            st.caption(f"当前: {exec_mode_short} | {new_leverage}x杠杆 | 主仓{new_main_pct*100:.1f}% | 次仓{new_sub_pct*100:.1f}%")
        
        # 资产概览已移至侧边栏顶部, 此处不再重复显示

@st.fragment
def _render_kline_section_fragment(view_model, actions):
    """
    🔥 K线图区域 Fragment - 包含 expander 和自动刷新逻辑
    
    使用 @st.fragment（无 run_every）将整个区域封装为独立 fragment：
    1. expander 状态在 fragment 内部管理，不受外部刷新影响
    2. 只有当用户勾选"自动刷新"且 expander 展开时，才启动定时刷新
    3. 折叠时跳过图表渲染，节省资源
    """
    # 🔥 使用 session_state 记录展开状态
    if 'kline_expanded' not in st.session_state:
        st.session_state.kline_expanded = False
    
    # 🔥 expander 展开状态检测 - expanded 参数控制初始状态
    expanded = st.expander("展开K线图", expanded=st.session_state.kline_expanded)
    with expanded:
        # 🔥 更新 session_state 中的展开状态（用于下次渲染）
        # 注意：Streamlit 的 expander 不直接返回当前展开状态
        # 我们通过 checkbox 来让用户控制是否启用自动刷新
        
        # 🔥 只有当 expander 内容被渲染时才执行
        if not HAS_PLOTLY and not HAS_LIGHTWEIGHT_CHARTS:
            st.warning("⚠️ 请安装 plotly 或 streamlit-lightweight-charts 库以显示K线图")
            return
        
        # 渲染 K线图
        _render_kline_chart(view_model, actions)


def _render_kline_chart(view_model, actions):
    """渲染K线图分析窗口 - TradingView Lightweight Charts 风格
    
    🔥 K线图完全独立模块：
    1. 使用独立缓存，只显示收盘K线
    2. 独立计算策略信号（不读数据库）
    3. 支持自动刷新（使用 @st.fragment 局部刷新）
    """
    symbols = st.session_state.get('auto_symbols', ['BTC/USDT:USDT'])
    if not symbols:
        st.info("请先在侧边栏配置交易池")
        return
    
    timeframes = ['1m', '3m', '5m', '15m', '30m', '1h']
    
    # 🔥 控制栏
    col_sym, col_tf, col_refresh, col_interval, col_btn, col_status = st.columns([2, 1, 1, 1, 1, 1])
    with col_sym:
        selected_symbol = st.selectbox("币种", symbols, key="kline_symbol_selector")
    with col_tf:
        selected_tf = st.selectbox("周期", timeframes, index=2, key="kline_tf_selector")
    with col_refresh:
        auto_refresh = st.checkbox("自动刷新", value=False, key="kline_auto_refresh")
    with col_interval:
        # 🔥 刷新间隔选择（仅在自动刷新开启时显示）
        if auto_refresh:
            refresh_interval = st.selectbox(
                "间隔",
                options=[1, 2, 5, 10],
                index=0,
                key="kline_refresh_interval",
                format_func=lambda x: f"{x}秒"
            )
        else:
            refresh_interval = 2
            st.caption("")
    with col_btn:
        fetch_btn = st.button("🔄", key="fetch_kline_btn", help="手动刷新")
    with col_status:
        api_status = check_market_api_status()
        if api_status:
            st.caption("🟢 API")
        else:
            st.caption("🟡 直连")
    
    # 🔥 根据自动刷新状态选择渲染模式
    if auto_refresh:
        # 自动刷新模式：使用自定义 HTML 组件实现真正的实时更新
        _render_kline_chart_realtime(selected_symbol, selected_tf, api_status, refresh_interval)
    else:
        # 手动刷新模式：普通渲染
        _render_kline_chart_core(selected_symbol, selected_tf, fetch_btn, api_status, is_auto_refresh=False)


def _render_kline_chart_realtime(selected_symbol, selected_tf, api_status, refresh_interval):
    """
    🔥 实时 K线图 - 使用自定义 HTML 组件实现 TradingView 风格的实时更新
    
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
    if api_status:
        result = fetch_kline_from_api(selected_symbol, selected_tf, limit=1000, strategy_id=current_strategy_id)
        if result.get('ok'):
            ohlcv_data = result.get('data', [])
            markers = result.get('markers', [])
    
    if not ohlcv_data:
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
    
    # 🔥 生成自定义 HTML 组件
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
                
                priceInfo.innerHTML = `💰 ${{price}} | <span class="${{changeClass}}">${{changeIcon}} ${{change}}%</span>`;
                
                const now = new Date();
                updateTime.textContent = `🔄 ${{now.toLocaleTimeString()}}`;
            }}
            
            // 初始状态
            if (initialCandles.length > 0) {{
                updateStatus(initialCandles[initialCandles.length - 1]);
            }}
            
            // 🔥 实时更新函数
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
                        
                        // 🔥 增量更新：只更新最后一根K线
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
            
            // 🔥 定时刷新
            setInterval(fetchAndUpdate, {refresh_interval * 1000});
        </script>
    </body>
    </html>
    '''
    
    # 渲染组件
    components.html(html_content, height=550)


def _render_kline_chart_core(selected_symbol, selected_tf, fetch_btn, api_status, is_auto_refresh=False):
    """
    🔥 K线图核心渲染逻辑
    """
    # 🔥 获取当前选择的策略ID（用于计算信号标记）
    current_strategy_id = st.session_state.get('selected_strategy_id', 'strategy_v2')
    
    # 🔥 获取 K线数据 - 优先 Market API，回退直连 OKX
    ohlcv_data = []
    api_markers = []  # 🔥 API 返回的策略信号标记
    data_source = ""
    
    # 🔥 自动刷新时不计算策略信号（性能优化）
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
    
    # 🔥 转换数据为 Lightweight Charts 格式
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
    
    # 🔥 使用 API 返回的策略信号标记（已在后端计算完成）
    markers = api_markers if api_markers else []
    signal_info = None  # 最新信号信息
    
    # 🔥 信号标记缓存（自动刷新时复用之前的信号，避免重复计算）
    markers_cache_key = f"markers_{selected_symbol}_{selected_tf}_{current_strategy_id}"
    if markers:
        # 有新的信号标记，更新缓存
        st.session_state[markers_cache_key] = markers
    elif is_auto_refresh and markers_cache_key in st.session_state:
        # 自动刷新时，复用缓存的信号标记
        markers = st.session_state[markers_cache_key]
    
    # 🔥 如果 API 没有返回 markers（直连模式或自动刷新），尝试本地计算或使用缓存
    if not markers and ohlcv_data and not is_auto_refresh:
        try:
            # 动态加载策略模块
            from strategy_registry import get_strategy_registry
            registry = get_strategy_registry()
            strategy_class = registry.get_strategy_class(current_strategy_id)
            
            if strategy_class:
                strategy = strategy_class()
                
                # 将 OHLCV 数据转换为 DataFrame
                df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                
                # 检查数据量是否足够
                min_bars = 200 if current_strategy_id == 'strategy_v1' else 1000
                if len(df) >= min_bars:
                    # 计算技术指标
                    try:
                        df_with_indicators = strategy.calculate_indicators(df)
                    except ValueError:
                        df_with_indicators = None
                    
                    if df_with_indicators is not None:
                        # 🔥 遍历最近 100 根 K线，检查信号
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
    
    # 🔥 提取最新信号信息（用于底部显示）
    if markers:
        latest_marker = markers[-1]
        signal_info = {
            'signal': 'BUY' if 'BUY' in latest_marker.get('text', '') else 'SELL',
            'price': candle_data[-1]['close'] if candle_data else 0,
            'reason': latest_marker.get('text', '').replace('\n', ' ')
        }
    
    # 🔥 渲染 Lightweight Charts
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
        
        # 🔥 统计买卖信号数量
        buy_count = len([m for m in markers if 'BUY' in m.get('text', '')])
        sell_count = len([m for m in markers if 'SELL' in m.get('text', '')])
        signal_summary = f"🎯 {buy_count}买/{sell_count}卖" if markers else "🎯 无信号"
        
        # 🔥 实时价格显示
        latest_price = latest['close']
        price_display = f"${latest_price:,.2f}" if latest_price < 1000 else f"${latest_price:,.0f}"
        
        col_stat1, col_stat2, col_stat3, col_stat4, col_stat5, col_stat6 = st.columns(6)
        with col_stat1:
            st.caption(f"💰 {price_display}")
        with col_stat2:
            st.caption(f"🕐 {latest_time_str}")
        with col_stat3:
            st.caption(f"{change_icon} {price_change:+.2f}%")
        with col_stat4:
            st.caption(f"📡 {data_source}")
        with col_stat5:
            st.caption(signal_summary)
        with col_stat6:
            st.caption(f"📊 {len(candle_data)} bars")
    
    # 🔥 显示最新信号状态
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
    st.plotly_chart(fig, use_container_width=True, config=config)


@st.fragment(run_every=2)
def _render_dashboard_cards_fragment(view_model, actions):
    """
    🔥 实盘监控卡片 Fragment - 每2秒自动刷新
    
    使用 @st.fragment(run_every=2) 实现局部自动刷新
    只刷新价格和状态，不影响其他组件
    """
    c1, c2, c3, c4 = st.columns(4)
    
    # session_state 获取 env_mode
    env_mode = st.session_state.get('env_mode', view_model.get("env_mode", "💰 实盘"))
    trading_active = view_model.get("trading_active", False)
    open_positions = view_model.get("open_positions", {})
    
    # 🔥 实时获取 BTC 价格（每次 fragment 刷新都会重新获取）
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


def render_dashboard(view_model, actions):
    """渲染主仪表盘"""
    # 页面样式已在theme_tiktok.css中定义
    
    # 🔥 从 view_model 获取关键变量
    open_positions = view_model.get("open_positions", {})
    env_mode = st.session_state.get('env_mode', view_model.get("env_mode", "💰 实盘"))
    
    # 主页面布局
    col_main, col_chat = st.columns([7, 3])
    
    with col_main:
        # 🔥 实盘监控卡片（使用 fragment 局部刷新）
        st.subheader("📊 实盘监控")
        _render_dashboard_cards_fragment(view_model, actions)
        
        st.divider()
        
        # 【C】修复: 系统控制精简为 3 个按钮
        st.subheader("🎮 系统控制")
        
        # 🔥 从数据库读取真实的交易状态
        bot_config = actions.get("get_bot_config", lambda: {})()
        db_enable_trading = bot_config.get("enable_trading", 0) == 1
        
        # 显示当前交易状态(基于数据库)
        if db_enable_trading:
            st.success("🟢 交易已启用")
        else:
            st.info("🔴 交易已关闭")
        
        # 🔥 炫酷按钮样式
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
            if st.button("✅ 启用交易", width="stretch", disabled=db_enable_trading):
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
            
            if st.button("🔥 一键平仓", width="stretch"):
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
                    actions.get("set_control_flags", lambda **kwargs: None)(emergency_flatten=1)
                    flatten_time = time.time() - flatten_start
                    st.session_state.flatten_confirm_pending = False
                    st.warning(f"⚠️ 已发送平仓信号 | 持仓 {len(open_positions)} | 耗时: {flatten_time:.2f}s")
                    time.sleep(0.5)
                    st.rerun()
            with col_cancel:
                if st.button("取消", width="stretch"):
                    st.session_state.flatten_confirm_pending = False
                    st.rerun()
        
        st.caption("💡 交易模式通过侧边栏设置")
        
        st.divider()
        
        # 情绪接口显示
        st.subheader("😰 市场情绪")
        with st.expander("情绪分析", expanded=False):
            # 获取情绪数据
            @st.cache_data(ttl=60)  # 60秒缓存, 避免频繁请求
            def fetch_sentiment():
                try:
                    response = requests.get("https://api.alternative.me/fng/")  # 情绪API
                    data = response.json()
                    return data["data"][0]["value"], data["data"][0]["value_classification"]
                except Exception as e:
                    st.error(f"情绪API请求失败: {str(e)[:30]}...")  # 显示错误摘要
                    return "----", "未知"  # 占位            
            fear_value, fear_level = fetch_sentiment()
            
            # 显示恐惧与贪婪指数
            col1, col2 = st.columns(2)
            with col1:
                st.metric("恐惧与贪婪指数", fear_value)
            with col2:
                st.metric("情绪水平", fear_level)
            
            # 情绪解释
            if fear_value != "----":
                try:
                    fear_num = int(fear_value)
                    if fear_num <= 20:
                        st.warning("市场处于极度恐惧状态, 可能是买入机会")
                    elif fear_num >= 80:
                        st.warning("市场处于极度贪婪状态, 可能是卖出机会")
                    else:
                        st.info("市场情绪较为中性")
                except ValueError:
                    pass
            
            # 情绪历史图表占位
            st.caption("情绪历史数据加载..")
        
        st.divider()
        
        # 持仓分析
        st.subheader("📈 持仓分析")
        pos_stats_col1, pos_stats_col2 = st.columns([2, 1])
        
        with pos_stats_col1:
            # 持仓详细分析(包含主仓和对冲仓)
            has_positions = open_positions or view_model.get("hedge_positions", {})
            
            if has_positions:
                # 构建持仓数据
                pos_data = []
                
                # 主仓数据
                for symbol, pos in open_positions.items():
                    if pos.get("size", 0) > 0:
                        pos_data.append({
                            "币种": symbol,
                            "类型": "主仓",
                            "方向": pos.get("side", "LONG"),
                            "仓位": f"${pos.get('size', 0):.2f}",
                            "入场": f"${pos.get('entry_price', 0):.4f}",
                            "当前": view_model.get("current_prices", {}).get(symbol, "----"),
                            "浮盈": f"${pos.get('pnl', 0):+.2f}"
                        })
                
                # 对冲仓数据
                for symbol, hedge_list in view_model.get("hedge_positions", {}).items():
                    for idx, pos in enumerate(hedge_list):
                        if pos.get("size", 0) > 0:
                            pos_data.append({
                                "币种": symbol,
                                "类型": f"对冲仓{idx+1}",
                                "方向": pos.get("side", "SHORT"),
                                "仓位": f"${pos.get('size', 0):.2f}",
                                "入场": f"${pos.get('entry_price', 0):.4f}",
                                "当前": view_model.get("current_prices", {}).get(symbol, "----"),
                                "浮盈": f"${pos.get('pnl', 0):+.2f}"
                            })
                
                # 显示持仓表格
                if pos_data:
                    df_positions = pd.DataFrame(pos_data)
                    st.dataframe(df_positions, width="stretch")
            else:
                st.info("暂无持仓数据")
        
        st.divider()
        
        # 模拟账户统计(如果是实盘测试模式)
        if env_mode == "🛰实盘测试":
            st.subheader("📊 模拟账户统计")
            
            try:
                # 从view_model获取模拟账户数据
                sim_stats = view_model.get("simulation_stats", {})
                
                if sim_stats:
                    # 显示关键指标
                    sim_col1, sim_col2, sim_col3, sim_col4 = st.columns(4)
                    with sim_col1:
                        st.metric("模拟净值", f"${sim_stats.get('current_equity', 0):.2f}", 
                                 delta=f"+${sim_stats.get('current_equity', 0) - sim_stats.get('initial_balance', 0):.2f}")
                    with sim_col2:
                        st.metric("总收益率", f"{sim_stats.get('total_return', 0):+.2f}%")
                    with sim_col3:
                        st.metric("总交易", f"{sim_stats.get('total_trades', 0)}", 
                                 delta=f"胜率 {sim_stats.get('win_rate', 0):.1f}%")
                    with sim_col4:
                        st.metric("最大回撤", f"{sim_stats.get('max_drawdown', 0):.2f}%")
            except Exception as e:
                st.warning(f"模拟引擎未启动: {str(e)}")
        
        st.divider()
        
        # 手动扫描
        st.subheader("📡 手动扫描")
        with st.expander("扫描设置", expanded=False):
            scan_syms = st.multiselect("目标", st.session_state.auto_symbols, default=st.session_state.auto_symbols[:1])
            scan_tf = st.selectbox("周期", ["3m", "5m", "15m", "30m", "1h", "4h"], index=2)
            if st.button(f"立即扫描 ({scan_tf})"):
                # 调用actions中的扫描函数
                res = actions.get("manual_scan", lambda s, t: [])(scan_syms, scan_tf)
                if res: 
                    st.dataframe(pd.DataFrame(res), width="stretch")
                else: 
                    st.info("无数据")
        
        st.divider()
        
        # 🔥 K线图展开窗口（使用独立 fragment，支持折叠状态检测）
        st.subheader("📊 K线图分析")
        _render_kline_section_fragment(view_model, actions)
        
        st.divider()
        
        # 交易记录和当前持仓
        c_log1, c_log2 = st.columns([1, 1])
        with c_log1:
            st.subheader("📜 历史记录 (数据库)")
            try:
                # 从view_model获取日志数据
                db_logs = view_model.get("recent_logs", [])
                if db_logs:
                    # 格式化盈亏字段, 添加颜色
                    for log in db_logs:
                        pnl = log.get("pnl", 0)
                        if pnl != 0:
                            log['盈亏'] = f"${pnl:+.2f}"
                        else:
                            log['盈亏'] = "-"
                    
                    st.dataframe(pd.DataFrame(db_logs), width="stretch")
                else: 
                    st.caption("暂无记录")
            except Exception as e:
                st.caption(f"数据库连接中... {e}")
                
        with c_log2:
            st.subheader("📦 当前持仓")
            if open_positions:
                d = [{"币种": k, "方向": v['side'], "仓位": f"${v['size']:.0f}", "入场": f"${v['entry_price']:.4f}"} for k,v in open_positions.items()]
                st.dataframe(pd.DataFrame(d), width="stretch")
            else: 
                st.caption("空仓")


def render_main(view_model, actions):
    """主渲染函数"""
    # 注意: set_page_config 已在 app.py 中调用，此处不再重复调用
    # 否则会导致 StreamlitAPIException: set_page_config() can only be called once
    
    # ============ 自动刷新机制 ============
    # 🔥 移除全局 st_autorefresh，改用 @st.fragment 局部刷新
    # 这样可以避免整个页面重绘，只刷新需要更新的组件
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
        from strategy_registry import validate_and_fallback_strategy
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
    
    # 注入抖音风格CSS
    try:
        with open('assets/theme_tiktok.css', 'r', encoding='utf-8') as f:
            css_content = f.read()
        st.markdown(f'<style>{css_content}</style>', unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"CSS文件加载失败: {e}")
    
    # 渲染侧边栏
    render_sidebar(view_model, actions)
    
    # 渲染主仪表盘
    render_dashboard(view_model, actions)