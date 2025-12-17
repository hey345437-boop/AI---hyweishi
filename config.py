import os
import json
import logging

logger = logging.getLogger(__name__)


def _load_saved_credentials():
    """
    🔥 启动时加载保存的 API 凭证
    
    优先级：配置文件 > 环境变量
    """
    try:
        from config_manager import get_config_manager
        manager = get_config_manager()
        creds = manager.load_credentials()
        
        # 如果配置文件中有凭证，更新环境变量
        if creds.has_trade_key():
            os.environ["OKX_API_KEY"] = creds.trade_api_key
            os.environ["OKX_API_SECRET"] = creds.trade_api_secret
            os.environ["OKX_API_PASSPHRASE"] = creds.trade_api_passphrase
            logger.info("[config] 从配置文件加载交易 Key")
        
        if creds.has_market_key():
            os.environ["MARKET_DATA_API_KEY"] = creds.market_api_key
            os.environ["MARKET_DATA_SECRET"] = creds.market_api_secret
            os.environ["MARKET_DATA_PASSPHRASE"] = creds.market_api_passphrase
            logger.info("[config] 从配置文件加载行情 Key")
            
    except ImportError:
        pass  # config_manager 未安装，使用环境变量
    except Exception as e:
        logger.warning(f"[config] 加载保存的凭证失败: {e}")


# 🔥 启动时自动加载保存的配置
_load_saved_credentials()


def parse_symbols(symbols_str):
    """解析交易对字符串为字典格式
    
    参数:
    - symbols_str: 交易对字符串，格式为"BTC/USDT:USDT,ETH/USDT:USDT"或"BTC/USDT,ETH/USDT"
    
    返回:
    - 交易对字典，格式为{"BTC/USDT": "USDT", "ETH/USDT": "USDT"}
    """
    symbols = {}
    for pair in symbols_str.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" in pair:
            symbol, quote = pair.split(":", 1)
            symbols[symbol.strip()] = quote.strip()
        elif "/" in pair:
            # 如果没有结算货币，默认使用USDT
            symbols[pair.strip()] = "USDT"
    return symbols

# 环境变量读取与默认值

# 🔥 交易专用 Key（用于下单、撤单、查询持仓）
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE", "")

# 🔥 行情专用 Key（用于 K线、实时行情，建议只读权限）
# 如果未配置，将回退使用交易 Key
MARKET_DATA_API_KEY = os.getenv("MARKET_DATA_API_KEY", "")
MARKET_DATA_SECRET = os.getenv("MARKET_DATA_SECRET", "")
MARKET_DATA_PASSPHRASE = os.getenv("MARKET_DATA_PASSPHRASE", "")

# 交易所配置
OKX_MARKET_TYPE = os.getenv("OKX_MARKET_TYPE", "swap")
OKX_TD_MODE = os.getenv("OKX_TD_MODE", "cross")

# 🔥 重要：OKX_SANDBOX 已废弃，强制为 False
# 本系统只支持两种模式：live（实盘）和 paper_on_real（实盘测试）
# 两种模式都必须使用实盘 API Key，禁止 demo/sandbox
OKX_SANDBOX = False  # 强制禁用，忽略环境变量

# 运行模式：live（实盘下单）或 paper（实盘行情+本地模拟）
# 🔥 统一使用 'live' 和 'paper' 两种模式
# 注意：'sim' 和 'paper_on_real' 会被自动映射为 'paper'
RUN_MODE = os.getenv("RUN_MODE", "paper")  # live|paper
SYMBOLS = os.getenv("SYMBOLS", "BTC/USDT:USDT,ETH/USDT:USDT")
TIMEFRAME = os.getenv("TIMEFRAME", "1m")
SCAN_INTERVAL_SEC = int(os.getenv("SCAN_INTERVAL_SEC", "2"))
EXIT_ON_FATAL = os.getenv("EXIT_ON_FATAL", "false").lower() == "true"
MAX_CYCLE_ERRORS = int(os.getenv("MAX_CYCLE_ERRORS", "10"))

# 解析交易对
TRADE_SYMBOLS = parse_symbols(SYMBOLS)

# 数据库配置
DB_PATH = "quant_system.db"

# 日志配置
LOG_DIR = "logs"
RUNNER_LOG_FILE = "runner.log"

# 控制标志默认值
DEFAULT_STOP_SIGNAL = 0
DEFAULT_PAUSE_TRADING = 0
DEFAULT_RELOAD_CONFIG = 0
DEFAULT_ALLOW_LIVE = 0

# 状态默认值
DEFAULT_ALIVE = 0
DEFAULT_CYCLE_MS = 0
DEFAULT_LAST_ERROR = ""
DEFAULT_LAST_OKX_LATENCY_MS = 0
DEFAULT_LAST_PLAN_ORDER_JSON = "{}"
DEFAULT_POSITIONS_JSON = "{}"

def get_env_config():
    """获取并显示环境变量配置
    
    返回:
    - 环境变量配置字典
    """
    config = {
        "OKX_API_KEY": OKX_API_KEY,
        "OKX_SANDBOX": str(OKX_SANDBOX),
        "RUN_MODE": RUN_MODE,
        "SYMBOLS": SYMBOLS,
        "OKX_MARKET_TYPE": OKX_MARKET_TYPE,
        "OKX_TD_MODE": OKX_TD_MODE,
        "SCAN_INTERVAL_SEC": str(SCAN_INTERVAL_SEC),
        "MARKET_DATA_API_KEY": MARKET_DATA_API_KEY[:8] + "..." if MARKET_DATA_API_KEY else "(未配置)"
    }
    return config


def get_market_data_credentials():
    """获取行情数据专用 API 凭证
    
    🔥 双 Key 机制：优先使用配置管理器，回退到环境变量
    
    返回:
    - (api_key, secret, passphrase, is_dedicated) 元组
      - is_dedicated: True 表示使用独立行情 Key，False 表示回退到交易 Key
    """
    # 尝试使用配置管理器
    try:
        from config_manager import get_config_manager
        return get_config_manager().get_market_credentials()
    except ImportError:
        pass
    
    # 回退到环境变量
    market_key = os.getenv("MARKET_DATA_API_KEY", "")
    market_secret = os.getenv("MARKET_DATA_SECRET", "")
    market_pass = os.getenv("MARKET_DATA_PASSPHRASE", "")
    
    if market_key and market_secret and market_pass:
        return (market_key, market_secret, market_pass, True)
    
    trade_key = os.getenv("OKX_API_KEY", "")
    trade_secret = os.getenv("OKX_API_SECRET", "")
    trade_pass = os.getenv("OKX_API_PASSPHRASE", "")
    return (trade_key, trade_secret, trade_pass, False)


def get_trading_credentials():
    """获取交易专用 API 凭证
    
    🔥 优先使用配置管理器，回退到环境变量
    
    返回:
    - (api_key, secret, passphrase) 元组
    """
    # 尝试使用配置管理器
    try:
        from config_manager import get_config_manager
        return get_config_manager().get_trade_credentials()
    except ImportError:
        pass
    
    # 回退到环境变量
    return (
        os.getenv("OKX_API_KEY", ""),
        os.getenv("OKX_API_SECRET", ""),
        os.getenv("OKX_API_PASSPHRASE", "")
    )
