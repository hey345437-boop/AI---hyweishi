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
异步市场数据获取器 (Async Market Fetcher)

使用 ccxt.async_support 实现真正的并发 API 请求，
将扫描耗时从 3-4 秒压缩到 1 秒以内。

使用方式：
    from async_market_fetcher import AsyncMarketFetcher, fetch_batch_ohlcv_sync
    
    # 同步调用（兼容现有代码）
    results = fetch_batch_ohlcv_sync(tasks, credentials)
    
    # 异步调用
    async with AsyncMarketFetcher(credentials) as fetcher:
        results = await fetcher.fetch_batch_ohlcv(tasks)
"""

import asyncio
import logging
import time
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# 使用 ccxt 异步支持
import ccxt.async_support as ccxt_async

logger = logging.getLogger(__name__)


@dataclass
class FetchTask:
    """单个获取任务"""
    symbol: str
    timeframe: str
    limit: int = 50
    since: Optional[int] = None


@dataclass
class FetchResult:
    """获取结果"""
    symbol: str
    timeframe: str
    data: Optional[List] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    
    @property
    def success(self) -> bool:
        return self.data is not None and self.error is None


class AsyncMarketFetcher:
    """
    异步市场数据获取器
    
    特点：
    - 使用 ccxt.async_support 实现真正的并发
    - 支持批量获取多个币种/周期的 K 线数据
    - 自动处理异常，单个失败不影响其他请求
    - 支持上下文管理器，自动关闭连接
    
    使用示例：
        async with AsyncMarketFetcher(credentials) as fetcher:
            tasks = [
                FetchTask("BTC/USDT:USDT", "1m", 50),
                FetchTask("ETH/USDT:USDT", "1m", 50),
            ]
            results = await fetcher.fetch_batch_ohlcv(tasks)
    """
    
    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        sandbox: bool = False,
        market_type: str = "swap",
        rate_limit: bool = False,  # 异步模式下关闭自动限流，由并发控制
        timeout_ms: int = 10000,
        max_concurrent: int = 20,  # 最大并发数
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.sandbox = sandbox
        self.market_type = market_type
        self.rate_limit = rate_limit
        self.timeout_ms = timeout_ms
        self.max_concurrent = max_concurrent
        
        self.exchange: Optional[ccxt_async.okx] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口 - 确保关闭连接"""
        await self.close()
    
    async def initialize(self):
        """初始化异步交易所实例"""
        config = {
            "enableRateLimit": self.rate_limit,
            "timeout": self.timeout_ms,
            "options": {
                "defaultType": self.market_type,
            },
        }
        
        if self.api_key:
            config["apiKey"] = self.api_key
        if self.api_secret:
            config["secret"] = self.api_secret
        if self.passphrase:
            config["password"] = self.passphrase
        
        self.exchange = ccxt_async.okx(config)
        
        if self.sandbox:
            self.exchange.set_sandbox_mode(True)
        
        # 加载市场信息（带错误处理）
        try:
            await self.exchange.load_markets()
        except Exception as e:
            # 确保出错时也关闭连接
            await self.close()
            raise
        
        # 初始化并发控制信号量
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        logger.info(f"[AsyncFetcher] 初始化完成 | 最大并发: {self.max_concurrent}")
    
    async def close(self):
        """关闭交易所连接，释放资源"""
        if self.exchange:
            try:
                await self.exchange.close()
                logger.debug("[AsyncFetcher] 连接已关闭")
            except Exception as e:
                logger.warning(f"[AsyncFetcher] 关闭连接时出错: {e}")
            finally:
                self.exchange = None
    
    def _normalize_symbol(self, symbol: str) -> str:
        """标准化交易对格式"""
        s = symbol.strip().upper()
        
        # BTC-USDT-SWAP -> BTC/USDT:USDT
        if s.endswith("-SWAP"):
            parts = s.replace("-SWAP", "").split("-")
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}:{parts[1]}"
        
        # BTC-USDT -> BTC/USDT:USDT (for swap)
        if "-" in s and "/" not in s:
            parts = s.split("-")
            if len(parts) >= 2:
                if self.market_type == "swap":
                    return f"{parts[0]}/{parts[1]}:{parts[1]}"
                return f"{parts[0]}/{parts[1]}"
        
        # 已经是标准格式
        return s
    
    async def _fetch_single_ohlcv(self, task: FetchTask) -> FetchResult:
        """
        获取单个币种/周期的 K 线数据（带并发控制）
        """
        start_time = time.perf_counter()
        symbol = self._normalize_symbol(task.symbol)
        
        async with self._semaphore:  # 并发控制
            try:
                data = await self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=task.timeframe,
                    limit=task.limit,
                    since=task.since,
                )
                
                latency = (time.perf_counter() - start_time) * 1000
                
                return FetchResult(
                    symbol=task.symbol,
                    timeframe=task.timeframe,
                    data=data,
                    latency_ms=latency,
                )
                
            except Exception as e:
                latency = (time.perf_counter() - start_time) * 1000
                error_msg = f"{type(e).__name__}: {str(e)}"
                logger.warning(f"[AsyncFetcher] 获取失败 {task.symbol} {task.timeframe}: {error_msg}")
                
                return FetchResult(
                    symbol=task.symbol,
                    timeframe=task.timeframe,
                    error=error_msg,
                    latency_ms=latency,
                )
    
    async def fetch_batch_ohlcv(self, tasks: List[FetchTask]) -> List[FetchResult]:
        """
         批量并发获取 K 线数据
        
        使用 asyncio.gather 并发执行所有请求，
        return_exceptions=True 确保单个失败不影响其他请求。
        
        Args:
            tasks: 获取任务列表
        
        Returns:
            结果列表（与 tasks 顺序对应）
        """
        if not self.exchange:
            raise RuntimeError("Exchange not initialized. Call initialize() first.")
        
        if not tasks:
            return []
        
        start_time = time.perf_counter()
        
        # 核心：使用 asyncio.gather 并发执行
        coroutines = [self._fetch_single_ohlcv(task) for task in tasks]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        
        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # gather 返回的异常
                processed_results.append(FetchResult(
                    symbol=tasks[i].symbol,
                    timeframe=tasks[i].timeframe,
                    error=f"Unexpected: {type(result).__name__}: {str(result)}",
                ))
            else:
                processed_results.append(result)
        
        total_time = (time.perf_counter() - start_time) * 1000
        success_count = sum(1 for r in processed_results if r.success)
        
        # 计算各请求的延迟分布
        latencies = [r.latency_ms for r in processed_results if r.success]
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        max_latency = max(latencies) if latencies else 0
        min_latency = min(latencies) if latencies else 0
        
        logger.info(
            f"[AsyncFetcher] 批量获取完成 | "
            f"任务: {len(tasks)} | 成功: {success_count} | "
            f"总耗时: {total_time:.0f}ms | "
            f"延迟: {min_latency:.0f}/{avg_latency:.0f}/{max_latency:.0f}ms (min/avg/max)"
        )
        
        return processed_results


