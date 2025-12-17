# exchange_adapters/okx_adapter.py
# OKX 交易所适配器
# 
# 重要说明：本系统只支持两种模式
# - live: 实盘模式，真实下单
# - paper_on_real: 实盘测试模式，用实盘行情但本地模拟下单
# 
# 两种模式都必须使用实盘 API Key，绝对禁止 demo/sandbox

import ccxt
import logging
import os
import sys
import io
import uuid
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# ============ Windows UTF-8 编码修复 ============
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True
        )

# 添加父目录到路径以导入风控模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from risk_control import RiskControlModule, RiskControlConfig
from order_size_calculator import OrderSizeCalculator, OrderSizeResult

from .base import ExchangeAdapter


# ============ 本地模拟撮合器 (paper_on_real 模式) ============
@dataclass
class PaperOrder:
    """模拟订单"""
    order_id: str
    symbol: str
    side: str
    amount: float
    price: float
    order_type: str
    status: str = 'filled'  # 模拟订单立即成交
    timestamp: int = 0
    pos_side: str = ''
    reduce_only: bool = False


class LocalPaperBroker:
    """
    本地模拟撮合器
    
    用于 paper_on_real 模式，拦截所有交易请求并在本地模拟
    """
    
    def __init__(self):
        self.orders: List[PaperOrder] = []
        self._order_counter = 0
    
    def create_order(self, symbol: str, side: str, amount: float, 
                     order_type: str = 'market', price: float = 0,
                     params: Optional[Dict] = None) -> Dict:
        """模拟下单"""
        self._order_counter += 1
        order_id = f"paper_{int(time.time()*1000)}_{self._order_counter}"
        
        pos_side = params.get('posSide', '') if params else ''
        reduce_only = params.get('reduceOnly', False) if params else False
        
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            timestamp=int(time.time() * 1000),
            pos_side=pos_side,
            reduce_only=reduce_only
        )
        self.orders.append(order)
        
        # 返回类似 ccxt 的订单结构
        return {
            'id': order_id,
            'clientOrderId': params.get('clOrdId', '') if params else '',
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'amount': amount,
            'price': price,
            'status': 'closed',
            'filled': amount,
            'remaining': 0,
            'timestamp': order.timestamp,
            'info': {'paper': True, 'posSide': pos_side}
        }
    
    def cancel_order(self, order_id: str, symbol: str = None) -> Dict:
        """模拟撤单"""
        return {
            'id': order_id,
            'symbol': symbol,
            'status': 'canceled',
            'info': {'paper': True}
        }
    
    def get_orders(self) -> List[Dict]:
        """获取所有模拟订单"""
        return [
            {
                'id': o.order_id,
                'symbol': o.symbol,
                'side': o.side,
                'amount': o.amount,
                'price': o.price,
                'status': o.status,
                'timestamp': o.timestamp
            }
            for o in self.orders
        ]


