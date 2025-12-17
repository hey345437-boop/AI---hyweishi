import os
import json

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
OKX_API_KEY = os.getenv("OKX_API_KEY", "")
OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE", "")
OKX_MARKET_TYPE = os.getenv("OKX_MARKET_TYPE", "swap")
OKX_TD_MODE = os.getenv("OKX_TD_MODE", "cross")

# 🔥 重要：OKX_SANDBOX 已废弃，强制为 False
# 本系统只支持两种模式：live（实盘）和 paper_on_real（实盘测试）
# 两种模式都必须使用实盘 API Key，禁止 demo/sandbox
OKX_SANDBOX = False  # 强制禁用，忽略环境变量

# 运行模式：live（实盘下单）或 paper_on_real（实盘行情+本地模拟）
# 注意：'sim' 和 'paper' 会被自动映射为 'paper_on_real'
RUN_MODE = os.getenv("RUN_MODE", "paper_on_real")  # live|paper_on_real
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
        "SCAN_INTERVAL_SEC": str(SCAN_INTERVAL_SEC)
    }
    return config