# ============  持久化事件循环 + 连接池（单例模式）============

import threading
import atexit
import os

# 全局单例状态（模块级别，进程内唯一）
_background_loop: Optional[asyncio.AbstractEventLoop] = None
_background_thread: Optional[threading.Thread] = None
_global_fetcher: Optional[AsyncMarketFetcher] = None
_global_fetcher_config: Dict[str, Any] = {}
_init_lock = threading.Lock()
_singleton_id: Optional[int] = None  # 用于追踪单例实例


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """在后台线程中运行事件循环"""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def _get_or_create_loop() -> asyncio.AbstractEventLoop:
    """
     获取或创建持久化的后台事件循环（单例模式 + 双重检查锁定）
    
    使用单独的后台线程运行事件循环，避免每次 asyncio.run() 创建新循环。
    双重检查锁定：先无锁检查，只有需要创建时才获取锁。
    """
    global _background_loop, _background_thread, _singleton_id
    
    # 第一次检查（无锁，快速路径）
    if (_background_thread is not None and _background_thread.is_alive() and
        _background_loop is not None and _background_loop.is_running()):
        return _background_loop
    
    # 需要创建或重建，获取锁
    with _init_lock:
        # 第二次检查（有锁，防止竞态）
        thread_alive = _background_thread is not None and _background_thread.is_alive()
        loop_running = _background_loop is not None and _background_loop.is_running()
        
        if thread_alive and loop_running:
            return _background_loop
        
        # 清理旧的循环（如果有）
        if _background_loop is not None:
            try:
                if _background_loop.is_running():
                    _background_loop.call_soon_threadsafe(_background_loop.stop)
            except Exception:
                pass
        
        # 创建新的事件循环和线程
        _background_loop = asyncio.new_event_loop()
        _background_thread = threading.Thread(
            target=_start_background_loop,
            args=(_background_loop,),
            daemon=True,
            name="AsyncFetcher-EventLoop"
        )
        _background_thread.start()
        
        # 等待事件循环启动
        time.sleep(0.01)
        
        # 记录单例 ID
        _singleton_id = id(_background_thread)
        logger.info(f"[AsyncFetcher] 后台事件循环已启动 (singleton_id={_singleton_id}, pid={os.getpid()})")
    
    return _background_loop


