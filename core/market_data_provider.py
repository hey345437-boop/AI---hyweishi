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
市场数据提供者

支持 REST API 和 WebSocket 两种数据源
"""
import os
import time
import threading
import logging
import random
from collections import defaultdict
from typing import Dict, Any, Optional, Tuple, NamedTuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# 双通道K线数据支持
try:
    from dual_channel.dual_channel_ohlcv import (
        DualChannelOHLCV, 
        IncrementalFetcher, 
        get_incremental_fetcher,
        get_timeframe_ms,
        InsufficientDataError
    )
    DUAL_CHANNEL_AVAILABLE = True
except ImportError:
    DUAL_CHANNEL_AVAILABLE = False
    logger.warning("dual_channel_ohlcv module not available, dual channel features disabled")


# ============  智能K线缓存数据结构 ============
@dataclass
class OHLCVCacheEntry:
    """K线缓存条目 - 基于时间戳增长的智能缓存"""
    data: list                    # K线数据 [[ts, o, h, l, c, v], ...]
    last_max_ts: int              # data 中最大的时间戳 (ms)
    fetched_at_ms: int            # 拉取时刻的 UTC ms
    is_stale: bool = False        # 是否判定为陈旧（交易所未更新）
    stale_count: int = 0          # 连续陈旧次数
    bars_count: int = 0           # K线数量
    is_initialized: bool = False  # 是否已完成全量初始化（1000根）


# ============  缓存配置常量 ============
OHLCV_TARGET_BARS = 1000          # 目标K线数量
OHLCV_INCREMENTAL_LIMIT = 50      # 增量拉取数量
OHLCV_PAGE_SIZE = 100             # OKX 单次返回上限（保守值）
OHLCV_MAX_PAGES = 15              # 最大分页次数（防止无限循环）


def _get_timeframe_ms(timeframe: str) -> int:
    """获取时间周期对应的毫秒数"""
    if DUAL_CHANNEL_AVAILABLE:
        return get_timeframe_ms(timeframe)
    
    # 备用实现
    tf_map = {
        '1m': 60 * 1000,
        '3m': 3 * 60 * 1000,
        '5m': 5 * 60 * 1000,
        '15m': 15 * 60 * 1000,
        '30m': 30 * 60 * 1000,
        '1h': 60 * 60 * 1000,
        '4h': 4 * 60 * 60 * 1000,
        '1d': 24 * 60 * 60 * 1000,
    }
    return tf_map.get(timeframe, 60 * 1000)

class MarketDataProvider:
    def __init__(self, exchange_adapter, timeframe, ohlcv_limit,
                 ohlcv_ttl_sec=None, ticker_ttl_sec=None,
                 balance_ttl_sec=None, positions_ttl_sec=None):
        # 交易所适配器
        self.exchange = exchange_adapter
        
        # 默认参数
        self.timeframe = timeframe
        self.ohlcv_limit = ohlcv_limit
        
        # TTL配置 - 从环境变量读取，有默认值
        self.OHLCV_TTL_SEC = int(os.getenv("OHLCV_TTL_SEC", ohlcv_ttl_sec or "30"))
        self.TICKER_TTL_SEC = int(os.getenv("TICKER_TTL_SEC", ticker_ttl_sec or "10"))
        self.BALANCE_TTL_SEC = int(os.getenv("BALANCE_TTL_SEC", balance_ttl_sec or "60"))
        self.POSITIONS_TTL_SEC = int(os.getenv("POSITIONS_TTL_SEC", positions_ttl_sec or "30"))
        
        # 缓存存储
        self.ohlcv_cache = {}
        self.ticker_cache = {}
        self.balance_cache = {}
        self.positions_cache = {}
        
        # 单航班去重锁和事件
        self.locks = defaultdict(threading.Lock)
        self.pending = defaultdict(threading.Event)
        
        # 指标记录
        self.metrics = {
            "api_calls": 0,
            "api_latency_ms": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "last_error_time": 0
        }
        
        # 熔断状态
        self.circuit_breakers = defaultdict(dict)
        # 错误节流
        self.last_error_summary = 0
        self.error_counts = defaultdict(int)
        
        # 待初始化队列：记录首次拉取失败的币种，下一轮优先重试
        self.pending_init: Dict[Tuple[str, str], int] = {}  # {(symbol, tf): retry_count}
    
    def _request_with_retry(self, endpoint, symbol, func, *args, **kwargs):
        """
        带重试的请求执行函数
        
        参数:
        - endpoint: 端点名称
        - symbol: 交易对
        - func: 要执行的函数
        - args: 位置参数
        - kwargs: 关键字参数
        
        返回:
        - 函数执行结果
        """
        max_retries = 3
        base_delay = 0.2  # 基础延迟时间（秒）
        max_delay = 1.0   # 最大延迟时间（秒）
        
        for retry in range(max_retries):
            try:
                start_time = time.time()
                result = func(*args, **kwargs)
                api_latency = (time.time() - start_time) * 1000
                
                # 更新指标
                self.metrics["api_calls"] += 1
                self.metrics["api_latency_ms"].append(api_latency)
                
                return result, api_latency
            except Exception as e:
                # 记录错误
                self.metrics["errors"] += 1
                self.record_error(endpoint, symbol, str(e))
                
                # 如果是最后一次重试，抛出异常
                if retry == max_retries - 1:
                    raise
                
                # 计算指数退避时间 + 抖动
                delay = base_delay * (2 ** retry)
                # 添加抖动 (0.5-1.5倍的计算延迟)
                jitter = delay * (0.5 + random.random())
                # 确保不超过最大延迟
                final_delay = min(jitter, max_delay)
                
                logger.debug(f"[重试] {endpoint} {symbol} - {e}，将在 {final_delay:.2f}s 后重试")
                time.sleep(final_delay)
        
        # 理论上不会到达这里，但为了类型安全
        raise Exception("重试次数耗尽")

    def get_ohlcv(self, symbol, timeframe=None, limit=None, force_fetch=False) -> Tuple[list, bool]:
        """
        获取K线数据 - 首次全量分页拉取 + 后续轻量增量更新 + 缓存固定长度
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - limit: 数量限制（目标K线数量，默认1000）
        - force_fetch: 强制拉取最新数据（00秒扫描时使用）
        
        返回:
        - (K线数据, is_stale) 元组
          - K线数据: [[ts, o, h, l, c, v], ...]
          - is_stale: 是否为陈旧数据（交易所未更新）
        """
        timeframe = timeframe or self.timeframe
        limit = limit or OHLCV_TARGET_BARS  # 默认目标1000根
        key = (symbol, timeframe)
        now_ms = int(time.time() * 1000)
        
        # 获取时间周期毫秒数
        tf_ms = _get_timeframe_ms(timeframe)
        safety_ms = 1500  # 安全边际 1.5 秒
        
        # 检查熔断
        if self.is_circuit_broken("ohlcv", symbol):
            if key in self.ohlcv_cache:
                entry = self.ohlcv_cache[key]
                logger.info(f"[md-circuit] {symbol} {timeframe} 熔断中，使用缓存")
                self.metrics["cache_hits"] += 1
                return entry.data, True  # 熔断时标记为 stale
            raise Exception(f"[熔断中] 无缓存K线数据: {symbol} {timeframe}")
        
        # 单航班去重锁
        with self.locks[key]:
            # ========== 检查是否需要全量初始化 ==========
            need_full_init = False
            if key not in self.ohlcv_cache:
                need_full_init = True
            elif not self.ohlcv_cache[key].is_initialized:
                # 缓存存在但未完成初始化（可能之前拉取失败）
                need_full_init = True
            elif self.ohlcv_cache[key].bars_count < 200:
                # K线数量严重不足，需要重新初始化
                need_full_init = True
                logger.debug(f"[md-reinit] {symbol} {timeframe} K线不足，重新初始化")
            
            # ========== 全量分页拉取（首次初始化）==========
            if need_full_init:
                try:
                    data = self._fetch_full_history(symbol, timeframe, limit)
                    
                    # 修复：接受较少的K线数据（新上线币种可能数据不足）
                    # 最低要求：至少 50 根 K 线才能进行基本的技术分析
                    MIN_BARS_REQUIRED = 50
                    
                    if data and len(data) >= MIN_BARS_REQUIRED:
                        max_ts = max(candle[0] for candle in data)
                        
                        # 创建缓存条目
                        self.ohlcv_cache[key] = OHLCVCacheEntry(
                            data=data,
                            last_max_ts=max_ts,
                            fetched_at_ms=now_ms,
                            is_stale=False,
                            stale_count=0,
                            bars_count=len(data),
                            is_initialized=True
                        )
                        
                        # 从待初始化队列移除
                        if key in self.pending_init:
                            del self.pending_init[key]
                        
                        # 如果数据不足目标数量，打印警告但不失败
                        if len(data) < limit:
                            logger.debug(f"[md-init] {symbol} {timeframe} 数据不足目标 ({len(data)}/{limit} bars)")
                        else:
                            logger.debug(f"[md-init] {symbol} {timeframe} 全量拉取完成 {len(data)} bars")
                        
                        self.reset_circuit_breaker("ohlcv", symbol)
                        return data, False
                    elif data and len(data) > 0:
                        # 数据太少（< 50 根），记录警告但仍然缓存
                        max_ts = max(candle[0] for candle in data)
                        self.ohlcv_cache[key] = OHLCVCacheEntry(
                            data=data,
                            last_max_ts=max_ts,
                            fetched_at_ms=now_ms,
                            is_stale=False,
                            stale_count=0,
                            bars_count=len(data),
                            is_initialized=True  # 标记为已初始化，避免重复拉取
                        )
                        logger.debug(f"[md-init] {symbol} {timeframe} K线数量过少 ({len(data)} bars)")
                        return data, False
                    else:
                        raise Exception(f"全量拉取返回空数据: {symbol} {timeframe}")
                        
                except Exception as e:
                    # 记录到待初始化队列
                    retry_count = self.pending_init.get(key, 0) + 1
                    self.pending_init[key] = retry_count
                    logger.error(f"[md-init-fail] {symbol} {timeframe} 全量拉取失败 (重试次数: {retry_count}): {e}")
                    self.update_circuit_breaker("ohlcv", symbol)
                    raise
            
            # ========== 增量更新（已初始化的缓存）==========
            entry = self.ohlcv_cache[key]
            
            # 计算是否应该有新 K线
            expected_new_ts = entry.last_max_ts + tf_ms
            
            # force_fetch=True 时跳过缓存新鲜度检查，强制拉取
            if not force_fetch and now_ms < expected_new_ts + safety_ms:
                # 未到新 K线时间，直接返回缓存（仍新鲜）
                self.metrics["cache_hits"] += 1
                logger.debug(f"[md-fresh] {symbol} {timeframe} 缓存新鲜，距新K线 {(expected_new_ts - now_ms)/1000:.1f}s")
                return entry.data, False
            
            # 执行增量拉取（只拉取最新的几十根）
            try:
                new_data = self._fetch_incremental(symbol, timeframe, entry.last_max_ts)
                
                self.metrics["cache_misses"] += 1
                
                if new_data and len(new_data) > 0:
                    new_max_ts = max(candle[0] for candle in new_data)
                    
                    if new_max_ts > entry.last_max_ts:
                        # 有新 K线，合并数据并保持固定长度
                        bars_added = sum(1 for c in new_data if c[0] > entry.last_max_ts)
                        merged_data = self._merge_ohlcv(entry.data, new_data, limit)
                        
                        # 更新缓存
                        self.ohlcv_cache[key] = OHLCVCacheEntry(
                            data=merged_data,
                            last_max_ts=new_max_ts,
                            fetched_at_ms=now_ms,
                            is_stale=False,
                            stale_count=0,
                            bars_count=len(merged_data),
                            is_initialized=True
                        )
                        
                        logger.debug(f"[md-incr] {symbol} {timeframe} +{bars_added} bars, total={len(merged_data)}")
                        self.reset_circuit_breaker("ohlcv", symbol)
                        return merged_data, False
                    else:
                        # 交易所还没更新，标记为 stale
                        entry.stale_count += 1
                        entry.is_stale = True
                        entry.fetched_at_ms = now_ms
                        
                        if entry.stale_count >= 3:
                            logger.warning(f"[md-warn] {symbol} {timeframe} stale_count={entry.stale_count} (交易所延迟)")
                        else:
                            logger.debug(f"[md-stale] {symbol} {timeframe} stale_count={entry.stale_count}")
                        
                        return entry.data, True
                else:
                    # 增量拉取返回空数据
                    entry.stale_count += 1
                    entry.is_stale = True
                    logger.debug(f"[md-stale] {symbol} {timeframe} 增量拉取返回空数据")
                    return entry.data, True
                    
            except Exception as e:
                # 增量拉取失败，返回旧缓存
                logger.warning(f"[md-error] {symbol} {timeframe} 增量拉取失败: {e}，使用旧缓存")
                self.update_circuit_breaker("ohlcv", symbol)
                return entry.data, True
    
    def _fetch_full_history(self, symbol: str, timeframe: str, target_bars: int) -> list:
        """
         分页循环拉取全量历史K线（倒序策略）
        
        OKX 单次只返回 100/300 根，需要多次请求拼接直到凑够目标数量
        
        策略：从最新数据向过去拉取（倒序分页）
        - 第一次不带 since，获取最新的 100 根
        - 后续使用 since = 最小时间戳 - 1，向过去拉取
        - 直到凑够目标数量或无更多数据
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - target_bars: 目标K线数量
        
        返回:
        - K线数据列表 [[ts, o, h, l, c, v], ...]（按时间升序）
        """
        tf_ms = _get_timeframe_ms(timeframe)
        all_candles = []
        seen_timestamps = set()
        
        page_count = 0
        # 第一次不带 since，获取最新数据
        current_end_ts = None
        
        logger.debug(f"[md-full] {symbol} {timeframe} 开始倒序分页拉取，目标 {target_bars} bars")
        
        while len(all_candles) < target_bars and page_count < OHLCV_MAX_PAGES:
            page_count += 1
            
            try:
                # 构建请求参数
                if current_end_ts is None:
                    # 第一次请求：不带 since，获取最新数据
                    data, _ = self._request_with_retry(
                        "ohlcv", symbol,
                        lambda: self.exchange.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=timeframe,
                            limit=OHLCV_PAGE_SIZE
                        )
                    )
                else:
                    # 后续请求：使用 params.after 向过去拉取（OKX 特有参数）
                    # OKX 的 after 参数表示获取该时间戳之前的数据
                    end_ts = current_end_ts
                    data, _ = self._request_with_retry(
                        "ohlcv", symbol,
                        lambda: self.exchange.fetch_ohlcv(
                            symbol=symbol,
                            timeframe=timeframe,
                            limit=OHLCV_PAGE_SIZE,
                            params={'after': str(end_ts)}
                        )
                    )
                
                if not data or len(data) == 0:
                    logger.debug(f"[md-full] {symbol} {timeframe} 第{page_count}页返回空数据，停止分页")
                    break
                
                # 去重并添加
                new_count = 0
                min_ts_in_page = float('inf')
                for candle in data:
                    ts = candle[0]
                    if ts not in seen_timestamps:
                        seen_timestamps.add(ts)
                        all_candles.append(candle)
                        new_count += 1
                    if ts < min_ts_in_page:
                        min_ts_in_page = ts
                
                logger.debug(f"[md-full] {symbol} {timeframe} 第{page_count}页: +{new_count} bars, 累计 {len(all_candles)}")
                
                if new_count == 0:
                    # 没有新数据，可能已到达历史最早
                    logger.debug(f"[md-full] {symbol} {timeframe} 无新数据，停止分页")
                    break
                
                # 更新 end_ts 为本页最小时间戳，用于下一页请求
                current_end_ts = min_ts_in_page
                
                # 短暂延迟，避免触发限流
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"[md-full] {symbol} {timeframe} 第{page_count}页拉取失败: {e}")
                break
        
        # 按时间戳排序（升序）
        all_candles.sort(key=lambda x: x[0])
        
        # 保留最新的 target_bars 根
        if len(all_candles) > target_bars:
            all_candles = all_candles[-target_bars:]
        
        logger.debug(f"[md-full] {symbol} {timeframe} 分页拉取完成: {page_count} 页, {len(all_candles)} bars")
        
        return all_candles
    
    def _fetch_incremental(self, symbol: str, timeframe: str, since_ts: int) -> list:
        """
         增量拉取最新K线
        
        只请求 since_ts 之后的数据，数量限制为 OHLCV_INCREMENTAL_LIMIT
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - since_ts: 起始时间戳（毫秒）
        
        返回:
        - 新K线数据列表
        """
        try:
            data, _ = self._request_with_retry(
                "ohlcv", symbol,
                lambda: self.exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since_ts,
                    limit=OHLCV_INCREMENTAL_LIMIT
                )
            )
            return data if data else []
        except Exception as e:
            logger.warning(f"[md-incr] {symbol} {timeframe} 增量拉取失败: {e}")
            raise
    
    def _merge_ohlcv(self, cached_data: list, new_data: list, limit: int) -> list:
        """
        合并K线数据，去重并保留最新的 limit 根（固定长度缓存）
        
        参数:
        - cached_data: 缓存的K线数据
        - new_data: 新拉取的K线数据
        - limit: 保留数量（默认1000）
        
        返回:
        - 合并后的K线数据（固定长度）
        """
        # 使用时间戳作为 key 去重
        ts_map = {}
        for candle in cached_data:
            ts_map[candle[0]] = candle
        for candle in new_data:
            ts_map[candle[0]] = candle  # 新数据覆盖旧数据
        
        # 按时间戳排序
        sorted_candles = sorted(ts_map.values(), key=lambda x: x[0])
        
        # 关键：执行 tail(limit) 保持缓存长度恒定，丢弃过期数据
        if len(sorted_candles) > limit:
            sorted_candles = sorted_candles[-limit:]
        
        return sorted_candles
    
    def get_pending_init_symbols(self) -> list:
        """
        获取待初始化的币种列表
        
        返回:
        - [(symbol, timeframe, retry_count), ...]
        """
        return [(k[0], k[1], v) for k, v in self.pending_init.items()]
    
    def retry_pending_init(self, max_retries: int = 3) -> Dict[str, bool]:
        """
        重试待初始化的币种
        
        参数:
        - max_retries: 最大重试次数，超过则放弃
        
        返回:
        - {(symbol, timeframe): success} 字典
        """
        results = {}
        keys_to_retry = list(self.pending_init.keys())
        
        for key in keys_to_retry:
            symbol, timeframe = key
            retry_count = self.pending_init.get(key, 0)
            
            if retry_count >= max_retries:
                logger.warning(f"[md-skip] {symbol} {timeframe} 重试次数超限 ({retry_count} >= {max_retries})，跳过")
                results[key] = False
                continue
            
            try:
                logger.debug(f"[md-retry] {symbol} {timeframe} 重试初始化 (第{retry_count + 1}次)")
                self.get_ohlcv(symbol, timeframe, force_fetch=True)
                results[key] = True
            except Exception as e:
                logger.debug(f"[md-retry-fail] {symbol} {timeframe} 重试失败: {e}")
                results[key] = False
        
        return results
    
    def get_cache_status(self) -> Dict[str, Any]:
        """
        获取缓存状态摘要
        
        返回:
        - 缓存状态字典
        """
        status = {
            "total_cached": len(self.ohlcv_cache),
            "initialized": 0,
            "pending_init": len(self.pending_init),
            "details": []
        }
        
        for key, entry in self.ohlcv_cache.items():
            symbol, timeframe = key
            if entry.is_initialized:
                status["initialized"] += 1
            
            status["details"].append({
                "symbol": symbol,
                "timeframe": timeframe,
                "bars": entry.bars_count,
                "initialized": entry.is_initialized,
                "stale": entry.is_stale,
                "stale_count": entry.stale_count
            })
        
        return status
    
    def get_ohlcv_data_only(self, symbol, timeframe=None, limit=None) -> list:
        """
        获取K线数据（仅数据，不返回 is_stale）- 兼容旧接口
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - limit: 数量限制
        
        返回:
        - K线数据
        """
        data, _ = self.get_ohlcv(symbol, timeframe, limit)
        return data
    
    def get_ticker(self, symbol):
        """
        获取实时行情，支持TTL缓存和单航班去重
        
        参数:
        - symbol: 交易对
        
        返回:
        - 实时行情数据
        """
        key = symbol
        now = time.time()
        
        # 检查熔断
        if self.is_circuit_broken("ticker", symbol):
            if key in self.ticker_cache:
                logger.info(f"[熔断中] 使用缓存的行情数据: {symbol}")
                self.metrics["cache_hits"] += 1
                return self.ticker_cache[key][0]
            raise Exception(f"[熔断中] 无缓存行情数据: {symbol}")
        
        # 检查缓存
        if key in self.ticker_cache:
            cached_data, fetched_at, last_error = self.ticker_cache[key]
            if now - fetched_at < self.TICKER_TTL_SEC:
                self.metrics["cache_hits"] += 1
                return cached_data
        
        # 单航班去重
        with self.locks[key]:
            if self.pending[key].is_set():
                self.pending[key].wait()
                if key in self.ticker_cache:
                    self.metrics["cache_hits"] += 1
                    return self.ticker_cache[key][0]
                raise Exception(f"等待API调用超时: {key}")
            
            self.pending[key].clear()
            
            try:
                # 使用带重试的请求
                data, api_latency = self._request_with_retry(
                    "ticker", symbol, 
                    self.exchange.fetch_ticker, symbol
                )
                
                self.metrics["cache_misses"] += 1
                
                # 更新缓存
                self.ticker_cache[key] = (data, time.time(), None)
                
                # 重置熔断状态
                self.reset_circuit_breaker("ticker", symbol)
                
                return data
            except Exception as e:
                # 检查是否有旧缓存可以返回
                if key in self.ticker_cache:
                    logger.warning(f"[行情获取失败] 使用旧缓存: {symbol} - {e}")
                    self.metrics["cache_hits"] += 1
                    return self.ticker_cache[key][0]
                
                # 更新熔断状态
                self.update_circuit_breaker("ticker", symbol)
                
                raise
            finally:
                self.pending[key].set()
    
    def get_balance(self, params=None):
        """
        获取账户余额，支持TTL缓存和单航班去重
        
        参数:
        - params: 可选参数
        
        返回:
        - 账户余额数据
        """
        key = "balance"
        now = time.time()
        
        # 检查熔断
        if self.is_circuit_broken("balance", "global"):
            if key in self.balance_cache:
                logger.info(f"[熔断中] 使用缓存的余额数据")
                self.metrics["cache_hits"] += 1
                return self.balance_cache[key][0]
            raise Exception(f"[熔断中] 无缓存余额数据")
        
        # 检查缓存
        if key in self.balance_cache:
            cached_data, fetched_at, last_error = self.balance_cache[key]
            if now - fetched_at < self.BALANCE_TTL_SEC:
                self.metrics["cache_hits"] += 1
                return cached_data
        
        # 单航班去重
        with self.locks[key]:
            if self.pending[key].is_set():
                self.pending[key].wait()
                if key in self.balance_cache:
                    self.metrics["cache_hits"] += 1
                    return self.balance_cache[key][0]
                raise Exception(f"等待API调用超时: {key}")
            
            self.pending[key].clear()
            
            try:
                # 使用带重试的请求
                data, api_latency = self._request_with_retry(
                    "balance", "global", 
                    self.exchange.fetch_balance, params
                )
                
                self.metrics["cache_misses"] += 1
                
                # 更新缓存
                self.balance_cache[key] = (data, time.time(), None)
                
                # 重置熔断状态
                self.reset_circuit_breaker("balance", "global")
                
                return data
            except Exception as e:
                # 检查是否有旧缓存可以返回
                if key in self.balance_cache:
                    logger.warning(f"[余额获取失败] 使用旧缓存 - {e}")
                    self.metrics["cache_hits"] += 1
                    return self.balance_cache[key][0]
                
                # 更新熔断状态
                self.update_circuit_breaker("balance", "global")
                
                raise
            finally:
                self.pending[key].set()
    
    def get_positions(self, symbols=None):
        """
        获取持仓信息，支持TTL缓存和单航班去重
        
        参数:
        - symbols: 交易对列表
        
        返回:
        - 持仓数据
        """
        key = "positions"
        now = time.time()
        
        # 检查熔断
        if self.is_circuit_broken("positions", "global"):
            if key in self.positions_cache:
                logger.info(f"[熔断中] 使用缓存的持仓数据")
                self.metrics["cache_hits"] += 1
                return self.positions_cache[key][0]
            raise Exception(f"[熔断中] 无缓存持仓数据")
        
        # 检查缓存
        if key in self.positions_cache:
            cached_data, fetched_at, last_error = self.positions_cache[key]
            if now - fetched_at < self.POSITIONS_TTL_SEC:
                self.metrics["cache_hits"] += 1
                return cached_data
        
        # 单航班去重
        with self.locks[key]:
            if self.pending[key].is_set():
                self.pending[key].wait()
                if key in self.positions_cache:
                    self.metrics["cache_hits"] += 1
                    return self.positions_cache[key][0]
                raise Exception(f"等待API调用超时: {key}")
            
            self.pending[key].clear()
            
            try:
                # 使用带重试的请求
                data, api_latency = self._request_with_retry(
                    "positions", "global", 
                    self.exchange.fetch_positions, symbols
                )
                
                self.metrics["cache_misses"] += 1
                
                # 更新缓存
                self.positions_cache[key] = (data, time.time(), None)
                
                # 重置熔断状态
                self.reset_circuit_breaker("positions", "global")
                
                return data
            except Exception as e:
                # 检查是否有旧缓存可以返回
                if key in self.positions_cache:
                    logger.warning(f"[持仓获取失败] 使用旧缓存 - {e}")
                    self.metrics["cache_hits"] += 1
                    return self.positions_cache[key][0]
                
                # 更新熔断状态
                self.update_circuit_breaker("positions", "global")
                
                raise
            finally:
                self.pending[key].set()
    
    def invalidate_balance(self):
        """
        使余额缓存失效
        """
        if "balance" in self.balance_cache:
            del self.balance_cache["balance"]
            logger.info("余额缓存已失效")
    
    def invalidate_positions(self):
        """
        使持仓缓存失效
        """
        if "positions" in self.positions_cache:
            del self.positions_cache["positions"]
            logger.info("持仓缓存已失效")
    
    def invalidate_ohlcv(self, symbol, timeframe=None, limit=None):
        """
        使K线缓存失效
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期（如果为 None，则清除该 symbol 的所有周期缓存）
        - limit: 数量限制（已废弃，保留兼容性）
        """
        if timeframe:
            key = (symbol, timeframe)
            if key in self.ohlcv_cache:
                del self.ohlcv_cache[key]
                logger.debug(f"[md-invalidate] {symbol} {timeframe} 缓存已清除")
        else:
            # 清除该 symbol 的所有周期缓存
            keys_to_delete = [k for k in self.ohlcv_cache.keys() if k[0] == symbol]
            for key in keys_to_delete:
                del self.ohlcv_cache[key]
            if keys_to_delete:
                logger.debug(f"[md-invalidate] {symbol} 所有周期缓存已清除 ({len(keys_to_delete)} 个)")
    
    def invalidate_ticker(self, symbol):
        """
        使行情缓存失效
        
        参数:
        - symbol: 交易对
        """
        if symbol in self.ticker_cache:
            del self.ticker_cache[symbol]
            logger.info(f"行情缓存已失效: {symbol}")
    
    def is_circuit_broken(self, endpoint, symbol):
        """
        检查特定端点和交易对的熔断状态
        
        参数:
        - endpoint: 端点名称
        - symbol: 交易对
        
        返回:
        - 是否熔断
        """
        now = time.time()
        key = f"{endpoint}:{symbol}"
        
        if key not in self.circuit_breakers:
            return False
        
        state = self.circuit_breakers[key]
        if now < state["until"]:
            return True
        
        # 熔断已过期
        del self.circuit_breakers[key]
        return False
    
    def update_circuit_breaker(self, endpoint, symbol):
        """
        更新熔断状态
        
        参数:
        - endpoint: 端点名称
        - symbol: 交易对
        """
        key = f"{endpoint}:{symbol}"
        now = time.time()
        
        if key not in self.circuit_breakers:
            self.circuit_breakers[key] = {
                "failures": 1,
                "until": 0
            }
        else:
            self.circuit_breakers[key]["failures"] += 1
        
        failures = self.circuit_breakers[key]["failures"]
        
        # 连续5次失败触发熔断
        if failures >= 5:
            # 熔断时间30-60秒随机
            cooldown = random.randint(30, 60)
            self.circuit_breakers[key]["until"] = now + cooldown
            logger.warning(f"[熔断触发] {endpoint} {symbol}: {failures}次失败 → 熔断{cooldown}秒")
    
    def reset_circuit_breaker(self, endpoint, symbol):
        """
        重置熔断状态
        
        参数:
        - endpoint: 端点名称
        - symbol: 交易对
        """
        key = f"{endpoint}:{symbol}"
        if key in self.circuit_breakers:
            del self.circuit_breakers[key]
    
    def record_error(self, endpoint, symbol, error_msg):
        """
        记录错误并实现错误节流
        
        参数:
        - endpoint: 端点名称
        - symbol: 交易对
        - error_msg: 错误信息
        """
        now = time.time()
        self.error_counts[(endpoint, symbol)] += 1
        
        # 错误节流，每30秒汇总一次
        if now - self.last_error_summary > 30:
            summary = []
            for (ep, sym), count in self.error_counts.items():
                if count > 0:
                    summary.append(f"{ep} {sym}: {count}次")
            
            if summary:
                logger.error(f"[错误汇总] {', '.join(summary)}")
            
            # 重置计数
            self.error_counts.clear()
            self.last_error_summary = now
    
    def get_metrics(self):
        """
        获取指标数据
        
        返回:
        - 指标字典
        """
        avg_latency = 0
        if self.metrics["api_calls"] > 0:
            avg_latency = sum(self.metrics["api_latency_ms"]) / self.metrics["api_calls"]
        
        cache_hit_rate = 0
        total_requests = self.metrics["cache_hits"] + self.metrics["cache_misses"]
        if total_requests > 0:
            cache_hit_rate = self.metrics["cache_hits"] / total_requests
        
        return {
            "api_calls": self.metrics["api_calls"],
            "avg_api_latency_ms": round(avg_latency, 2),
            "cache_hits": self.metrics["cache_hits"],
            "cache_misses": self.metrics["cache_misses"],
            "cache_hit_rate": round(cache_hit_rate, 4),
            "errors": self.metrics["errors"],
            "circuit_breakers": len(self.circuit_breakers)
        }
    
    def reset_metrics(self):
        """
        重置指标
        """
        self.metrics = {
            "api_calls": 0,
            "api_latency_ms": [],
            "cache_hits": 0,
            "cache_misses": 0,
            "errors": 0,
            "last_error_time": 0
        }
    
    # ============  双通道K线数据支持 ============
    
    def get_dual_channel_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = None, 
        limit: int = None,
        use_incremental: bool = True
    ) -> Tuple[Optional['DualChannelOHLCV'], bool]:
        """
        获取双通道K线数据
        
        明确区分 forming_candle (candles[-1]) 和 last_closed_candle (candles[-2])
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - limit: 数量限制
        - use_incremental: 是否使用增量拉取（已废弃，智能缓存自动处理）
        
        返回:
        - (DualChannelOHLCV 对象, is_stale) 元组
          - DualChannelOHLCV: 如果数据不足则为 None
          - is_stale: 是否为陈旧数据
        """
        if not DUAL_CHANNEL_AVAILABLE:
            logger.warning("Dual channel OHLCV not available")
            return None, True
        
        timeframe = timeframe or self.timeframe
        limit = limit or self.ohlcv_limit
        
        # 获取原始K线数据（使用智能缓存）
        candles, is_stale = self.get_ohlcv(symbol, timeframe, limit)
        
        if not candles or len(candles) < 2:
            logger.warning(f"Insufficient candles for dual channel: {symbol}/{timeframe}")
            return None, True
        
        try:
            # 创建 DualChannelOHLCV 对象
            dual_channel = DualChannelOHLCV.from_candles(
                symbol=symbol,
                timeframe=timeframe,
                candles=candles,
                fetch_time=int(time.time() * 1000)
            )
            
            return dual_channel, is_stale
            
        except InsufficientDataError as e:
            logger.warning(f"Insufficient data for dual channel: {e}")
            return None, True
        except Exception as e:
            logger.error(f"Error creating DualChannelOHLCV: {e}")
            return None, True
    
    def get_ohlcv_with_since(
        self, 
        symbol: str, 
        timeframe: str = None, 
        limit: int = None
    ) -> Tuple[list, bool]:
        """
        使用增量拉取获取K线数据（已整合到 get_ohlcv，此方法保留兼容性）
        
        参数:
        - symbol: 交易对
        - timeframe: 时间周期
        - limit: 数量限制
        
        返回:
        - (K线数据, is_stale) 元组
        """
        # 直接调用新的智能缓存方法
        return self.get_ohlcv(symbol, timeframe, limit)


# ============  双 Key 机制：行情专用 Provider 工厂 ============

def create_market_data_exchange(use_market_key: bool = True):
    """
    创建行情数据专用的交易所适配器
    
     双 Key 机制：
    - use_market_key=True: 优先使用行情专用 Key (MARKET_DATA_API_KEY)
    - use_market_key=False: 使用交易 Key (OKX_API_KEY)
    
    参数:
    - use_market_key: 是否使用行情专用 Key
    
    返回:
    - (exchange_adapter, is_dedicated_key) 元组
      - exchange_adapter: ccxt.okx 实例
      - is_dedicated_key: 是否使用了独立行情 Key
    """
    import ccxt
    
    # 优先从数据库读取 Key（UI 配置的 Key）
    market_key = ""
    market_secret = ""
    market_passphrase = ""
    trade_key = ""
    trade_secret = ""
    trade_passphrase = ""
    
    try:
        from core.config_manager import get_config_manager
        config_mgr = get_config_manager()
        creds = config_mgr.load_credentials()  # 修正方法名
        
        # 从数据库读取行情专用 Key
        if creds.has_market_key():
            market_key = creds.market_api_key
            market_secret = creds.market_api_secret
            market_passphrase = creds.market_api_passphrase
            logger.debug("[MarketData] 从配置文件加载行情 Key")
        
        # 从数据库读取交易 Key
        if creds.has_trade_key():
            trade_key = creds.trade_api_key
            trade_secret = creds.trade_api_secret
            trade_passphrase = creds.trade_api_passphrase
            logger.debug("[MarketData] 从配置文件加载交易 Key")
    except Exception as e:
        logger.debug(f"[MarketData] 配置文件读取失败，回退到环境变量: {e}")
    
    # 回退到环境变量
    if not market_key:
        market_key = os.getenv("MARKET_DATA_API_KEY", "")
        market_secret = os.getenv("MARKET_DATA_SECRET", "")
        market_passphrase = os.getenv("MARKET_DATA_PASSPHRASE", "")
    
    if not trade_key:
        trade_key = os.getenv("OKX_API_KEY", "")
        trade_secret = os.getenv("OKX_API_SECRET", "")
        trade_passphrase = os.getenv("OKX_API_PASSPHRASE", "")
    
    # 决定使用哪套 Key
    is_dedicated_key = False
    if use_market_key and market_key and market_secret and market_passphrase:
        api_key = market_key
        api_secret = market_secret
        api_passphrase = market_passphrase
        is_dedicated_key = True
        logger.info("[MarketData] 使用独立行情 Key ")
    else:
        api_key = trade_key
        api_secret = trade_secret
        api_passphrase = trade_passphrase
        if use_market_key:
            logger.debug("[MarketData] 未配置独立行情 Key，使用交易 Key")
        else:
            logger.info("[MarketData] 使用交易 Key")
    
    # 获取代理配置
    http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
    https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
    
    # 创建 ccxt 配置
    config = {
        'enableRateLimit': True,
        'options': {
            'defaultType': 'swap',
        }
    }
    
    # 添加代理
    if https_proxy:
        config['proxies'] = {
            'http': http_proxy or https_proxy,
            'https': https_proxy
        }
    
    # 添加 API 凭证
    if api_key and api_secret and api_passphrase:
        config['apiKey'] = api_key
        config['secret'] = api_secret
        config['password'] = api_passphrase
    
    exchange = ccxt.okx(config)
    return exchange, is_dedicated_key


def create_market_data_provider_with_dedicated_key(
    timeframe: str = '1m',
    ohlcv_limit: int = 1000,
    **kwargs
) -> 'MarketDataProvider':
    """
    创建使用行情专用 Key 的 MarketDataProvider
    
     双 Key 机制：自动使用行情专用 Key，与交易接口隔离
    
    参数:
    - timeframe: 默认时间周期
    - ohlcv_limit: 默认 K线数量
    - **kwargs: 其他 MarketDataProvider 参数
    
    返回:
    - MarketDataProvider 实例
    """
    exchange, is_dedicated = create_market_data_exchange(use_market_key=True)
    
    provider = MarketDataProvider(
        exchange_adapter=exchange,
        timeframe=timeframe,
        ohlcv_limit=ohlcv_limit,
        **kwargs
    )
    
    # 记录 Key 类型
    provider._is_dedicated_market_key = is_dedicated
    
    return provider


# ============  WebSocket 数据源支持 ============

# WebSocket 客户端导入
try:
    from exchange.okx_websocket import (
        OKXWebSocketClient, 
        get_ws_client, 
        start_ws_client, 
        stop_ws_client,
        is_ws_available,
        WEBSOCKET_AVAILABLE
    )
    WS_IMPORT_OK = True
except ImportError:
    WS_IMPORT_OK = False
    WEBSOCKET_AVAILABLE = False
    logger.warning("okx_websocket module not available")


class WebSocketMarketDataProvider:
    """
    WebSocket 数据源提供者
    
    特点：
    - 实时推送，低延迟
    - 自动重连
    - 与 REST 数据源可切换
    
    使用场景：
    - K线图实时更新（固定使用 WebSocket）
    - 交易引擎可选数据源
    """
    
    def __init__(self, use_aws: bool = False, fallback_provider: MarketDataProvider = None):
        """
        初始化 WebSocket 数据源
        
        Args:
            use_aws: 是否使用 AWS 节点
            fallback_provider: REST 回退数据源
        """
        self.use_aws = use_aws
        self.fallback_provider = fallback_provider
        self.ws_client: Optional[OKXWebSocketClient] = None
        self._subscribed_symbols: Dict[str, str] = {}  # {symbol: timeframe}
        
        # 本地历史数据缓存（混合模式核心）
        # {symbol: {timeframe: {'data': [...], 'last_ts': int, 'initialized': bool}}}
        self._history_cache: Dict[str, Dict[str, Dict]] = {}
        self._cache_lock = threading.Lock()
        
        # 初始化 WebSocket 客户端
        if WS_IMPORT_OK and WEBSOCKET_AVAILABLE:
            self.ws_client = get_ws_client(use_aws)
        else:
            logger.warning("[WS-Provider] WebSocket 不可用，将使用 REST 回退")
    
    def start(self) -> bool:
        """启动 WebSocket 连接"""
        if self.ws_client:
            return self.ws_client.start()
        return False
    
    def stop(self):
        """停止 WebSocket 连接"""
        if self.ws_client:
            self.ws_client.stop()
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.ws_client and self.ws_client.is_connected()
    
    def subscribe(self, symbol: str, timeframe: str = "1m") -> bool:
        """
        订阅 K线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            是否订阅成功
        """
        if not self.ws_client:
            return False
        
        # 确保连接
        if not self.ws_client.is_connected():
            if not self.ws_client.start():
                logger.warning(f"[WS-Provider] 无法连接，订阅失败: {symbol}")
                return False
        
        # 订阅 K线
        success = self.ws_client.subscribe_candles(symbol, timeframe)
        if success:
            self._subscribed_symbols[symbol] = timeframe
        
        return success
    
    def unsubscribe(self, symbol: str) -> bool:
        """取消订阅"""
        if not self.ws_client:
            return False
        
        timeframe = self._subscribed_symbols.get(symbol, "1m")
        success = self.ws_client.unsubscribe(symbol, "candle", timeframe)
        
        if symbol in self._subscribed_symbols:
            del self._subscribed_symbols[symbol]
        
        return success
    
    def get_ohlcv(
        self, 
        symbol: str, 
        timeframe: str = "1m", 
        limit: int = 500,
        fallback_to_rest: bool = True
    ) -> Tuple[list, bool]:
        """
        获取 K线数据（混合模式）
        
         混合模式逻辑：
        1. 首次请求：用 REST 拉取完整历史数据，缓存到本地
        2. 后续请求：用 WebSocket 增量更新最新 K 线
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            limit: 数量限制
            fallback_to_rest: 是否回退到 REST
        
        Returns:
            (K线数据, is_from_ws) 元组
        """
        cache_key = f"{symbol}:{timeframe}"
        
        with self._cache_lock:
            # 初始化缓存结构
            if symbol not in self._history_cache:
                self._history_cache[symbol] = {}
            if timeframe not in self._history_cache[symbol]:
                self._history_cache[symbol][timeframe] = {
                    'data': [],
                    'last_ts': 0,
                    'initialized': False
                }
            
            cache_entry = self._history_cache[symbol][timeframe]
        
        # 首次请求：用 REST 拉取完整历史数据
        if not cache_entry['initialized']:
            if fallback_to_rest and self.fallback_provider:
                logger.info(f"[WS-Provider] 首次加载 {symbol} {timeframe}，使用 REST 拉取历史数据...")
                data, is_stale = self.fallback_provider.get_ohlcv(symbol, timeframe, limit)
                
                if data and len(data) > 0:
                    with self._cache_lock:
                        cache_entry['data'] = data
                        cache_entry['last_ts'] = data[-1][0] if data else 0
                        cache_entry['initialized'] = True
                    
                    # 确保 WebSocket 已订阅
                    if self.ws_client and self.ws_client.is_connected():
                        if symbol not in self._subscribed_symbols:
                            self.subscribe(symbol, timeframe)
                    
                    logger.info(f"[WS-Provider] {symbol} {timeframe} 历史数据已缓存: {len(data)} bars")
                    return data, False
                else:
                    return [], False
            else:
                return [], False
        
        # 后续请求：用 WebSocket 增量更新
        if self.ws_client and self.ws_client.is_connected():
            # 确保已订阅
            if symbol not in self._subscribed_symbols:
                self.subscribe(symbol, timeframe)
            
            # 获取 WebSocket 最新数据
            ws_data = self.ws_client.get_candles(symbol, timeframe, 10)  # 只取最新几根
            
            if ws_data and len(ws_data) > 0:
                with self._cache_lock:
                    cached_data = cache_entry['data']
                    last_cached_ts = cache_entry['last_ts']
                    
                    # 合并新数据
                    updated = False
                    for candle in ws_data:
                        candle_ts = candle[0]
                        
                        if candle_ts > last_cached_ts:
                            # 新 K 线，追加
                            cached_data.append(candle)
                            updated = True
                        elif candle_ts == last_cached_ts:
                            # 更新最后一根（可能还在形成中）
                            if cached_data:
                                cached_data[-1] = candle
                                updated = True
                    
                    if updated:
                        # 保持数据量不超过 limit
                        if len(cached_data) > limit:
                            cached_data = cached_data[-limit:]
                        
                        cache_entry['data'] = cached_data
                        cache_entry['last_ts'] = cached_data[-1][0] if cached_data else 0
                    
                    result_data = cached_data[-limit:] if len(cached_data) > limit else cached_data
                
                logger.debug(f"[WS-Provider] {symbol} {timeframe} 增量更新完成: {len(result_data)} bars")
                return result_data, True
        
        # WebSocket 不可用，返回缓存数据
        with self._cache_lock:
            cached_data = cache_entry['data']
            result_data = cached_data[-limit:] if len(cached_data) > limit else cached_data
        
        return result_data, False
    
    def get_ticker(self, symbol: str, fallback_to_rest: bool = True) -> Optional[Dict]:
        """
        获取实时行情
        
        Args:
            symbol: 交易对
            fallback_to_rest: 是否回退到 REST
        
        Returns:
            行情数据
        """
        # 尝试从 WebSocket 获取
        if self.ws_client and self.ws_client.is_connected():
            ticker = self.ws_client.get_ticker(symbol)
            if ticker:
                return ticker
        
        # 回退到 REST
        if fallback_to_rest and self.fallback_provider:
            return self.fallback_provider.get_ticker(symbol)
        
        return None
    
    def get_last_price(self, symbol: str) -> Optional[float]:
        """获取最新价格"""
        ticker = self.get_ticker(symbol)
        if ticker:
            return ticker.get("last")
        return None
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {
            "ws_available": WS_IMPORT_OK and WEBSOCKET_AVAILABLE,
            "ws_connected": self.is_connected(),
            "subscribed_symbols": list(self._subscribed_symbols.keys()),
            "has_fallback": self.fallback_provider is not None
        }
        
        if self.ws_client:
            stats.update(self.ws_client.get_cache_stats())
        
        # 添加本地缓存统计
        with self._cache_lock:
            cache_stats = {}
            for symbol, tf_data in self._history_cache.items():
                for tf, entry in tf_data.items():
                    key = f"{symbol}:{tf}"
                    cache_stats[key] = {
                        'bars': len(entry['data']),
                        'initialized': entry['initialized']
                    }
            stats['history_cache'] = cache_stats
        
        return stats
    
    def clear_cache(self, symbol: str = None, timeframe: str = None):
        """
        清除本地历史数据缓存
        
        Args:
            symbol: 指定币种（None 表示全部）
            timeframe: 指定周期（None 表示全部）
        """
        with self._cache_lock:
            if symbol is None:
                # 清除全部
                self._history_cache.clear()
                logger.info("[WS-Provider] 已清除全部历史数据缓存")
            elif timeframe is None:
                # 清除指定币种的全部周期
                if symbol in self._history_cache:
                    del self._history_cache[symbol]
                    logger.info(f"[WS-Provider] 已清除 {symbol} 的历史数据缓存")
            else:
                # 清除指定币种的指定周期
                if symbol in self._history_cache and timeframe in self._history_cache[symbol]:
                    del self._history_cache[symbol][timeframe]
                    logger.info(f"[WS-Provider] 已清除 {symbol} {timeframe} 的历史数据缓存")


def create_hybrid_market_data_provider(
    exchange_adapter,
    timeframe: str = '1m',
    ohlcv_limit: int = 1000,
    enable_websocket: bool = False,
    use_aws: bool = False,
    **kwargs
) -> Tuple[MarketDataProvider, Optional[WebSocketMarketDataProvider]]:
    """
    创建混合数据源提供者
    
    返回 REST 和 WebSocket 两个提供者，可根据配置切换
    
    Args:
        exchange_adapter: 交易所适配器
        timeframe: 默认时间周期
        ohlcv_limit: 默认 K线数量
        enable_websocket: 是否启用 WebSocket
        use_aws: WebSocket 是否使用 AWS 节点
        **kwargs: 其他参数
    
    Returns:
        (rest_provider, ws_provider) 元组
    """
    # 创建 REST 提供者
    rest_provider = MarketDataProvider(
        exchange_adapter=exchange_adapter,
        timeframe=timeframe,
        ohlcv_limit=ohlcv_limit,
        **kwargs
    )
    
    # 创建 WebSocket 提供者（如果启用）
    ws_provider = None
    if enable_websocket and WS_IMPORT_OK and WEBSOCKET_AVAILABLE:
        ws_provider = WebSocketMarketDataProvider(
            use_aws=use_aws,
            fallback_provider=rest_provider
        )
        logger.info("[Hybrid] WebSocket 数据源已创建")
    
    return rest_provider, ws_provider

