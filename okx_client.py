"""
OKX 数据读取模块 - 支持 live / live_test / demo 三种模式

功能特性：
1. 三种运行模式：live(实盘交易), live_test(实盘只读), demo(模拟盘)
2. 只读优先：默认仅使用 public 接口，显式传入 allow_private=True 才启用私有接口
3. Router 自动选择是否需要认证
4. demo 模式私有接口自动添加 x-simulated-trading: '1' 头
5. live_test 模式禁止下单操作
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Literal
from enum import Enum

import ccxt
from ccxt.base.errors import (
    NetworkError, 
    ExchangeError, 
    AuthenticationError,
    RateLimitExceeded,
    InvalidOrder
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# 配置定义
# ============================================================================

class Mode(str, Enum):
    """运行模式枚举"""
    LIVE = "live"           # 实盘交易（可读可写）
    LIVE_TEST = "live_test" # 实盘只读（禁止下单）
    DEMO = "demo"           # 模拟盘（需要 x-simulated-trading 头）


class MarketType(str, Enum):
    """市场类型枚举"""
    SPOT = "spot"       # 现货
    SWAP = "swap"       # 永续合约
    MARGIN = "margin"   # 杠杆
    OPTION = "option"   # 期权


@dataclass
class OkxConfig:
    """OKX 配置类"""
    mode: Mode = Mode.LIVE_TEST
    api_key: str = ""
    secret: str = ""
    password: str = ""  # passphrase
    enable_rate_limit: bool = True
    timeout: int = 30000  # 毫秒
    proxy: Optional[str] = None
    market_type: MarketType = MarketType.SWAP
    
    def mask_key(self) -> str:
        """返回脱敏的 API Key（仅显示前4位和后4位）"""
        if len(self.api_key) > 8:
            return f"{self.api_key[:4]}****{self.api_key[-4:]}"
        return "****"
    
    def __repr__(self) -> str:
        return (f"OkxConfig(mode={self.mode.value}, api_key={self.mask_key()}, "
                f"market_type={self.market_type.value})")


# ============================================================================
# Action 路由定义
# ============================================================================

class ActionType(str, Enum):
    """操作类型"""
    PUBLIC = "public"    # 公开接口，无需认证
    PRIVATE = "private"  # 私有接口，需要认证
    TRADE = "trade"      # 交易接口，需要认证且 live_test 禁止


# Action 到类型的映射
ACTION_REGISTRY: Dict[str, ActionType] = {
    # 公开接口
    "public_ticker": ActionType.PUBLIC,
    "public_ohlcv": ActionType.PUBLIC,
    "public_order_book": ActionType.PUBLIC,
    "public_markets": ActionType.PUBLIC,
    "public_time": ActionType.PUBLIC,
    
    # 私有只读接口
    "private_balance": ActionType.PRIVATE,
    "private_positions": ActionType.PRIVATE,
    "private_orders": ActionType.PRIVATE,
    "private_trades": ActionType.PRIVATE,
    
    # 交易接口
    "trade_create_order": ActionType.TRADE,
    "trade_cancel_order": ActionType.TRADE,
    "trade_cancel_all": ActionType.TRADE,
}


class OkxRouter:
    """
    OKX 请求路由器
    
    根据 mode 和 action 自动选择：
    - 是否需要认证
    - 是否需要 x-simulated-trading 头
    - 是否允许执行（live_test 禁止交易）
    """
    
    def __init__(self, mode: Mode):
        self.mode = mode
    
    def get_action_type(self, action: str) -> ActionType:
        """获取 action 的类型"""
        return ACTION_REGISTRY.get(action, ActionType.PUBLIC)
    
    def requires_auth(self, action: str) -> bool:
        """判断 action 是否需要认证"""
        action_type = self.get_action_type(action)
        return action_type in (ActionType.PRIVATE, ActionType.TRADE)
    
    def requires_demo_header(self, action: str) -> bool:
        """判断是否需要 x-simulated-trading 头"""
        if self.mode != Mode.DEMO:
            return False
        return self.requires_auth(action)
    
    def is_allowed(self, action: str) -> tuple[bool, str]:
        """
        判断 action 是否允许执行
        
        Returns:
            (是否允许, 原因)
        """
        action_type = self.get_action_type(action)
        
        if action_type == ActionType.TRADE and self.mode == Mode.LIVE_TEST:
            return False, "live_test mode prohibits trading operations"
        
        return True, ""
    
    def route(self, action: str) -> Dict[str, Any]:
        """
        路由 action，返回配置信息
        
        Returns:
            {
                "allowed": bool,
                "reason": str,
                "requires_auth": bool,
                "requires_demo_header": bool,
                "action_type": ActionType
            }
        """
        allowed, reason = self.is_allowed(action)
        return {
            "allowed": allowed,
            "reason": reason,
            "requires_auth": self.requires_auth(action),
            "requires_demo_header": self.requires_demo_header(action),
            "action_type": self.get_action_type(action)
        }


# ============================================================================
# Exchange 工厂函数
# ============================================================================

def build_okx_exchange(
    config: OkxConfig, 
    for_private: bool = False
) -> ccxt.okx:
    """
    构建 OKX exchange 实例
    
    Args:
        config: OKX 配置
        for_private: 是否用于私有接口（需要 apiKey）
    
    Returns:
        ccxt.okx 实例
    """
    exchange_options: Dict[str, Any] = {
        'enableRateLimit': config.enable_rate_limit,
        'timeout': config.timeout,
        'options': {
            'defaultType': config.market_type.value,
        }
    }
    
    # 代理配置
    if config.proxy:
        exchange_options['proxies'] = {
            'http': config.proxy,
            'https': config.proxy,
        }
        logger.info(f"Using proxy: {config.proxy[:20]}...")
    
    # 私有接口需要 apiKey
    if for_private:
        if not config.api_key or not config.secret or not config.password:
            raise ValueError("Private API requires api_key, secret, and password")
        
        exchange_options['apiKey'] = config.api_key
        exchange_options['secret'] = config.secret
        exchange_options['password'] = config.password
        
        logger.info(f"Building private exchange with key: {config.mask_key()}")
    else:
        logger.info("Building public exchange (no authentication)")
    
    # 创建 exchange 实例
    exchange = ccxt.okx(exchange_options)
    
    # Demo 模式：为私有接口添加 x-simulated-trading 头
    if config.mode == Mode.DEMO and for_private:
        # 重写 sign 方法以添加模拟交易头
        original_sign = exchange.sign
        
        def sign_with_demo_header(path, api='public', method='GET', params={}, headers=None, body=None):
            result = original_sign(path, api, method, params, headers, body)
            if api != 'public':
                if result.get('headers') is None:
                    result['headers'] = {}
                result['headers']['x-simulated-trading'] = '1'
            return result
        
        exchange.sign = sign_with_demo_header
        logger.info("Demo mode: x-simulated-trading header enabled for private requests")
    
    return exchange


# ============================================================================
# OkxClient 主类
# ============================================================================

class OkxClient:
    """
    OKX 客户端 - 只读优先设计
    
    默认仅使用 public 接口获取行情；
    只有在显式传入 allow_private=True 时才初始化带 apiKey 的 exchange。
    """
    
    def __init__(
        self, 
        config: OkxConfig,
        allow_private: bool = False
    ):
        """
        初始化 OKX 客户端
        
        Args:
            config: OKX 配置
            allow_private: 是否允许私有接口（需要 apiKey）
        """
        self.config = config
        self.allow_private = allow_private
        self.router = OkxRouter(config.mode)
        
        # 公开接口 exchange（无需认证）
        self._public_exchange: Optional[ccxt.okx] = None
        
        # 私有接口 exchange（需要认证）
        self._private_exchange: Optional[ccxt.okx] = None
        
        logger.info(f"OkxClient initialized: {config}, allow_private={allow_private}")
    
    @property
    def public_exchange(self) -> ccxt.okx:
        """获取公开接口 exchange（懒加载）"""
        if self._public_exchange is None:
            self._public_exchange = build_okx_exchange(self.config, for_private=False)
        return self._public_exchange
    
    @property
    def private_exchange(self) -> ccxt.okx:
        """获取私有接口 exchange（懒加载）"""
        if not self.allow_private:
            raise RuntimeError(
                "Private API not allowed. Initialize OkxClient with allow_private=True"
            )
        if self._private_exchange is None:
            self._private_exchange = build_okx_exchange(self.config, for_private=True)
        return self._private_exchange
    
    def _check_action(self, action: str) -> None:
        """检查 action 是否允许执行"""
        route_info = self.router.route(action)
        if not route_info["allowed"]:
            raise RuntimeError(f"Action '{action}' not allowed: {route_info['reason']}")
        
        if route_info["requires_auth"] and not self.allow_private:
            raise RuntimeError(
                f"Action '{action}' requires authentication. "
                "Initialize OkxClient with allow_private=True"
            )
    
    # ========================================================================
    # 公开接口（无需认证）
    # ========================================================================
    
    def fetch_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        获取单个交易对的 ticker 数据
        
        Args:
            symbol: 交易对，如 'BTC/USDT:USDT'
        
        Returns:
            Ticker 数据字典
        """
        self._check_action("public_ticker")
        try:
            ticker = self.public_exchange.fetch_ticker(symbol)
            logger.info(f"Fetched ticker for {symbol}: last={ticker.get('last')}")
            return ticker
        except NetworkError as e:
            logger.error(f"Network error fetching ticker: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error fetching ticker: {e}")
            raise
    
    def fetch_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = '1m',
        since: Optional[int] = None,
        limit: int = 200
    ) -> List[List]:
        """
        获取 K 线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期，如 '1m', '5m', '1h', '1d'
            since: 起始时间戳（毫秒）
            limit: 数量限制
        
        Returns:
            OHLCV 数据列表 [[timestamp, open, high, low, close, volume], ...]
        """
        self._check_action("public_ohlcv")
        try:
            ohlcv = self.public_exchange.fetch_ohlcv(symbol, timeframe, since, limit)
            logger.info(f"Fetched {len(ohlcv)} candles for {symbol} ({timeframe})")
            return ohlcv
        except NetworkError as e:
            logger.error(f"Network error fetching OHLCV: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error fetching OHLCV: {e}")
            raise
    
    def fetch_order_book(self, symbol: str, limit: int = 50) -> Dict[str, Any]:
        """
        获取订单簿数据
        
        Args:
            symbol: 交易对
            limit: 深度限制
        
        Returns:
            订单簿数据 {'bids': [...], 'asks': [...], ...}
        """
        self._check_action("public_order_book")
        try:
            order_book = self.public_exchange.fetch_order_book(symbol, limit)
            logger.info(f"Fetched order book for {symbol}: "
                       f"bids={len(order_book.get('bids', []))}, "
                       f"asks={len(order_book.get('asks', []))}")
            return order_book
        except NetworkError as e:
            logger.error(f"Network error fetching order book: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error fetching order book: {e}")
            raise

    
    # ========================================================================
    # 私有接口（需要认证）
    # ========================================================================
    
    def fetch_balance(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        获取账户余额
        
        Args:
            params: 额外参数，如 {'type': 'swap'}
        
        Returns:
            余额数据字典
        """
        self._check_action("private_balance")
        try:
            if params is None:
                params = {}
            # OKX 需要指定账户类型
            if 'type' not in params:
                params['type'] = self.config.market_type.value
            
            balance = self.private_exchange.fetch_balance(params)
            
            # 提取关键信息
            total_usdt = balance.get('USDT', {}).get('total', 0)
            free_usdt = balance.get('USDT', {}).get('free', 0)
            logger.info(f"Fetched balance: USDT total={total_usdt}, free={free_usdt}")
            
            return balance
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except RateLimitExceeded as e:
            logger.error(f"Rate limit exceeded: {e}")
            raise
        except NetworkError as e:
            logger.error(f"Network error fetching balance: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error fetching balance: {e}")
            raise
    
    def fetch_positions(
        self, 
        symbols: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        获取持仓信息
        
        Args:
            symbols: 交易对列表，None 表示获取所有持仓
        
        Returns:
            持仓数据列表
        
        Note:
            ccxt 的 fetch_positions 在某些交易所可能不支持，
            此时返回空列表。
        """
        self._check_action("private_positions")
        try:
            if not hasattr(self.private_exchange, 'fetch_positions'):
                logger.warning("fetch_positions not supported by this exchange")
                return []
            
            positions = self.private_exchange.fetch_positions(symbols)
            
            # 过滤有效持仓
            active_positions = [
                p for p in positions 
                if p.get('contracts', 0) != 0 or p.get('contractSize', 0) != 0
            ]
            logger.info(f"Fetched {len(active_positions)} active positions")
            
            return positions
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except NetworkError as e:
            logger.error(f"Network error fetching positions: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error fetching positions: {e}")
            raise
    
    # ========================================================================
    # 交易接口（live_test 模式禁止）
    # ========================================================================
    
    def create_order(
        self,
        symbol: str,
        side: Literal['buy', 'sell'],
        order_type: Literal['market', 'limit'],
        amount: float,
        price: Optional[float] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        创建订单
        
        Args:
            symbol: 交易对
            side: 方向 'buy' 或 'sell'
            order_type: 订单类型 'market' 或 'limit'
            amount: 数量
            price: 价格（限价单必填）
            params: 额外参数
        
        Returns:
            订单信息
        
        Raises:
            RuntimeError: live_test 模式禁止下单
        """
        self._check_action("trade_create_order")
        
        # 双重检查：live_test 模式禁止下单
        if self.config.mode == Mode.LIVE_TEST:
            raise RuntimeError("live_test mode prohibits order creation")
        
        try:
            if params is None:
                params = {}
            
            order = self.private_exchange.create_order(
                symbol, order_type, side, amount, price, params
            )
            logger.info(f"Created order: {order.get('id')} {side} {amount} {symbol}")
            return order
        except InvalidOrder as e:
            logger.error(f"Invalid order: {e}")
            raise
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            raise
        except ExchangeError as e:
            logger.error(f"Exchange error creating order: {e}")
            raise
    
    def cancel_order(
        self, 
        order_id: str, 
        symbol: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            order_id: 订单 ID
            symbol: 交易对
            params: 额外参数
        
        Returns:
            取消结果
        
        Raises:
            RuntimeError: live_test 模式禁止取消订单
        """
        self._check_action("trade_cancel_order")
        
        if self.config.mode == Mode.LIVE_TEST:
            raise RuntimeError("live_test mode prohibits order cancellation")
        
        try:
            result = self.private_exchange.cancel_order(order_id, symbol, params)
            logger.info(f"Cancelled order: {order_id}")
            return result
        except ExchangeError as e:
            logger.error(f"Exchange error cancelling order: {e}")
            raise
    
    def set_leverage(
        self,
        symbol: str,
        leverage: int,
        margin_mode: str = 'cross',
        pos_side: str = 'long'
    ) -> Dict[str, Any]:
        """
        设置杠杆倍数
        
        Args:
            symbol: 交易对，如 'BTC/USDT:USDT'
            leverage: 杠杆倍数 (1-125，具体取决于交易对)
            margin_mode: 保证金模式 'cross'(全仓) 或 'isolated'(逐仓)
            pos_side: 持仓方向 'long' 或 'short'
        
        Returns:
            设置结果
        
        Raises:
            RuntimeError: live_test 模式禁止设置杠杆
        """
        self._check_action("trade_create_order")  # 使用相同的权限检查
        
        if self.config.mode == Mode.LIVE_TEST:
            raise RuntimeError("live_test mode prohibits leverage setting")
        
        try:
            # OKX 需要先设置保证金模式
            # ccxt 的 set_leverage 方法
            result = self.private_exchange.set_leverage(
                leverage,
                symbol,
                params={
                    'mgnMode': margin_mode,  # cross 或 isolated
                    'posSide': pos_side  # long 或 short
                }
            )
            logger.info(f"Set leverage for {symbol}: {leverage}x ({margin_mode}, {pos_side})")
            return result
        except ExchangeError as e:
            logger.error(f"Exchange error setting leverage: {e}")
            raise
    
    # ========================================================================
    # 便捷方法
    # ========================================================================
    
    def load_markets(self) -> Dict[str, Any]:
        """加载市场信息"""
        self._check_action("public_markets")
        markets = self.public_exchange.load_markets()
        logger.info(f"Loaded {len(markets)} markets")
        return markets
    
    def get_server_time(self) -> int:
        """获取服务器时间"""
        self._check_action("public_time")
        return self.public_exchange.fetch_time()
    
    def close(self) -> None:
        """关闭连接"""
        if self._public_exchange:
            try:
                self._public_exchange.close()
            except Exception:
                pass
        if self._private_exchange:
            try:
                self._private_exchange.close()
            except Exception:
                pass
        logger.info("OkxClient closed")


# ============================================================================
# 从环境变量加载配置
# ============================================================================

def load_config_from_env(mode: Mode) -> OkxConfig:
    """
    从环境变量加载配置
    
    环境变量命名规则：
    - 实盘: OKX_API_KEY_LIVE, OKX_SECRET_LIVE, OKX_PASSPHRASE_LIVE
    - 模拟盘: OKX_API_KEY_DEMO, OKX_SECRET_DEMO, OKX_PASSPHRASE_DEMO
    - 代理: HTTP_PROXY 或 HTTPS_PROXY（如果未设置，自动检测系统代理）
    """
    if mode == Mode.DEMO:
        suffix = "DEMO"
    else:
        suffix = "LIVE"
    
    api_key = os.getenv(f"OKX_API_KEY_{suffix}", "")
    secret = os.getenv(f"OKX_SECRET_{suffix}", "")
    password = os.getenv(f"OKX_PASSPHRASE_{suffix}", "")
    
    # 代理配置：优先使用环境变量，否则自动检测
    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    
    if not proxy:
        # 自动检测系统代理
        try:
            from env_validator import EnvironmentValidator
            proxy_config = EnvironmentValidator.detect_system_proxy()
            proxy = proxy_config.get('https_proxy') or proxy_config.get('http_proxy')
            if proxy:
                logger.info(f"自动检测到系统代理: {proxy}")
        except Exception as e:
            logger.debug(f"自动检测代理失败: {e}")
    
    # 市场类型
    market_type_str = os.getenv("OKX_MARKET_TYPE", "swap").lower()
    market_type = MarketType(market_type_str) if market_type_str in [m.value for m in MarketType] else MarketType.SWAP
    
    return OkxConfig(
        mode=mode,
        api_key=api_key,
        secret=secret,
        password=password,
        proxy=proxy,
        market_type=market_type
    )


# ============================================================================
# 演示代码
# ============================================================================

def demo_public_only():
    """演示：仅使用公开接口（无需 API Key）"""
    print("\n" + "="*60)
    print("Demo: Public API Only (No Authentication)")
    print("="*60)
    
    # 创建只读客户端（不需要 API Key）
    config = OkxConfig(
        mode=Mode.LIVE_TEST,
        market_type=MarketType.SWAP,
        proxy=os.getenv("HTTPS_PROXY")
    )
    
    client = OkxClient(config, allow_private=False)
    
    try:
        # 获取 BTC 行情
        symbol = "BTC/USDT:USDT"
        
        print(f"\n1. Fetching ticker for {symbol}...")
        ticker = client.fetch_ticker(symbol)
        print(f"   Last price: {ticker.get('last')}")
        print(f"   24h volume: {ticker.get('quoteVolume')}")
        
        print(f"\n2. Fetching OHLCV for {symbol}...")
        ohlcv = client.fetch_ohlcv(symbol, '1h', limit=5)
        print(f"   Got {len(ohlcv)} candles")
        if ohlcv:
            print(f"   Latest: O={ohlcv[-1][1]}, H={ohlcv[-1][2]}, L={ohlcv[-1][3]}, C={ohlcv[-1][4]}")
        
        print(f"\n3. Fetching order book for {symbol}...")
        order_book = client.fetch_order_book(symbol, limit=5)
        print(f"   Best bid: {order_book['bids'][0] if order_book['bids'] else 'N/A'}")
        print(f"   Best ask: {order_book['asks'][0] if order_book['asks'] else 'N/A'}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


def demo_private_api(mode: Mode):
    """演示：使用私有接口（需要 API Key）"""
    print("\n" + "="*60)
    print(f"Demo: Private API ({mode.value} mode)")
    print("="*60)
    
    # 从环境变量加载配置
    config = load_config_from_env(mode)
    
    if not config.api_key:
        print(f"Error: No API key found for {mode.value} mode")
        print(f"Please set OKX_API_KEY_{'DEMO' if mode == Mode.DEMO else 'LIVE'} environment variable")
        return
    
    print(f"Using API key: {config.mask_key()}")
    
    client = OkxClient(config, allow_private=True)
    
    try:
        # 获取余额
        print("\n1. Fetching balance...")
        balance = client.fetch_balance()
        
        # 显示 USDT 余额
        usdt = balance.get('USDT', {})
        print(f"   USDT total: {usdt.get('total', 0)}")
        print(f"   USDT free: {usdt.get('free', 0)}")
        print(f"   USDT used: {usdt.get('used', 0)}")
        
        # 获取持仓
        print("\n2. Fetching positions...")
        positions = client.fetch_positions()
        if positions:
            for pos in positions[:3]:  # 只显示前3个
                if pos.get('contracts', 0) != 0:
                    print(f"   {pos.get('symbol')}: {pos.get('contracts')} contracts")
        else:
            print("   No active positions")
        
        # live_test 模式尝试下单（应该失败）
        if mode == Mode.LIVE_TEST:
            print("\n3. Attempting to create order (should fail)...")
            try:
                client.create_order("BTC/USDT:USDT", "buy", "limit", 0.001, 10000)
            except RuntimeError as e:
                print(f"   Expected error: {e}")
        
    except AuthenticationError as e:
        print(f"Authentication failed: {e}")
        print("Please check your API key, secret, and passphrase")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


def demo_router():
    """演示：Router 功能"""
    print("\n" + "="*60)
    print("Demo: Router")
    print("="*60)
    
    for mode in [Mode.LIVE, Mode.LIVE_TEST, Mode.DEMO]:
        print(f"\nMode: {mode.value}")
        router = OkxRouter(mode)
        
        actions = ["public_ohlcv", "private_balance", "trade_create_order"]
        for action in actions:
            info = router.route(action)
            print(f"  {action}:")
            print(f"    allowed={info['allowed']}, auth={info['requires_auth']}, "
                  f"demo_header={info['requires_demo_header']}")


if __name__ == "__main__":
    import sys
    
    print("OKX Client Demo")
    print("===============")
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        mode_arg = sys.argv[1].lower()
        if mode_arg == "live":
            demo_private_api(Mode.LIVE)
        elif mode_arg == "live_test":
            demo_private_api(Mode.LIVE_TEST)
        elif mode_arg == "demo":
            demo_private_api(Mode.DEMO)
        elif mode_arg == "router":
            demo_router()
        else:
            print(f"Unknown mode: {mode_arg}")
            print("Usage: python okx_client.py [live|live_test|demo|router]")
    else:
        # 默认运行公开接口演示
        demo_public_only()
        demo_router()