def get_fetcher_status() -> Dict[str, Any]:
    """
     获取 fetcher 状态（用于调试和监控）
    """
    return {
        "singleton_id": _singleton_id,
        "pid": os.getpid(),
        "thread_alive": _background_thread.is_alive() if _background_thread else False,
        "loop_running": _background_loop.is_running() if _background_loop else False,
        "fetcher_initialized": _global_fetcher is not None,
        "fetcher_config": {k: "***" if "secret" in k or "key" in k else v 
                          for k, v in _global_fetcher_config.items()},
    }


async def _get_or_create_fetcher(
    api_key: str,
    api_secret: str,
    passphrase: str,
    sandbox: bool,
    market_type: str,
    max_concurrent: int,
) -> AsyncMarketFetcher:
    """
     获取或创建全局 fetcher 实例（连接复用 + 快速路径）
    
    只有在配置变化或连接失效时才重新创建，
    避免每次扫描都调用 load_markets()
    """
    global _global_fetcher, _global_fetcher_config
    
    # 快速路径：如果 fetcher 存在且连接有效，直接返回
    if (_global_fetcher is not None and 
        _global_fetcher.exchange is not None and
        _global_fetcher_config.get("api_key") == api_key and
        _global_fetcher_config.get("sandbox") == sandbox):
        return _global_fetcher
    
    current_config = {
        "api_key": api_key,
        "api_secret": api_secret,
        "passphrase": passphrase,
        "sandbox": sandbox,
        "market_type": market_type,
        "max_concurrent": max_concurrent,
    }
    
    # 检查是否需要重新创建
    need_recreate = False
    
    if _global_fetcher is None:
        need_recreate = True
        logger.debug("[AsyncFetcher] 首次创建全局实例")
    elif _global_fetcher_config != current_config:
        need_recreate = True
        logger.info("[AsyncFetcher] 配置变化，重新创建实例")
    elif _global_fetcher.exchange is None:
        need_recreate = True
        logger.warning("[AsyncFetcher] 连接已关闭，重新创建实例")
    
    if need_recreate:
        # 关闭旧连接
        if _global_fetcher is not None:
            try:
                await _global_fetcher.close()
            except Exception:
                pass
        
        # 创建新实例
        _global_fetcher = AsyncMarketFetcher(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            sandbox=sandbox,
            market_type=market_type,
            max_concurrent=max_concurrent,
        )
        await _global_fetcher.initialize()
        _global_fetcher_config = current_config
        logger.info("[AsyncFetcher] 全局实例已创建/更新")
    
    return _global_fetcher


# ============ 同步兼容接口 ============