# 安全的日志流处理器
class SafeStreamHandler(logging.StreamHandler):
    """安全的流处理器，确保 Unicode 字符不会导致崩溃"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            try:
                stream.write(msg + self.terminator)
            except UnicodeEncodeError:
                safe_msg = msg.encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                stream.write(safe_msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


# 配置日志
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

_file_handler = logging.FileHandler(os.path.join(log_dir, 'exchange.log'), encoding='utf-8')
_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

_console_handler = SafeStreamHandler(sys.stdout)
_console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    handlers=[_file_handler, _console_handler]
)
logger = logging.getLogger(__name__)


class OKXEnvironmentError(Exception):
    """OKX 环境配置错误"""
    pass


class OKXAdapter(ExchangeAdapter):
    """
    OKX 交易所适配器
    
    重要：本适配器只支持两种模式
    - live: 实盘模式，真实下单
    - paper_on_real: 实盘测试模式，用实盘行情但本地模拟下单
    
    两种模式都必须使用实盘 API Key，绝对禁止 demo/sandbox
    """
    
    # 禁止的环境配置
    FORBIDDEN_ENVS = {'demo', 'sandbox', 'test'}
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 OKX 适配器
        
        参数:
        - config: 交易所配置
          - api_key: API Key (必须是实盘 Key)
          - api_secret: API Secret
          - api_passphrase: API Passphrase
          - run_mode: 运行模式 ('live' 或 'paper_on_real')
          - sandbox: 必须为 False (会被强制覆盖)
        """
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.secret = config.get('api_secret')
        self.password = config.get('api_passphrase')
        
        # 🔥 关键修复：强制使用实盘模式
        # run_mode: 'live' = 真实下单, 'paper_on_real' = 本地模拟
        self.run_mode = config.get('run_mode', 'paper_on_real')
        
        # 🔥 强制禁用 sandbox/demo
        # 无论传入什么配置，都强制设为 False
        self._sandbox_disabled = True
        
        # 兼容旧配置：将 'sim' 映射到 'paper_on_real'
        if self.run_mode in ('sim', 'paper', 'demo'):
            self.run_mode = 'paper_on_real'
            logger.warning(f"[CONFIG] run_mode '{config.get('run_mode')}' 已映射为 'paper_on_real'")
        
        self.exchange = None
        self.options = config.get('options', {})
        if 'defaultType' not in self.options:
            self.options['defaultType'] = 'swap'
        
        # 连接状态
        self.connection_status = False
        self.last_self_check_time = 0
        self.last_self_check_error = ""
        
        # 风控模块
        risk_config = RiskControlConfig(
            max_order_size=config.get('max_order_size', 1000.0),
            daily_loss_limit_pct=config.get('daily_loss_limit_pct', 0.10)
        )
        self.risk_control = RiskControlModule(risk_config)
        
        # 实盘模式确认标志
        self.live_mode_confirmed = False
        
        # 仓位模式状态
        self._position_mode_set = False
        
        # 信号去重
        self._last_signal_candle = {}
        
        # 杠杆缓存
        self._leverage_cache = {}
        
        # 订单数量计算器
        self.order_size_calculator = OrderSizeCalculator(self)
        
        # 🔥 本地模拟撮合器 (paper_on_real 模式使用)
        self.paper_broker = LocalPaperBroker()
        
    def _validate_environment(self):
        """
        🔥 启动自检：验证环境配置
        
        检查项：
        1. x-simulated-trading 必须为 0
        2. sandbox 必须为 False
        3. 不允许 demo 环境
        
        Raises:
            OKXEnvironmentError: 如果配置不符合要求
        """
        errors = []
        
        # 检查 sandbox 设置
        if hasattr(self.exchange, 'sandbox') and self.exchange.sandbox:
            errors.append("sandbox=True 不允许，必须使用实盘环境")
        
        # 检查 x-simulated-trading header
        headers = getattr(self.exchange, 'headers', {})
        sim_trading = headers.get('x-simulated-trading', '0')
        if str(sim_trading) == '1':
            errors.append("x-simulated-trading=1 不允许，必须为 0")
        
        # 检查 API URL
        if hasattr(self.exchange, 'urls'):
            api_url = self.exchange.urls.get('api', {})
            if isinstance(api_url, dict):
                for key, url in api_url.items():
                    if 'sandbox' in str(url).lower() or 'demo' in str(url).lower():
                        errors.append(f"API URL 包含 sandbox/demo: {url}")
            elif isinstance(api_url, str):
                if 'sandbox' in api_url.lower() or 'demo' in api_url.lower():
                    errors.append(f"API URL 包含 sandbox/demo: {api_url}")
        
        if errors:
            error_msg = (
                "\n" + "="*60 + "\n"
                "🚨 OKX 环境配置错误 - 启动被阻断\n"
                "="*60 + "\n"
                "当前系统只支持两种模式:\n"
                "  - live: 实盘模式（真实下单）\n"
                "  - paper_on_real: 实盘测试模式（实盘行情+本地模拟）\n"
                "\n"
                "两种模式都必须使用实盘 API Key，禁止 demo/sandbox\n"
                "\n"
                "发现的问题:\n"
            )
            for i, err in enumerate(errors, 1):
                error_msg += f"  {i}. {err}\n"
            error_msg += "\n修复方法:\n"
            error_msg += "  1. 确保 .env 中 OKX_SANDBOX=false\n"
            error_msg += "  2. 使用实盘 API Key（不是模拟盘 Key）\n"
            error_msg += "  3. 删除任何 demo/sandbox 相关配置\n"
            error_msg += "="*60
            
            logger.error(error_msg)
            raise OKXEnvironmentError(error_msg)
    
    def _print_startup_summary(self):
        """打印启动自检摘要（静默模式，只记录日志不打印）"""
        # 获取当前配置
        sandbox_status = getattr(self.exchange, 'sandbox', False)
        headers = getattr(self.exchange, 'headers', {})
        sim_trading = headers.get('x-simulated-trading', '0')
        
        # 获取 API URL
        api_url = "unknown"
        if hasattr(self.exchange, 'urls'):
            urls = self.exchange.urls
            if isinstance(urls, dict):
                api = urls.get('api', {})
                if isinstance(api, dict):
                    api_url = api.get('public', api.get('private', str(api)))
                else:
                    api_url = str(api)
        
        # 🔥 只记录日志，不打印到控制台（防止刷屏）
        logger.info(f"OKX适配器初始化: run_mode={self.run_mode}, sandbox={sandbox_status}, sim_trading={sim_trading}")
        
    def normalize_symbol(self, symbol: str) -> str:
        """将 UI 输入的 symbol 转换为 OKX/ccxt 可用的格式"""
        if ':' in symbol:
            return symbol
        if self.options.get('defaultType') == 'spot':
            return symbol
        base, quote = symbol.split('/')
        return f"{base}/{quote}:{quote}"
    
    def initialize(self):
        """初始化 OKX 交易所连接"""
        import time
        import socket
        import requests
        from urllib3.exceptions import MaxRetryError, NewConnectionError
        from requests.exceptions import ConnectionError, Timeout
        
        # 获取代理配置
        http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        proxies = {}
        if http_proxy:
            proxies['http'] = http_proxy
            logger.debug(f"使用HTTP代理: {http_proxy}")
        if https_proxy:
            proxies['https'] = https_proxy
            logger.debug(f"使用HTTPS代理: {https_proxy}")
        
        if self.exchange is None:
            exchange_config = {
                'apiKey': self.api_key,
                'secret': self.secret,
                'password': self.password,
                'enableRateLimit': True,
                'options': self.options,
            }
            
            # 添加代理配置
            if https_proxy:
                exchange_config['proxies'] = {
                    'http': http_proxy or https_proxy,
                    'https': https_proxy
                }
            
            # 创建交易所实例
            self.exchange = ccxt.okx(exchange_config)
            
            # 🔥 关键修复：强制禁用 sandbox 模式
            # 无论任何配置，都强制设为 False
            self.exchange.set_sandbox_mode(False)
            
            # 🔥 关键修复：强制设置 x-simulated-trading=0
            # 确保所有请求都不带模拟交易头
            if not hasattr(self.exchange, 'headers'):
                self.exchange.headers = {}
            self.exchange.headers['x-simulated-trading'] = '0'
            
            logger.info("[FORCED] sandbox=False, x-simulated-trading=0")
            
            # 加载市场数据
            retry_count = 3
            for attempt in range(retry_count):
                try:
                    logger.debug(f"加载市场数据 (尝试 {attempt+1}/{retry_count})")
                    self.exchange.load_markets()
                    logger.info("[OK] OKX markets loaded successfully")
                    break
                except (ConnectionError, Timeout, MaxRetryError, NewConnectionError, socket.timeout) as e:
                    logger.error(f"网络连接错误 (尝试 {attempt+1}/{retry_count}): {e}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                    else:
                        raise
                except Exception as e:
                    logger.error(f"加载市场数据失败 (尝试 {attempt+1}/{retry_count}): {e}")
                    if attempt < retry_count - 1:
                        time.sleep(2)
                    else:
                        raise
        
        # 🔥 启动自检：验证环境配置
        self._validate_environment()
        
        # 打印启动摘要
        self._print_startup_summary()
        
        # 执行连接自检
        self._connection_self_check()
        
        return self.exchange

    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', since: int = None, limit: int = 100, params: dict = None) -> Any:
        """
        获取 K 线数据（始终调用 OKX 实盘）
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期，默认 '1m'
        - since: 起始时间戳（毫秒），用于增量拉取
        - limit: 数量限制，默认 100
        - params: 额外参数
        
        返回:
        - K线数据 [[ts, o, h, l, c, v], ...]
        """
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            
            if since:
                logger.debug(f"Fetching OHLCV for {normalized_symbol}, timeframe: {timeframe}, since: {since}, limit: {limit}")
            else:
                logger.debug(f"Fetching OHLCV for {normalized_symbol}, timeframe: {timeframe}, limit: {limit}")
            
            # 透传给 ccxt，支持 since 参数用于增量拉取
            return self.exchange.fetch_ohlcv(
                normalized_symbol, 
                timeframe, 
                since=since, 
                limit=limit, 
                params=params or {}
            )
        except ccxt.NetworkError as e:
            logger.error(f"Network error when fetching OHLCV for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when fetching OHLCV for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when fetching OHLCV for {symbol}: {e}")
            raise
    
    def _connection_self_check(self) -> bool:
        """连接自检，验证OKX连接是否正常"""
        logger.debug("正在执行OKX连接自检...")
        self.connection_status = False
        self.last_self_check_time = time.time()
        self.last_self_check_error = ""
        
        try:
            test_symbol = "BTC/USDT:USDT"
            logger.debug(f"正在测试获取 {test_symbol} 的ticker数据...")
            
            ticker = self.exchange.fetch_ticker(test_symbol)
            if ticker and 'last' in ticker:
                logger.debug(f"OKX连接成功 - 实时价格: {ticker['last']}")
                
                ohlcv = self.exchange.fetch_ohlcv(test_symbol, timeframe='1m', limit=5)
                if ohlcv and len(ohlcv) > 0:
                    logger.debug(f"K线数据获取成功 - 共 {len(ohlcv)} 根K线")
                    self.connection_status = True
                    self.last_self_check_error = ""
                    return True
                else:
                    logger.error("K线数据获取失败 - 返回数据为空")
                    self.last_self_check_error = "K线数据获取失败"
                    return False
            else:
                logger.error("Ticker数据获取失败 - 返回数据无效")
                self.last_self_check_error = "Ticker数据获取失败"
                return False
        except ccxt.NetworkError as e:
            logger.error(f"网络错误 - {e}")
            self.last_self_check_error = f"网络错误: {str(e)}"
            return False
        except ccxt.ExchangeError as e:
            logger.error(f"交易所错误 - {e}")
            self.last_self_check_error = f"交易所错误: {str(e)}"
            return False
        except Exception as e:
            logger.error(f"连接自检失败 - {e}")
            self.last_self_check_error = f"自检失败: {str(e)}"
            return False
    
    def fetch_ticker(self, symbol: str) -> Any:
        """获取实时价格（始终调用 OKX 实盘）"""
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            logger.debug(f"Fetching ticker for {normalized_symbol}")
            
            return self.exchange.fetch_ticker(normalized_symbol)
        except ccxt.NetworkError as e:
            logger.error(f"Network error when fetching ticker for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when fetching ticker for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when fetching ticker for {symbol}: {e}")
            raise
    
    def fetch_orderbook(self, symbol: str) -> Any:
        """获取市场深度（始终调用 OKX 实盘）"""
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            logger.debug(f"Fetching orderbook for {normalized_symbol}")
            
            return self.exchange.fetch_orderbook(normalized_symbol)
        except ccxt.NetworkError as e:
            logger.error(f"Network error when fetching orderbook for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when fetching orderbook for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when fetching orderbook for {symbol}: {e}")
            raise
    
    def fetch_balance(self, params: Optional[Dict] = None) -> Any:
        """获取账户余额（始终调用 OKX 实盘）"""
        try:
            if self.exchange is None:
                self.initialize()
            
            if params is None:
                params = {}
            if 'type' not in params:
                params['type'] = 'swap'
            
            logger.debug(f"Fetching balance with params: {params}")
            result = self.exchange.fetch_balance(params)
            
            if result is None:
                logger.warning("fetch_balance returned None, returning empty balance")
                return {'total': {}, 'free': {}, 'used': {}}
            
            return result
        except ccxt.NetworkError as e:
            logger.error(f"Network error when fetching balance: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when fetching balance: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when fetching balance: {e}")
            raise
    
    def fetch_positions(self, symbols: Optional[list] = None) -> Any:
        """获取持仓信息（始终调用 OKX 实盘）"""
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbols = None
            if symbols:
                normalized_symbols = [self.normalize_symbol(symbol) for symbol in symbols]
                logger.debug(f"Fetching positions for {normalized_symbols}")
            else:
                logger.debug("Fetching all positions")
            
            return self.exchange.fetch_positions(normalized_symbols)
        except ccxt.NetworkError as e:
            logger.error(f"Network error when fetching positions: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when fetching positions: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when fetching positions: {e}")
            raise
    
    def generate_client_order_id(self, symbol: str, side: str) -> str:
        """生成唯一的客户端订单ID"""
        base = symbol.split('/')[0].replace('-', '').replace(':', '')[:4]
        ts = int(time.time() * 1000) % 10000000000
        uid = uuid.uuid4().hex[:6]
        return f"{side[0]}_{base}_{ts}_{uid}"
    
    def create_order(self, symbol: str, side: str, amount: float, order_type: str = 'market', 
                     params: Optional[Dict] = None, reduce_only: bool = False) -> Any:
        """
        下单 - 根据 run_mode 路由到实盘或本地模拟
        
        - live 模式: 调用 OKX 实盘下单
        - paper_on_real 模式: 路由到 LocalPaperBroker 本地模拟
        """
        try:
            if self.exchange is None:
                self.initialize()
            
            # 风控检查
            validation_result = self.risk_control.validate_order(amount, symbol)
            if not validation_result.is_valid:
                error_msg = f"风控拒绝订单: {validation_result.error_message}"
                logger.error(f"[BLOCKED] {error_msg}")
                raise ValueError(error_msg)
            
            normalized_symbol = self.normalize_symbol(symbol)
            
            if params is None:
                params = {}
            
            if 'clOrdId' not in params:
                params['clOrdId'] = self.generate_client_order_id(symbol, side)
            
            if reduce_only and 'reduceOnly' not in params:
                params['reduceOnly'] = True
            
            # 🔥 关键路由：根据 run_mode 决定是否真实下单
            if self.run_mode == 'paper_on_real':
                # paper_on_real 模式：路由到本地模拟
                logger.warning(
                    f"[paper] blocked_real_trade op=create_order "
                    f"symbol={normalized_symbol} side={side} amount={amount} "
                    f"reason=paper_on_real"
                )
                print(
                    f"[paper] blocked_real_trade op=create_order "
                    f"symbol={normalized_symbol} side={side} amount={amount} "
                    f"reason=paper_on_real"
                )
                
                # 获取当前价格用于模拟
                try:
                    ticker = self.exchange.fetch_ticker(normalized_symbol)
                    price = ticker.get('last', 0)
                except:
                    price = 0
                
                return self.paper_broker.create_order(
                    symbol=normalized_symbol,
                    side=side,
                    amount=amount,
                    order_type=order_type,
                    price=price,
                    params=params
                )
            else:
                # live 模式：调用 OKX 实盘
                logger.info(
                    f"[LIVE] Creating order: {side} {amount} {normalized_symbol} ({order_type}) "
                    f"clOrdId={params.get('clOrdId')} reduceOnly={params.get('reduceOnly', False)}"
                )
                return self.exchange.create_order(
                    normalized_symbol, order_type, side, amount, price=None, params=params
                )
                
        except ValueError:
            raise
        except Exception as e:
            error_type = type(e).__name__
            if 'NetworkError' in error_type:
                logger.error(f"Network error when creating order for {symbol}: {e}")
            elif 'ExchangeError' in error_type:
                logger.error(f"Exchange error when creating order for {symbol}: {e}")
            else:
                logger.error(f"Unexpected error when creating order for {symbol}: {e}")
            raise
    
    def create_market_order(self, symbol: str, side: str, amount: float, 
                            params: Optional[Dict] = None, reduce_only: bool = False) -> Any:
        """创建市价单"""
        return self.create_order(symbol, side, amount, 'market', params, reduce_only)
    
    def create_close_order(self, symbol: str, side: str, amount: float, 
                           params: Optional[Dict] = None) -> Any:
        """创建平仓订单（自动设置 reduceOnly=True）"""
        return self.create_order(symbol, side, amount, 'market', params, reduce_only=True)
    
    def calculate_order_size(
        self,
        symbol: str,
        equity: float,
        risk_pct: float,
        leverage: int,
        price: float
    ) -> OrderSizeResult:
        """计算订单数量"""
        result = self.order_size_calculator.calculate(
            symbol, equity, risk_pct, leverage, price
        )
        
        if result.is_valid:
            logger.info(result.log_line)
        else:
            logger.warning(result.log_line)
        
        return result
    
    def cancel_order(self, order_id: str, symbol: str = None) -> Any:
        """
        撤单 - 根据 run_mode 路由
        
        - live 模式: 调用 OKX 实盘撤单
        - paper_on_real 模式: 路由到 LocalPaperBroker
        """
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol) if symbol else None
            
            # 🔥 关键路由
            if self.run_mode == 'paper_on_real':
                logger.warning(
                    f"[paper] blocked_real_trade op=cancel_order "
                    f"order_id={order_id} symbol={normalized_symbol} "
                    f"reason=paper_on_real"
                )
                print(
                    f"[paper] blocked_real_trade op=cancel_order "
                    f"order_id={order_id} symbol={normalized_symbol} "
                    f"reason=paper_on_real"
                )
                return self.paper_broker.cancel_order(order_id, normalized_symbol)
            else:
                logger.info(f"[LIVE] Cancelling order {order_id} for {normalized_symbol}")
                return self.exchange.cancel_order(order_id, normalized_symbol)
                
        except ccxt.NetworkError as e:
            logger.error(f"Network error when cancelling order {order_id}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when cancelling order {order_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when cancelling order {order_id}: {e}")
            raise

    def set_margin_mode(self, margin_mode: str, symbol: str) -> Any:
        """设置保证金模式"""
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            logger.info(f"Setting margin mode to {margin_mode} for {normalized_symbol}")
            
            return self.exchange.set_margin_mode(margin_mode, normalized_symbol)
        except ccxt.NetworkError as e:
            logger.error(f"Network error when setting margin mode for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when setting margin mode for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when setting margin mode for {symbol}: {e}")
            raise
    
    def set_leverage(self, leverage: int, symbol: str) -> Any:
        """设置杠杆"""
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            logger.info(f"Setting leverage to {leverage}x for {normalized_symbol}")
            
            return self.exchange.set_leverage(leverage, normalized_symbol)
        except ccxt.NetworkError as e:
            logger.error(f"Network error when setting leverage for {symbol}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error when setting leverage for {symbol}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error when setting leverage for {symbol}: {e}")
            raise
    
    def ensure_position_mode(self, hedged: bool = True) -> bool:
        """确保账户处于正确的仓位模式"""
        if self._position_mode_set:
            return True
            
        try:
            if self.exchange is None:
                self.initialize()
            
            mode = 'long_short_mode' if hedged else 'net_mode'
            logger.info(f"设置仓位模式为: {mode}")
            
            result = self.exchange.set_position_mode(hedged=hedged)
            logger.info(f"仓位模式设置成功: {result}")
            self._position_mode_set = True
            return True
        except ccxt.ExchangeError as e:
            error_str = str(e).lower()
            if 'already' in error_str or 'same' in error_str or '50019' in str(e):
                logger.info(f"仓位模式已经是目标模式: {mode}")
                self._position_mode_set = True
                return True
            logger.error(f"设置仓位模式失败: {e}")
            return False
        except Exception as e:
            logger.error(f"设置仓位模式异常: {e}")
            return False
    
    def ensure_leverage(self, symbol: str, leverage: int) -> bool:
        """确保指定交易对的杠杆设置正确"""
        normalized_symbol = self.normalize_symbol(symbol)
        
        if self._leverage_cache.get(normalized_symbol) == leverage:
            return True
        
        try:
            result = self.set_leverage(leverage, symbol)
            self._leverage_cache[normalized_symbol] = leverage
            logger.info(f"杠杆设置成功: {normalized_symbol} = {leverage}x")
            return True
        except ccxt.ExchangeError as e:
            error_str = str(e).lower()
            if 'same' in error_str or 'already' in error_str:
                self._leverage_cache[normalized_symbol] = leverage
                return True
            logger.error(f"设置杠杆失败 {normalized_symbol}: {e}")
            return False
        except Exception as e:
            logger.error(f"设置杠杆异常 {normalized_symbol}: {e}")
            return False
    
    def should_execute_signal(self, symbol: str, timeframe: str, action: str, 
                              candle_time: int) -> bool:
        """信号去重 - 检查是否应该执行该信号"""
        key = (symbol, timeframe, action)
        
        if key in self._last_signal_candle and self._last_signal_candle[key] == candle_time:
            logger.debug(f"信号去重: {symbol} {timeframe} {action} 已在 {candle_time} 处理过")
            return False
        
        self._last_signal_candle[key] = candle_time
        return True
    
    def clear_signal_cache(self, symbol: str = None, timeframe: str = None):
        """清除信号缓存"""
        if symbol is None and timeframe is None:
            self._last_signal_candle.clear()
            logger.info("已清除所有信号缓存")
        else:
            keys_to_remove = [
                k for k in self._last_signal_candle 
                if (symbol is None or k[0] == symbol) and (timeframe is None or k[1] == timeframe)
            ]
            for k in keys_to_remove:
                del self._last_signal_candle[k]
            logger.info(f"已清除信号缓存: symbol={symbol}, timeframe={timeframe}")
    
    def set_live_mode(self, confirmed: bool = False) -> None:
        """设置实盘模式 - 需要确认"""
        if self.run_mode != 'live':
            logger.info(f"当前模式为 {self.run_mode}，无需确认")
            return
        
        if not confirmed:
            error_msg = (
                "[WARN] 切换到实盘模式需要显式确认！\n"
                "请调用 set_live_mode(confirmed=True) 确认切换。\n"
                "警告：实盘模式将使用真实资金进行交易！"
            )
            logger.warning(error_msg)
            raise ValueError(error_msg)
        
        self.live_mode_confirmed = True
        logger.warning(f"[LIVE] 实盘模式已确认启用 - 用户确认时间: {__import__('datetime').datetime.now()}")
    
    def record_trade_pnl(self, pnl: float) -> None:
        """记录交易盈亏到风控模块"""
        self.risk_control.record_trade_pnl(pnl)
    
    def normalize_position(self, position: Dict) -> Dict:
        """统一持仓字段解析"""
        if not position:
            return {}
        
        contracts = (
            position.get('contracts') or 
            position.get('contractSize') or 
            position.get('positionAmt') or
            (position.get('info', {}).get('pos') if isinstance(position.get('info'), dict) else 0) or
            0
        )
        
        try:
            contracts = float(contracts)
        except (ValueError, TypeError):
            contracts = 0.0
        
        side = position.get('side', '')
        if not side:
            if contracts > 0:
                side = 'long'
            elif contracts < 0:
                side = 'short'
            else:
                side = 'none'
        
        return {
            'symbol': position.get('symbol', ''),
            'contracts': abs(contracts),
            'positionAmt': contracts,
            'side': side.lower(),
            'entryPrice': float(position.get('entryPrice') or position.get('avgPrice') or 0),
            'unrealizedPnl': float(position.get('unrealizedPnl') or position.get('unrealisedPnl') or 0),
            'leverage': int(position.get('leverage') or 1),
            'marginMode': position.get('marginMode') or position.get('marginType') or 'cross',
            'liquidationPrice': float(position.get('liquidationPrice') or 0),
            'notional': float(position.get('notional') or position.get('positionValue') or 0),
            'raw': position
        }
    
    def get_active_positions(self, symbols: Optional[list] = None) -> Dict[str, Dict]:
        """获取活跃持仓（已标准化）"""
        positions = self.fetch_positions(symbols)
        result = {}
        
        for pos in positions:
            normalized = self.normalize_position(pos)
            if normalized.get('contracts', 0) != 0:
                symbol = normalized.get('symbol', '')
                if symbol:
                    result[symbol] = normalized
        
        return result
    
    def close_position(self, symbol: str, pos_side: str = None, amount: float = None) -> Any:
        """
        平仓 - 根据 run_mode 路由
        
        - live 模式: 调用 OKX 实盘平仓
        - paper_on_real 模式: 路由到 LocalPaperBroker
        """
        try:
            if self.exchange is None:
                self.initialize()
            
            normalized_symbol = self.normalize_symbol(symbol)
            
            # 🔥 关键路由
            if self.run_mode == 'paper_on_real':
                logger.warning(
                    f"[paper] blocked_real_trade op=close_position "
                    f"symbol={normalized_symbol} pos_side={pos_side} amount={amount} "
                    f"reason=paper_on_real"
                )
                print(
                    f"[paper] blocked_real_trade op=close_position "
                    f"symbol={normalized_symbol} pos_side={pos_side} amount={amount} "
                    f"reason=paper_on_real"
                )
                
                # 模拟平仓
                side = 'sell' if pos_side == 'long' else 'buy'
                return self.paper_broker.create_order(
                    symbol=normalized_symbol,
                    side=side,
                    amount=amount or 0,
                    order_type='market',
                    params={'posSide': pos_side, 'reduceOnly': True}
                )
            else:
                # live 模式：调用实盘平仓
                logger.info(f"[LIVE] Closing position: {normalized_symbol} {pos_side} amount={amount}")
                
                # 确定平仓方向
                side = 'sell' if pos_side == 'long' else 'buy'
                
                params = {
                    'posSide': pos_side,
                    'reduceOnly': True
                }
                
                return self.exchange.create_order(
                    normalized_symbol, 'market', side, amount, price=None, params=params
                )
                
        except Exception as e:
            logger.error(f"Error closing position for {symbol}: {e}")
            raise
    
    def close(self) -> None:
        """关闭连接"""
        if self.exchange is not None:
            self.exchange.close()
            self.exchange = None
    
    def is_paper_mode(self) -> bool:
        """检查是否为模拟模式"""
        return self.run_mode == 'paper_on_real'
    
    def is_live_mode(self) -> bool:
        """检查是否为实盘模式"""
        return self.run_mode == 'live'
    
    def get_paper_orders(self) -> List[Dict]:
        """获取模拟订单列表（仅 paper_on_real 模式）"""
        return self.paper_broker.get_orders()
