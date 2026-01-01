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
#
"""
OKX WebSocket 客户端

支持订阅 K线数据的实时推送
"""
import json
import time
import threading
import logging
import queue
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
    OKX WebSocket 客户端 (Production-Ready Refactored Version)
    
    功能：
    - 订阅 K线数据 (candle)
    - 订阅实时行情 (ticker)
    - 自动重连（指数退避）
    - 内置心跳保活
    
    线程安全机制：
    - ws_lock: 保护 WebSocket 对象的并发访问（send/close）
    - msg_queue: 生产者-消费者模式，解耦网络线程与消息处理
    - stop_event: 优雅关闭信号
    """
    
    # OKX WebSocket 地址
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
        
        # 使用 Business 端点（K线数据需要此端点）
        self.ws_url = self.WS_BUSINESS_URL_AWS if use_aws else self.WS_BUSINESS_URL
        self.ws: Optional[websocket.WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        
        # 代理配置（复用 env_validator 的自动检测逻辑）
        import os
        self.http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
        self.https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
        
        # 如果没有配置代理，使用 env_validator 的自动检测
        if not self.https_proxy and not self.http_proxy:
            try:
                from utils.env_validator import EnvironmentValidator
                proxy_config = EnvironmentValidator.detect_system_proxy()
                self.https_proxy = proxy_config.get('https_proxy') or proxy_config.get('http_proxy')
                self.http_proxy = proxy_config.get('http_proxy')
            except Exception as e:
                logger.debug(f"[WS] 代理自动检测失败: {e}")
        
        if self.https_proxy:
            logger.info(f"[WS] 使用代理: {self.https_proxy}")
        
        # ========== 线程安全机制 ==========
        # [Fix #1] WebSocket 锁：保护 ws.send() / ws.close() 的并发访问
        self.ws_lock = threading.Lock()
        
        # [Fix #2] 消息队列：生产者-消费者模式，解耦网络 I/O 与业务处理
        self.msg_queue: queue.Queue = queue.Queue(maxsize=10000)
        self.queue_worker_thread: Optional[threading.Thread] = None
        
        # [Fix #5] 停止事件：优雅关闭信号
        self.stop_event = threading.Event()
        
        # 连接状态
        self.connected = False
        
        # 订阅管理
        self.subscriptions: Dict[str, Dict] = {}  # {channel_key: subscription_info}
        self.callbacks: Dict[str, List[Callable]] = defaultdict(list)  # {channel_key: [callbacks]}
        
        # K线数据缓存
        self.candle_cache: Dict[str, List] = {}  # {inst_id:timeframe: [[ts, o, h, l, c, v], ...]}
        self.candle_cache_lock = threading.Lock()
        
        # 行情数据缓存
        self.ticker_cache: Dict[str, Dict] = {}  # {inst_id: ticker_data}
        
        # [Fix #3] 重连配置（指数退避）
        self.base_reconnect_delay = 1  # 初始重连延迟（秒）
        self.max_reconnect_delay = 60  # 最大重连延迟（秒）
        self.reconnect_attempts = 0
    
    def start(self) -> bool:
        """
        启动 WebSocket 连接
        
        启动流程：
        1. 启动消息队列消费者线程
        2. 启动 WebSocket 连接线程（含自动重连循环）
        
        Returns:
            是否启动成功
        """
        if self.connected:
            logger.info("[WS] 已连接，无需重复启动")
            return True
        
        self.stop_event.clear()
        
        try:
            # [Fix #2] 启动消息队列消费者线程
            self.queue_worker_thread = threading.Thread(
                target=self._process_queue_loop,
                daemon=True,
                name="WS-QueueWorker"
            )
            self.queue_worker_thread.start()
            
            # 启动 WebSocket 连接线程
            self.ws_thread = threading.Thread(
                target=self._connection_loop,
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
        """
        [Fix #5] 优雅停止 WebSocket 连接
        
        停止流程：
        1. 设置停止事件信号
        2. 安全关闭 WebSocket（吞掉异常）
        3. 等待工作线程结束
        """
        logger.debug("[WS] 正在停止...")
        self.stop_event.set()
        
        # 安全关闭 WebSocket
        with self.ws_lock:
            if self.ws:
                try:
                    self.ws.close()
                except Exception:
                    pass  # 吞掉关闭时的异常
        
        self.connected = False
        
        # 等待线程结束
        if self.ws_thread and self.ws_thread.is_alive():
            self.ws_thread.join(timeout=5)
        if self.queue_worker_thread and self.queue_worker_thread.is_alive():
            # 放入哨兵值唤醒队列消费者
            self.msg_queue.put(None)
            self.queue_worker_thread.join(timeout=5)
        
        logger.debug("[WS] 已停止")
    
    def _connection_loop(self):
        """
        [Fix #3] WebSocket 连接主循环（带指数退避重连）
        
        模式：While-True-Try-Except
        - 连接断开后自动重连
        - 使用指数退避算法：1s, 2s, 4s, 8s... 最大 60s
        """
        while not self.stop_event.is_set():
            try:
                # 创建新的 WebSocket 实例
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close
                )
                
                # [Fix #4] 使用内置心跳，移除自定义心跳线程
                # ping_interval: 每 25 秒自动发送 Ping
                # ping_timeout: 10 秒内未收到 Pong 则断开
                
                # 代理支持：解析代理URL并传递给 run_forever
                run_kwargs = {
                    "ping_interval": 25,
                    "ping_timeout": 10
                }
                
                proxy_url = self.https_proxy or self.http_proxy
                if proxy_url:
                    from urllib.parse import urlparse
                    parsed = urlparse(proxy_url)
                    if parsed.hostname and parsed.port:
                        run_kwargs["http_proxy_host"] = parsed.hostname
                        run_kwargs["http_proxy_port"] = parsed.port
                        # 关键：必须指定 proxy_type，否则会报错
                        # 根据代理URL的scheme确定类型
                        scheme = parsed.scheme.lower()
                        if scheme in ('socks5', 'socks5h'):
                            run_kwargs["proxy_type"] = "socks5"
                        elif scheme in ('socks4', 'socks4a'):
                            run_kwargs["proxy_type"] = "socks4"
                        else:
                            # http/https 代理
                            run_kwargs["proxy_type"] = "http"
                        logger.info(f"[WS] 使用代理连接: {run_kwargs['proxy_type']}://{parsed.hostname}:{parsed.port}")
                
                self.ws.run_forever(**run_kwargs)
                
            except Exception as e:
                logger.error(f"[WS] 运行异常: {e}")
            
            # 连接断开，准备重连
            self.connected = False
            
            if self.stop_event.is_set():
                break
            
            # [Fix #3] 指数退避重连
            self.reconnect_attempts += 1
            delay = min(
                self.base_reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
                self.max_reconnect_delay
            )
            logger.debug(f"[WS] 将在 {delay:.1f}s 后重连 (第 {self.reconnect_attempts} 次)")
            
            # 可中断的等待
            if self.stop_event.wait(timeout=delay):
                break  # 收到停止信号，退出循环
        
        logger.debug("[WS] 连接循环已退出")
    
    def _on_open(self, ws):
        """连接建立回调"""
        self.connected = True
        self.reconnect_attempts = 0  # 重置重连计数
        logger.info("[WS] 连接已建立")  # 保留：连接成功是重要事件
        
        # 重新订阅之前的频道
        self._resubscribe_all()
        # [Fix #4] 移除自定义心跳线程，使用 run_forever 内置心跳
    
    def _on_message(self, ws, message):
        """
        [Fix #2] 消息接收回调 - 仅入队，不做业务处理
        
        生产者角色：将原始消息放入队列，立即返回
        这样可以避免阻塞 WebSocket 网络线程
        """
        try:
            self.msg_queue.put_nowait(message)
        except Exception:
            # 队列满时丢弃消息，避免阻塞
            logger.warning("[WS] 消息队列已满，丢弃消息")
    
    def _process_queue_loop(self):
        """
        [Fix #2] 消息队列消费者循环
        
        消费者角色：从队列取出消息并处理
        独立线程运行，与网络 I/O 解耦
        
        异常处理策略：
        - queue.Empty: 正常超时，继续循环
        - 处理异常: 记录日志，继续处理下一条消息（线程永不死亡）
        """
        logger.debug("[WS] 消息处理线程已启动")
        
        while not self.stop_event.is_set():
            try:
                # 带超时的阻塞获取，允许检查停止信号
                message = self.msg_queue.get(timeout=1.0)
            except queue.Empty:
                # 队列超时，继续循环检查 stop_event
                continue
            
            # 哨兵值，退出循环
            if message is None:
                break
            
            # 关键：处理逻辑包裹在独立的 try-except 中
            # 确保任何处理异常都不会导致工作线程崩溃
            try:
                self._process_message(message)
            except Exception as e:
                logger.error(f"[WS] 消息处理异常（线程继续运行）: {e}", exc_info=True)
                # 继续处理下一条消息，线程永不死亡
        
        logger.debug("[WS] 消息处理线程已退出")
    
    def _process_message(self, message: str):
        """
        实际的消息处理逻辑（从队列消费后调用）
        """
        try:
            # 处理纯文本 pong 响应
            if message == "pong":
                return
            
            data = json.loads(message)
            
            # 处理 JSON 格式的 pong
            if data.get("event") == "pong":
                return
            
            # 处理订阅确认
            if data.get("event") == "subscribe":
                logger.debug(f"[WS]  订阅确认: {data.get('arg', {})}")
                return
            
            # 处理错误
            if data.get("event") == "error":
                logger.error(f"[WS]  订阅错误: {data}")
                return
            
            # 处理数据推送
            if "data" in data and "arg" in data:
                self._handle_data_push(data)
                
        except json.JSONDecodeError:
            if message.strip().lower() != "pong":
                logger.warning(f"[WS] 无法解析消息: {message[:100]}")
        except Exception as e:
            logger.error(f"[WS] 消息处理异常: {e}")
    
    def _on_error(self, ws, error):
        """错误回调"""
        error_str = str(error)
        # 连接断开是常见情况，使用更友好的提示
        if "Connection to remote host was lost" in error_str or "ConnectionResetError" in error_str:
            logger.warning("[WS] 连接已断开，正在准备重连...")
        elif "timed out" in error_str.lower():
            logger.warning("[WS] 连接超时，正在准备重连...")
        else:
            logger.error(f"[WS] 连接异常: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """连接关闭回调"""
        self.connected = False
        logger.debug(f"[WS] 连接关闭: {close_status_code} - {close_msg}")
    
    def _resubscribe_all(self):
        """重新订阅所有频道"""
        if not self.subscriptions:
            logger.debug("[WS] 无待重新订阅的频道")
            return
        
        logger.debug(f"[WS] 开始重新订阅 {len(self.subscriptions)} 个频道")
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
        
        self._safe_send(json.dumps(msg))
    
    def _safe_send(self, message: str) -> bool:
        """
        [Fix #1] 线程安全的消息发送
        
        使用 ws_lock 保护 ws.send() 调用，防止并发写入导致的 Broken Pipe
        
        Args:
            message: 要发送的消息字符串
            
        Returns:
            是否发送成功
        """
        with self.ws_lock:
            if self.ws and self.connected:
                try:
                    self.ws.send(message)
                    # 调试：打印发送的消息（仅订阅请求）
                    if '"op": "subscribe"' in message or '"op":"subscribe"' in message:
                        logger.debug(f"[WS] 发送订阅请求: {message[:200]}")
                    return True
                except Exception as e:
                    logger.warning(f"[WS] 发送失败: {e}")
                    return False
            else:
                logger.warning(f"[WS] 无法发送: ws={self.ws is not None} connected={self.connected}")
        return False
    
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
        
        # OKX WebSocket K线频道格式
        tf_normalized = self._normalize_timeframe(timeframe)
        channel = f"candle{tf_normalized}"
        channel_key = f"{channel}:{inst_id}"
        
        # 去重检查：如果已订阅，只添加回调，不重复发送请求
        already_subscribed = channel_key in self.subscriptions
        
        # 记录订阅信息
        self.subscriptions[channel_key] = {
            "channel": channel,
            "inst_id": inst_id,
            "timeframe": timeframe
        }
        
        # 注册回调
        if callback:
            self.callbacks[channel_key].append(callback)
        
        # 已订阅则跳过发送
        if already_subscribed:
            logger.debug(f"[WS] 已订阅，跳过重复请求: {channel_key}")
            return True
        
        # 发送订阅请求（使用线程安全方法）
        if self.connected:
            if self._safe_send(json.dumps({
                "op": "subscribe",
                "args": [{"channel": channel, "instId": inst_id}]
            })):
                logger.debug(f"[WS] 订阅 K线: {inst_id} {timeframe}")
                return True
            return False
        else:
            logger.debug(f"[WS] 未连接，订阅将在连接后自动执行: {inst_id} {timeframe}")
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
        
        # 去重检查：如果已订阅，只添加回调，不重复发送请求
        already_subscribed = channel_key in self.subscriptions
        
        # 记录订阅信息
        self.subscriptions[channel_key] = {
            "channel": channel,
            "inst_id": inst_id
        }
        
        # 注册回调
        if callback:
            self.callbacks[channel_key].append(callback)
        
        # 已订阅则跳过发送
        if already_subscribed:
            logger.debug(f"[WS] 已订阅，跳过重复请求: {channel_key}")
            return True
        
        # 发送订阅请求（使用线程安全方法）
        if self.connected:
            if self._safe_send(json.dumps({
                "op": "subscribe",
                "args": [{"channel": channel, "instId": inst_id}]
            })):
                logger.debug(f"[WS] 订阅行情: {inst_id}")
                return True
            return False
        else:
            logger.debug(f"[WS] 未连接，订阅将在连接后自动执行: {inst_id}")
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
        
        # 发送取消订阅请求（使用线程安全方法）
        if self.connected:
            msg = {
                "op": "unsubscribe",
                "args": [{
                    "channel": channel,
                    "instId": inst_id
                }]
            }
            if self._safe_send(json.dumps(msg)):
                logger.debug(f"[WS] 取消订阅: {channel_key}")
                return True
            else:
                logger.warning(f"[WS] 取消订阅失败")
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
    
    def warmup_cache(self, symbol: str, timeframe: str, ohlcv_data: List) -> int:
        """
         预热 K线缓存（混合模式核心方法）
        
        将 REST API 获取的历史 K线数据注入到 WebSocket 缓存中，
        后续 WebSocket 推送的实时数据会自动更新/追加到缓存。
        
        Args:
            symbol: 交易对，如 "BTC/USDT:USDT"
            timeframe: 时间周期，如 "1m"
            ohlcv_data: K线数据列表 [[ts, o, h, l, c, vol], ...]
        
        Returns:
            注入的 K线数量
        """
        if not ohlcv_data:
            return 0
        
        inst_id = self._convert_symbol(symbol)
        tf_normalized = self._normalize_timeframe(timeframe)
        cache_key = f"{inst_id}:{tf_normalized}"
        
        with self.candle_cache_lock:
            # 如果缓存已存在，合并数据（去重）
            if cache_key in self.candle_cache:
                existing = self.candle_cache[cache_key]
                existing_ts = {candle[0] for candle in existing}
                
                # 只添加不存在的 K线
                new_candles = [c for c in ohlcv_data if c[0] not in existing_ts]
                if new_candles:
                    existing.extend(new_candles)
                    # 按时间戳排序
                    existing.sort(key=lambda x: x[0])
                    # 限制缓存大小
                    if len(existing) > 1000:
                        self.candle_cache[cache_key] = existing[-1000:]
                    
                    logger.debug(f"[WS] 预热合并: {cache_key} +{len(new_candles)} bars, total={len(self.candle_cache[cache_key])}")
                    return len(new_candles)
                return 0
            else:
                # 缓存不存在，直接设置
                # 确保数据格式正确：[[ts, o, h, l, c, vol], ...]
                normalized_data = []
                for candle in ohlcv_data:
                    if len(candle) >= 6:
                        normalized_data.append([
                            int(candle[0]),    # ts
                            float(candle[1]),  # open
                            float(candle[2]),  # high
                            float(candle[3]),  # low
                            float(candle[4]),  # close
                            float(candle[5])   # volume
                        ])
                
                # 按时间戳排序
                normalized_data.sort(key=lambda x: x[0])
                
                # 限制缓存大小
                if len(normalized_data) > 1000:
                    normalized_data = normalized_data[-1000:]
                
                self.candle_cache[cache_key] = normalized_data
                logger.info(f"[WS] 预热完成: {cache_key} = {len(normalized_data)} bars")
                return len(normalized_data)
    
    def get_cache_count(self, symbol: str, timeframe: str) -> int:
        """
        获取指定币种和周期的缓存 K线数量
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            缓存的 K线数量
        """
        inst_id = self._convert_symbol(symbol)
        tf_normalized = self._normalize_timeframe(timeframe)
        cache_key = f"{inst_id}:{tf_normalized}"
        
        with self.candle_cache_lock:
            return len(self.candle_cache.get(cache_key, []))
    
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


# ============ 测试入口 ============
if __name__ == "__main__":
    """
    简单测试：连接 OKX WebSocket，订阅 BTC-USDT-SWAP 行情，打印 10 秒数据后优雅退出
    
    运行方式: python okx_websocket.py
    """
    import sys
    
    # 配置日志输出到控制台
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    print("=" * 50)
    print("OKX WebSocket 客户端测试")
    print("=" * 50)
    
    # 创建客户端
    client = OKXWebSocketClient(use_aws=False)
    
    # 定义回调函数
    def on_ticker(data):
        """行情数据回调"""
        ticker_data = data.get("data", [{}])[0]
        last_price = ticker_data.get("last", "N/A")
        print(f"[Ticker] BTC-USDT-SWAP 最新价: {last_price}")
    
    try:
        # 启动连接
        print("\n[Test] 正在启动 WebSocket 连接...")
        if not client.start():
            print("[Test] 连接失败，退出")
            sys.exit(1)
        
        print("[Test] 连接成功！")
        
        # 订阅行情
        print("[Test] 订阅 BTC-USDT-SWAP 行情...")
        client.subscribe_ticker("BTC-USDT-SWAP", callback=on_ticker)
        
        # 运行 10 秒
        print("[Test] 接收数据 10 秒...\n")
        for i in range(10):
            time.sleep(1)
            # 也可以直接从缓存获取
            ticker = client.get_ticker("BTC-USDT-SWAP")
            if ticker:
                print(f"[Cache] 第 {i+1} 秒 - 缓存价格: {ticker.get('last', 'N/A')}")
        
        print("\n[Test] 测试完成")
        
    except KeyboardInterrupt:
        print("\n[Test] 收到中断信号")
    
    finally:
        # 优雅停止
        print("[Test] 正在停止客户端...")
        client.stop()
        print("[Test] 已退出")