def fetch_batch_ohlcv_sync(
    tasks: List[Tuple[str, str, int]],  # [(symbol, timeframe, limit), ...]
    api_key: str = "",
    api_secret: str = "",
    passphrase: str = "",
    sandbox: bool = False,
    market_type: str = "swap",
    max_concurrent: int = 20,
) -> Dict[Tuple[str, str], Any]:
    """
    同步接口：批量获取 K 线数据
    
     优化：
    1. 使用持久化后台事件循环，避免每次创建新循环
    2. 复用全局 fetcher 实例，避免每次都 load_markets()
    
    首次调用会初始化连接（约 0.5-1s），后续调用直接复用（约 0.2-0.4s）
    
    Args:
        tasks: [(symbol, timeframe, limit), ...]
        api_key, api_secret, passphrase: API 凭证
        sandbox: 是否沙盒模式
        market_type: 市场类型 (swap/spot)
        max_concurrent: 最大并发数
    
    Returns:
        {(symbol, timeframe): ohlcv_data or None, ...}
    """
    
    async def _run():
        # 使用连接池获取复用的 fetcher
        fetcher = await _get_or_create_fetcher(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            sandbox=sandbox,
            market_type=market_type,
            max_concurrent=max_concurrent,
        )
        
        fetch_tasks = [
            FetchTask(symbol=sym, timeframe=tf, limit=lim)
            for sym, tf, lim in tasks
        ]
        return await fetcher.fetch_batch_ohlcv(fetch_tasks)
    
    # 使用持久化的后台事件循环
    t0 = time.perf_counter()
    loop = _get_or_create_loop()
    t1 = time.perf_counter()
    
    # 在后台循环中执行异步任务
    future = asyncio.run_coroutine_threadsafe(_run(), loop)
    t2 = time.perf_counter()
    
    try:
        # 等待结果，设置超时
        results = future.result(timeout=30)
        t3 = time.perf_counter()
        
        # 详细计时日志
        loop_time = (t1 - t0) * 1000
        submit_time = (t2 - t1) * 1000
        wait_time = (t3 - t2) * 1000
        total_time = (t3 - t0) * 1000
        
        if loop_time > 5 or submit_time > 5:  # 只在有明显开销时打印
            logger.debug(
                f"[AsyncFetcher] 同步调用耗时 | "
                f"获取循环: {loop_time:.1f}ms | 提交任务: {submit_time:.1f}ms | "
                f"等待结果: {wait_time:.1f}ms | 总计: {total_time:.1f}ms"
            )
    except Exception as e:
        logger.error(f"[AsyncFetcher] 批量获取失败: {e}")
        # 返回空结果
        return {(sym, tf): None for sym, tf, _ in tasks}
    
    # 转换为字典格式
    return {
        (r.symbol, r.timeframe): r.data
        for r in results
    }


def close_global_fetcher():
    """
     关闭全局 fetcher 实例和后台事件循环（程序退出时调用）
    """
    global _global_fetcher, _background_loop
    
    if _global_fetcher is not None and _background_loop is not None:
        async def _close():
            if _global_fetcher:
                await _global_fetcher.close()
        
        try:
            future = asyncio.run_coroutine_threadsafe(_close(), _background_loop)
            future.result(timeout=5)
        except Exception as e:
            logger.warning(f"[AsyncFetcher] 关闭全局实例失败: {e}")
        finally:
            _global_fetcher = None
    
    # 停止后台事件循环
    if _background_loop is not None and _background_loop.is_running():
        _background_loop.call_soon_threadsafe(_background_loop.stop)
        logger.info("[AsyncFetcher] 后台事件循环已停止")


# 注册退出时清理
atexit.register(close_global_fetcher)


# ============ 测试入口 ============

if __name__ == "__main__":
    """
    测试异步获取性能
    
    运行: python async_market_fetcher.py
    """
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # 测试任务：5 个币种 × 6 个周期 = 30 个请求
    symbols = [
        "BTC-USDT-SWAP",
        "ETH-USDT-SWAP",
        "SOL-USDT-SWAP",
        "DOGE-USDT-SWAP",
        "XRP-USDT-SWAP",
    ]
    timeframes = ["1m", "3m", "5m", "15m", "30m", "1h", "4h", "1D"]
    
    tasks = [
        (sym, tf, 50)
        for sym in symbols
        for tf in timeframes
    ]
    
    print(f"\n{'='*50}")
    print(f"异步批量获取测试")
    print(f"任务数: {len(tasks)} ({len(symbols)} 币种 × {len(timeframes)} 周期)")
    print(f"{'='*50}\n")
    
    start = time.perf_counter()
    
    # 使用同步接口测试（无需 API 凭证，公开数据）
    results = fetch_batch_ohlcv_sync(
        tasks=tasks,
        market_type="swap",
        max_concurrent=20,
    )
    
    elapsed = time.perf_counter() - start
    
    success_count = sum(1 for v in results.values() if v is not None)
    
    print(f"\n{'='*50}")
    print(f"测试结果")
    print(f"{'='*50}")
    print(f"总耗时: {elapsed:.2f} 秒")
    print(f"成功: {success_count}/{len(tasks)}")
    print(f"平均每请求: {elapsed/len(tasks)*1000:.0f} ms")
    print(f"{'='*50}\n")
