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

# 🔥 使用 ccxt 异步支持
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
        rate_limit: bool = False,  # 🔥 异步模式下关闭自动限流，由并发控制
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
        🔥 批量并发获取 K 线数据
        
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
        
        # 🔥 核心：使用 asyncio.gather 并发执行
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
        
        logger.info(
            f"[AsyncFetcher] 批量获取完成 | "
            f"任务数: {len(tasks)} | 成功: {success_count} | "
            f"总耗时: {total_time:.0f}ms"
        )
        
        return processed_results


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
    
    兼容现有同步代码，内部使用 asyncio.run() 调用异步逻辑。
    
    Args:
        tasks: [(symbol, timeframe, limit), ...]
        api_key, api_secret, passphrase: API 凭证
        sandbox: 是否沙盒模式
        market_type: 市场类型 (swap/spot)
        max_concurrent: 最大并发数
    
    Returns:
        {(symbol, timeframe): ohlcv_data or None, ...}
    
    使用示例：
        tasks = [
            ("BTC-USDT-SWAP", "1m", 50),
            ("ETH-USDT-SWAP", "1m", 50),
            ("BTC-USDT-SWAP", "5m", 50),
        ]
        results = fetch_batch_ohlcv_sync(tasks, api_key, api_secret, passphrase)
        
        btc_1m_data = results.get(("BTC-USDT-SWAP", "1m"))
    """
    
    async def _run():
        async with AsyncMarketFetcher(
            api_key=api_key,
            api_secret=api_secret,
            passphrase=passphrase,
            sandbox=sandbox,
            market_type=market_type,
            max_concurrent=max_concurrent,
        ) as fetcher:
            fetch_tasks = [
                FetchTask(symbol=sym, timeframe=tf, limit=lim)
                for sym, tf, lim in tasks
            ]
            return await fetcher.fetch_batch_ohlcv(fetch_tasks)
    
    # 运行异步代码
    results = asyncio.run(_run())
    
    # 转换为字典格式
    return {
        (r.symbol, r.timeframe): r.data
        for r in results
    }


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
    timeframes = ["1m", "3m", "5m", "15m", "30m", "1h"]
    
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
