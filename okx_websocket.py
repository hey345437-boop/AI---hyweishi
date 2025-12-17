"""
OKX WebSocket 客户端

支持订阅 K线数据的实时推送，用于：
1. K线图实时更新（低延迟）
2. 交易引擎可选的数据源

使用方式：
- UI K线图：固定使用 WebSocket（实时更新）
- 交易引擎：默认 REST，可切换为 WebSocket
"""

import json
import time
import threading
import logging
from typing import Dict, List, Callable, Optional, Any
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

# WebSocket 依赖检查
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client 未安装，WebSocket 功能不可用。请运行: pip install websocket-client")


class OKXWebSocketClient:
    """
    OKX WebSocket 客户端
    
    功能：
    - 订阅 K线数据 (candle)
    - 订阅实时行情 (ticker)
    - 自动重连
    - 心跳保活
    """
    
    # OKX WebSocket 地址
    # 🔥 K线数据使用 Business 端点，不是 Public 端点
    # Public 端点用于: tickers, trades, books 等
    # Business 端点用于: candle (K线), mark-price-candle 等
    WS_BUSINESS_URL = "wss://ws.okx.com:8443/ws/v5/business"
    WS_BUSINESS_URL_AWS = "wss://wsaws.okx.com:8443/ws/v5/business"
    WS_PUBLIC_URL = "wss://ws.okx.com:8443/ws/v5/public"
    WS_PUBLIC_URL_AWS = "wss://wsaws.okx.com:8443/ws/v5/public"
    
    def __init__(self, use_aws: bool = False):
        """
        初始化 WebSocket 客户端
        
        Args:
            use_aws: 是否使用 AWS 节点（海外用户推荐）
        """
        if not WEBSOCKET_AVAILABLE:
            raise ImportError("websocket-client 未安装，请运行: pip install websocket-client")
        
        # 🔥 使用 Business 端点（K线数据需要此端点）
        self.ws_url = self.WS_BUSINESS_URL_AWS if use_aws else self.WS_BUSINESS_URL
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        
        # 连接状态
        self.connected = False
        self.reconnecting = False
        self.should_stop = False
        
        # 订阅管理
        self.subscriptions: Dict[str, Dict] = {}  # {channel_key: subscription_info}
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)  # {channel_key: [callbacks]}
        
        # K线数据缓存
        self.candle_cache: Dict[str, List] = {}  # {inst_id:timeframe: [[ts, o, h, l, c, v], ...]}
        self.candle_cache_lock = threading.Lock()
        
        # 行情数据缓存
        self.ticker_cache: Dict[str, Dict] = {}  # {inst_id: ticker_data}
        
        # 心跳
        self.last_pong_time = 0
        self.heartbeat_thread: Optional[threading.Thread] = None
        
        # 重连配置
        self.reconnect_delay = 5  # 重连延迟（秒）
        self.max_reconnect_attempts = 10
        self.reconnect_attempts = 0
    
    def start(self) -> bool:
        """
        启动 WebSocket 连接
        
        Returns:
            是否启动成功
        """
        if self.connected:
            logger.info("[WS] 已连接，无需重复启动")
            return True
        
        self.should_stop = False
        
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            
            # 在后台线程运行
            self.ws_thread = threading.Thread(
                target=self._run_forever,
                daemon=True,
                name="OKX-WebSocket"
            )
            self.ws_thread.start()
            
            # 等待连接建立
            for _ in range(100):  # 最多等待 10 秒
                if self.connected:
                    logger.info(f"[WS] 连接成功: {self.ws_url}")
                    return True
                time.sleep(0.1)
            
            logger.warning("[WS] 连接超时")
            return False
            
        except Exception as e:
            logger.error(f"[WS] 启动失败: {e}")
            return False
    
    def stop(self):
        """停止 WebSocket 连接"""
        self.should_stop = True
        
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        
        self.connected = False
        logger.info("[WS] 已停止")
    
    def _run_forever(self):
        """WebSocket 运行循环"""
        while not self.should_stop:
            try:
                self.ws.run_forever(
                    ping_interval=25,
                    ping_timeout=10
                )
            except Exception as e:
                logger.error(f"[WS] 运行异常: {e}")
            
            if not self.should_stop:
                self._handle_reconnect()
    
    def _handle_reconnect(self):
        """处理重连"""
        if self.reconnecting or self.should_stop:
            return
        
        self.reconnecting = True
        self.connected = False
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            logger.error(f"[WS] 重连次数超限 ({self.max_reconnect_attempts})，停止重连")
            self.should_stop = True
            self.reconnecting = False
            return
        
        delay = min(self.reconnect_delay * self.reconnect_attempts, 60)
        logger.info(f"[WS] 将在 {delay}s 后重连 (第 {self.reconnect_attempts} 次)")
        time.sleep(delay)
        
        self.reconnecting = False
    
    def _on_open(self, ws):
        """连接建立回调"""
        self.connected = True
        self.reconnect_attempts = 0
        self.last_pong_time = time.time()
        logger.info("[WS] 连接已建立")
        
        # 重新订阅之前的频道
        self._resubscribe_all()
        
        # 启动心跳线程
        self._start_heartbeat()
    
    def _on_message(self, ws, message):
        """消息接收回调"""
        try:
            # 🔥 处理纯文本 pong 响应
            if message == "pong":
                self.last_pong_time = time.time()
                return
            
            data = json.loads(message)
            
            # 处理 JSON 格式的 pong
            if data.get("event") == "pong":
                self.last_pong_time = time.time()
                return
            
            # 处理订阅确认
            if data.get("event") == "subscribe":
                logger.debug(f"[WS] 订阅确认: {data.get('arg', {})}")
                return
            
            # 处理错误
            if data.get("event") == "error":
                logger.error(f"[WS] 错误: {data}")
                return
            
            # 处理数据推送
            if "data" in data and "arg" in data:
                self._handle_data_push(data)
                
        except json.JSONDecodeError:
            # 忽略无法解析的消息（可能是心跳响应）
            if message.strip().lower() != "pong":
                logger.warning(f"[WS] 无法解析消息: {message[:100]}")
        except Exception as e:
            logger.error(f"[WS] 消息处理异常: {e}")
    
    def _on_error(self, ws, error):
        """错误回调"""
        logger.error(f"[WS] 错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        self.connected = False
        logger.info(f"[WS] 连接关闭: {close_status_code} - {close_msg}")
    
    def _start_heartbeat(self):
        """启动心跳线程"""
        def heartbeat_loop():
            while self.connected and not self.should_stop:
                try:
                    if self.ws and self.connected:
                        self.ws.send("ping")
                except Exception as e:
                    logger.warning(f"[WS] 心跳发送失败: {e}")
                time.sleep(25)
        
        self.heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            daemon=True,
            name="WS-Heartbeat"
        )
        self.heartbeat_thread.start()
    
    def _resubscribe_all(self):
        """重新订阅所有频道"""
        for channel_key, sub_info in self.subscriptions.items():
            try:
                self._send_subscribe(sub_info["channel"], sub_info["inst_id"], sub_info.get("extra_args", {}))
                logger.debug(f"[WS] 重新订阅: {channel_key}")
            except Exception as e:
                logger.error(f"[WS] 重新订阅失败 {channel_key}: {e}")
    
    def _send_subscribe(self, channel: str, inst_id: str, extra_args: Dict = None):
        """发送订阅请求"""
        args = {
            "channel": channel,
            "instId": inst_id
        }
        if extra_args:
            args.update(extra_args)
        
        msg = {
            "op": "subscribe",
            "args": [args]
        }
        
        if self.ws and self.connected:
            self.ws.send(json.dumps(msg))
    
    def _handle_data_push(self, data: Dict):
        """处理数据推送"""
        arg = data.get("arg", {})
        channel = arg.get("channel", "")
        inst_id = arg.get("instId", "")
        
        # K线数据
        if channel.startswith("candle"):
            self._handle_candle_data(arg, data.get("data", []))
        
        # 行情数据
        elif channel == "tickers":
            self._handle_ticker_data(inst_id, data.get("data", []))
        
        # 触发回调
        channel_key = f"{channel}:{inst_id}"
        for callback in self.callbacks.get(channel_key, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"[WS] 回调执行失败: {e}")
    
    def _handle_candle_data(self, arg: Dict, candles: List):
        """处理 K线数据"""
        channel = arg.get("channel", "")
        inst_id = arg.get("instId", "")
        
        # 提取时间周期 (candle1m -> 1m)
        timeframe = channel.replace("candle", "")
        cache_key = f"{inst_id}:{timeframe}"
        
        with self.candle_cache_lock:
            if cache_key not in self.candle_cache:
                self.candle_cache[cache_key] = []
            
            for candle in candles:
                # OKX 格式: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
                # 转换为标准格式: [ts, o, h, l, c, vol]
                ts = int(candle[0])
                o = float(candle[1])
                h = float(candle[2])
                l = float(candle[3])
                c = float(candle[4])
                vol = float(candle[5])
                
                standard_candle = [ts, o, h, l, c, vol]
                
                # 更新或追加
                existing = self.candle_cache[cache_key]
                updated = False
                for i, ec in enumerate(existing):
                    if ec[0] == ts:
                        existing[i] = standard_candle
                        updated = True
                        break
                
                if not updated:
                    existing.append(standard_candle)
                    # 保持排序
                    existing.sort(key=lambda x: x[0])
                    # 限制缓存大小
                    if len(existing) > 1000:
                        self.candle_cache[cache_key] = existing[-1000:]
    
    def _handle_ticker_data(self, inst_id: str, tickers: List):
        """处理行情数据"""
        for ticker in tickers:
            self.ticker_cache[inst_id] = {
                "symbol": inst_id,
                "last": float(ticker.get("last", 0)),
                "bid": float(ticker.get("bidPx", 0)),
                "ask": float(ticker.get("askPx", 0)),
                "high": float(ticker.get("high24h", 0)),
                "low": float(ticker.get("low24h", 0)),
                "volume": float(ticker.get("vol24h", 0)),
                "timestamp": int(ticker.get("ts", 0))
            }

    # ============ 公共 API 方法 ============
    
    def subscribe_candles(self, symbol: str, timeframe: str = "1m", callback: Callable = None) -> bool:
        """
        订阅 K线数据
        
        Args:
            symbol: 交易对，如 "BTC-USDT-SWAP" 或 "BTC/USDT:USDT"
            timeframe: 时间周期，如 "1m", "5m", "15m", "1H", "4H", "1D"
            callback: 数据回调函数（可选）
        
        Returns:
            是否订阅成功
        """
        # 转换 symbol 格式: "BTC/USDT:USDT" -> "BTC-USDT-SWAP"
        inst_id = self._convert_symbol(symbol)
        
        # 🔥 OKX WebSocket K线频道格式
        # 对于永续合约，使用 index-candle 或 candle 频道
        # 格式: candle1m, candle5m, candle15m, candle1H, candle4H, candle1D, candle1Dutc
        # 注意：OKX 使用大写的 H 和 D，小写的 m
        tf_normalized = self._normalize_timeframe(timeframe)
        channel = f"candle{tf_normalized}"
        channel_key = f"{channel}:{inst_id}"
        
        # 记录订阅信息
        self.subscriptions[channel_key] = {
            "channel": channel,
            "inst_id": inst_id,
            "timeframe": timeframe
        }
        
        # 注册回调
        if callback:
            self.callbacks[channel_key].append(callback)
        
        # 发送订阅请求
        if self.connected:
            self._send_subscribe(channel, inst_id)
            logger.info(f"[WS] 订阅 K线: {inst_id} {timeframe}")
            return True
        else:
            logger.warning(f"[WS] 未连接，订阅将在连接后自动执行: {inst_id} {timeframe}")
            return False
    
    def subscribe_ticker(self, symbol: str, callback: Callable = None) -> bool:
        """
        订阅实时行情
        
        Args:
            symbol: 交易对，如 "BTC-USDT-SWAP" 或 "BTC/USDT:USDT"
            callback: 数据回调函数（可选）
        
        Returns:
            是否订阅成功
        """
        inst_id = self._convert_symbol(symbol)
        channel = "tickers"
        channel_key = f"{channel}:{inst_id}"
        
        # 记录订阅信息
        self.subscriptions[channel_key] = {
            "channel": channel,
            "inst_id": inst_id
        }
        
        # 注册回调
        if callback:
            self.callbacks[channel_key].append(callback)
        
        # 发送订阅请求
        if self.connected:
            self._send_subscribe(channel, inst_id)
            logger.info(f"[WS] 订阅行情: {inst_id}")
            return True
        else:
            logger.warning(f"[WS] 未连接，订阅将在连接后自动执行: {inst_id}")
            return False
    
    def unsubscribe(self, symbol: str, channel_type: str = "candle", timeframe: str = "1m") -> bool:
        """
        取消订阅
        
        Args:
            symbol: 交易对
            channel_type: 频道类型 ("candle" 或 "ticker")
            timeframe: 时间周期（仅 candle 需要）
        
        Returns:
            是否取消成功
        """
        inst_id = self._convert_symbol(symbol)
        
        if channel_type == "candle":
            channel = f"candle{timeframe}"
        else:
            channel = "tickers"
        
        channel_key = f"{channel}:{inst_id}"
        
        # 移除订阅记录
        if channel_key in self.subscriptions:
            del self.subscriptions[channel_key]
        
        # 移除回调
        if channel_key in self.callbacks:
            del self.callbacks[channel_key]
        
        # 发送取消订阅请求
        if self.connected and self.ws:
            msg = {
                "op": "unsubscribe",
                "args": [{
                    "channel": channel,
                    "instId": inst_id
                }]
            }
            try:
                self.ws.send(json.dumps(msg))
                logger.info(f"[WS] 取消订阅: {channel_key}")
                return True
            except Exception as e:
                logger.error(f"[WS] 取消订阅失败: {e}")
                return False
        
        return True
    
    def get_candles(self, symbol: str, timeframe: str = "1m", limit: int = 500) -> List:
        """
        获取缓存的 K线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            limit: 返回数量限制
        
        Returns:
            K线数据列表 [[ts, o, h, l, c, vol], ...]
        """
        inst_id = self._convert_symbol(symbol)
        tf_normalized = self._normalize_timeframe(timeframe)
        cache_key = f"{inst_id}:{tf_normalized}"
        
        with self.candle_cache_lock:
            data = self.candle_cache.get(cache_key, [])
            if limit and len(data) > limit:
                return data[-limit:]
            return data.copy()
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        获取缓存的行情数据
        
        Args:
            symbol: 交易对
        
        Returns:
            行情数据字典或 None
        """
        inst_id = self._convert_symbol(symbol)
        return self.ticker_cache.get(inst_id)
    
    def get_last_price(self, symbol: str) -> Optional[float]:
        """
        获取最新价格
        
        Args:
            symbol: 交易对
        
        Returns:
            最新价格或 None
        """
        ticker = self.get_ticker(symbol)
        if ticker:
            return ticker.get("last")
        return None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connected
    
    def get_subscription_count(self) -> int:
        """获取当前订阅数量"""
        return len(self.subscriptions)
    
    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        with self.candle_cache_lock:
            candle_stats = {
                key: len(data) for key, data in self.candle_cache.items()
            }
        
        return {
            "connected": self.connected,
            "subscriptions": len(self.subscriptions),
            "candle_cache": candle_stats,
            "ticker_cache": len(self.ticker_cache),
            "reconnect_attempts": self.reconnect_attempts
        }
    
    def _normalize_timeframe(self, timeframe: str) -> str:
        """
        标准化时间周期格式为 OKX WebSocket 格式
        
        OKX WebSocket 使用:
        - 分钟: 1m, 3m, 5m, 15m, 30m (小写 m)
        - 小时: 1H, 2H, 4H (大写 H)
        - 天: 1D, 2D, 3D, 5D (大写 D)
        - 周: 1W (大写 W)
        - 月: 1M (大写 M，注意与分钟区分)
        - UTC日线: 1Dutc, 2Dutc, 3Dutc, 5Dutc
        """
        tf = timeframe.strip()
        
        # 处理小时格式
        if tf.lower().endswith('h'):
            num = tf[:-1]
            return f"{num}H"
        
        # 处理天格式
        if tf.lower().endswith('d'):
            num = tf[:-1]
            return f"{num}D"
        
        # 处理周格式
        if tf.lower().endswith('w'):
            num = tf[:-1]
            return f"{num}W"
        
        # 分钟格式保持小写
        if tf.lower().endswith('m') and not tf.endswith('M'):
            return tf.lower()
        
        return tf
    
    def _convert_symbol(self, symbol: str) -> str:
        """
        转换 symbol 格式
        
        "BTC/USDT:USDT" -> "BTC-USDT-SWAP"
        "BTC-USDT-SWAP" -> "BTC-USDT-SWAP" (不变)
        """
        if "/" in symbol:
            # CCXT 格式: "BTC/USDT:USDT"
            base = symbol.split("/")[0]
            return f"{base}-USDT-SWAP"
        return symbol


# ============ 全局单例 ============
_ws_client: Optional[OKXWebSocketClient] = None
_ws_client_lock = threading.Lock()


def get_ws_client(use_aws: bool = False) -> Optional[OKXWebSocketClient]:
    """
    获取全局 WebSocket 客户端单例
    
    Args:
        use_aws: 是否使用 AWS 节点
    
    Returns:
        WebSocket 客户端实例，如果 websocket-client 未安装则返回 None
    """
    global _ws_client
    
    if not WEBSOCKET_AVAILABLE:
        return None
    
    with _ws_client_lock:
        if _ws_client is None:
            try:
                _ws_client = OKXWebSocketClient(use_aws=use_aws)
            except ImportError:
                return None
        return _ws_client


def start_ws_client(use_aws: bool = False) -> bool:
    """
    启动全局 WebSocket 客户端
    
    Returns:
        是否启动成功
    """
    client = get_ws_client(use_aws)
    if client:
        return client.start()
    return False


def stop_ws_client():
    """停止全局 WebSocket 客户端"""
    global _ws_client
    
    with _ws_client_lock:
        if _ws_client:
            _ws_client.stop()
            _ws_client = None


def is_ws_available() -> bool:
    """检查 WebSocket 功能是否可用"""
    return WEBSOCKET_AVAILABLE
