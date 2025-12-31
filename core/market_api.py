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
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
"""
market_api.py - 独立的行情数据接口服务

为 Streamlit UI 提供 K线数据，与交易引擎完全解耦。
使用 FastAPI + 内存缓存（TTL 2秒）防止 IP 被禁。

启动方式：
    uvicorn market_api:app --host 0.0.0.0 --port 8000
    或
    python market_api.py
"""

import os
import sys
import time
import ccxt
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from dotenv import load_dotenv
import traceback

# 添加项目根目录到 Python 路径（用于导入策略模块）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 加载环境变量
load_dotenv()

# ============ FastAPI 应用 ============
try:
    from fastapi import FastAPI, Query, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("⚠️ FastAPI 未安装，请运行: pip install fastapi uvicorn")


# ============ 内存缓存 ============
@dataclass
class CacheEntry:
    """缓存条目"""
    data: List[List]
    fetched_at: float
    symbol: str
    timeframe: str


class KlineCache:
    """K线数据缓存（TTL 2秒）"""
    
    def __init__(self, ttl_sec: float = 2.0):
        self.ttl_sec = ttl_sec
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, symbol: str, timeframe: str) -> Optional[List[List]]:
        """获取缓存数据"""
        key = f"{symbol}:{timeframe}"
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry.fetched_at < self.ttl_sec:
                return entry.data
            # 缓存过期，删除
            del self._cache[key]
        return None
    
    def set(self, symbol: str, timeframe: str, data: List[List]) -> None:
        """设置缓存数据"""
        key = f"{symbol}:{timeframe}"
        self._cache[key] = CacheEntry(
            data=data,
            fetched_at=time.time(),
            symbol=symbol,
            timeframe=timeframe
        )
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()


# ============ OKX 交易所连接 ============
class OKXClient:
    """OKX 交易所客户端（只读，用于获取行情）
    
     双 Key 机制：优先使用行情专用 Key，避免挤占交易接口的 Rate Limit
    """
    
    def __init__(self):
        self.exchange = None
        self.is_dedicated_key = False  # 是否使用独立行情 Key
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接（优先使用行情专用 Key）"""
        try:
            # 双 Key 机制：优先使用行情专用 Key
            market_key = os.getenv("MARKET_DATA_API_KEY", "")
            market_secret = os.getenv("MARKET_DATA_SECRET", "")
            market_passphrase = os.getenv("MARKET_DATA_PASSPHRASE", "")
            
            # 回退到交易 Key
            api_key = market_key or os.getenv("OKX_API_KEY", "")
            api_secret = market_secret or os.getenv("OKX_API_SECRET", "")
            api_passphrase = market_passphrase or os.getenv("OKX_API_PASSPHRASE", "")
            
            # 记录是否使用独立行情 Key
            self.is_dedicated_key = bool(market_key and market_secret and market_passphrase)
            
            # 获取代理配置
            http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
            https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            
            config = {
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # 永续合约
                }
            }
            
            # 添加代理支持
            if https_proxy:
                config['proxies'] = {
                    'http': http_proxy or https_proxy,
                    'https': https_proxy
                }
                print(f"🌐 使用代理: {https_proxy}")
            
            # 如果有 API 密钥，添加认证
            if api_key and api_secret and api_passphrase:
                config['apiKey'] = api_key
                config['secret'] = api_secret
                config['password'] = api_passphrase
            
            self.exchange = ccxt.okx(config)
            
            # 打印 Key 类型
            if self.is_dedicated_key:
                print("✅ OKX 行情服务初始化成功 (使用独立行情 Key 🔑)")
            else:
                print("✅ OKX 行情服务初始化成功 (使用交易 Key)")
        except Exception as e:
            print(f"❌ OKX 交易所连接失败: {e}")
            self.exchange = None
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 500) -> List[List]:
        """
        获取 K线数据（支持分页拉取超过 300 根）
        
        参数:
        - symbol: 交易对，如 "BTC/USDT:USDT"
        - timeframe: 时间周期，如 "1m", "5m", "1h"
        - limit: K线数量
        
        返回:
        - [[timestamp, open, high, low, close, volume], ...]
        """
        if not self.exchange:
            raise Exception("交易所未连接")
        
        try:
            # OKX 单次最多返回 300 根 K线，需要分页拉取
            OKX_PAGE_SIZE = 300
            
            if limit <= OKX_PAGE_SIZE:
                # 单次请求即可
                return self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            # 分页拉取逻辑
            tf_ms = self._get_timeframe_ms(timeframe)
            all_candles = []
            seen_timestamps = set()
            
            # 计算起始时间（从过去开始向后拉取）
            now_ms = int(time.time() * 1000)
            start_ts = now_ms - (limit + 50) * tf_ms  # 多拉一些确保足够
            
            current_since = start_ts
            max_pages = (limit // OKX_PAGE_SIZE) + 3  # 最多拉取的页数
            
            for page in range(max_pages):
                if len(all_candles) >= limit:
                    break
                
                data = self.exchange.fetch_ohlcv(
                    symbol, timeframe, 
                    since=current_since, 
                    limit=OKX_PAGE_SIZE
                )
                
                if not data:
                    break
                
                # 去重并添加
                new_count = 0
                max_ts = 0
                for candle in data:
                    ts = candle[0]
                    if ts not in seen_timestamps:
                        seen_timestamps.add(ts)
                        all_candles.append(candle)
                        new_count += 1
                    if ts > max_ts:
                        max_ts = ts
                
                if new_count == 0:
                    break
                
                # 检查是否已拉取到最新
                if max_ts >= now_ms - tf_ms:
                    break
                
                # 更新 since 为本页最大时间戳 + 1ms
                current_since = max_ts + 1
                
                # 短暂延迟避免限流
                time.sleep(0.05)
            
            # 按时间戳排序并截取
            all_candles.sort(key=lambda x: x[0])
            return all_candles[-limit:] if len(all_candles) > limit else all_candles
            
        except Exception as e:
            raise Exception(f"获取K线失败: {e}")
    
    def _get_timeframe_ms(self, timeframe: str) -> int:
        """将时间周期转换为毫秒"""
        tf_map = {
            '1m': 60 * 1000,
            '3m': 3 * 60 * 1000,
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '2h': 2 * 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '6h': 6 * 60 * 60 * 1000,
            '12h': 12 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000,
            '1w': 7 * 24 * 60 * 60 * 1000,
        }
        return tf_map.get(timeframe, 60 * 1000)


# ============ 全局实例 ============
cache = KlineCache(ttl_sec=2.0)
okx_client = OKXClient()


# ============ 策略信号计算 ============
def _calculate_strategy_markers(ohlcv: List[List], symbol: str, timeframe: str, strategy_id: str) -> List[Dict]:
    """
    计算历史 K线上的策略信号标记
    
    参数:
    - ohlcv: K线数据 [[ts, o, h, l, c, v], ...]
    - symbol: 交易对
    - timeframe: 时间周期
    - strategy_id: 策略ID (strategy_v1 或 strategy_v2)
    
    返回:
    - markers 列表，用于 Lightweight Charts 显示
    """
    markers = []
    
    try:
        # 动态加载策略模块
        from strategy_registry import get_strategy_registry
        registry = get_strategy_registry()
        
        # 获取策略类并实例化
        strategy_class = registry.get_strategy_class(strategy_id)
        if not strategy_class:
            print(f"[market_api] 策略 {strategy_id} 未找到")
            return markers
        
        strategy = strategy_class()
        
        # 将 OHLCV 转换为 DataFrame
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # 保存原始毫秒时间戳用于 marker 显示
        df['timestamp_ms'] = df['timestamp'].copy()
        
        # 转换 timestamp 为 datetime 类型（与 trade_engine 一致）
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # 检查数据量是否足够（统一要求 1000 条）
        min_bars = 1000
        if len(df) < min_bars:
            print(f"[market_api] K线数据不足: {len(df)} < {min_bars}，跳过信号计算")
            return markers
        
        print(f"[market_api] 开始计算策略信号 | 策略: {strategy_id} | 周期: {timeframe} | K线数: {len(df)}")
        
        # 计算技术指标
        try:
            df_with_indicators = strategy.calculate_indicators(df)
            print(f"[market_api] 指标计算完成 | 列数: {len(df_with_indicators.columns)}")
        except ValueError as e:
            print(f"[market_api] 指标计算失败: {e}")
            return markers
        
        # 遍历历史 K线，检查每根 K线的信号
        # 需要至少 200 根历史数据来计算指标（EMA 初始化）
        # 为了性能，只检查最近 200 根 K线的信号
        # 修复：start_idx 应该是 max(200, len(df) - 200)，而不是 max(1000, ...)
        # 因为我们只需要 200 根历史数据来初始化指标，然后检查后面的信号
        start_idx = max(200, len(df) - 200)
        
        # 北京时间偏移（秒）
        BEIJING_OFFSET_SEC = 8 * 3600
        
        signal_count = 0
        hold_count = 0
        error_count = 0
        
        for i in range(start_idx, len(df) - 2):
            # 00秒确认模式：策略使用 df.iloc[-2] 作为"当前K线"
            # 所以我们需要传入截止到 i+2 的数据（让 iloc[-2] 指向第 i 根）
            # 即：sub_df.iloc[-2] = df.iloc[i]，sub_df.iloc[-1] = df.iloc[i+1]
            # 需要 i+2 < len(df)，所以循环到 len(df) - 2
            sub_df = df_with_indicators.iloc[:i+3].copy()
            
            # 确保有足够的数据（至少4根K线用于 iloc[-2], [-3], [-4]）
            if len(sub_df) < 4:
                continue
            
            try:
                # 调用策略的信号检查方法
                signal = strategy.check_signals(sub_df, timeframe=timeframe)
                
                if signal and signal.get('action') in ['LONG', 'SHORT']:
                    # 修复：信号计数和 marker 创建应该在 LONG/SHORT 分支内
                    signal_count += 1
                    action = signal['action']
                    signal_type = signal.get('type', 'UNKNOWN')
                    
                    # 获取信号 K线的时间戳（第 i 根 K线，对应 sub_df.iloc[-2]）
                    ts_ms = int(df.iloc[i]['timestamp_ms'])
                    ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
                    
                    # 构造 marker
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
                elif signal and signal.get('action') == 'HOLD':
                    hold_count += 1
            except Exception as e:
                # 单根 K线计算失败，跳过
                error_count += 1
                continue
        
        print(f"[market_api] 策略 {strategy_id} 计算完成 | 信号: {signal_count} | HOLD: {hold_count} | 错误: {error_count} | markers: {len(markers)}")
        
    except Exception as e:
        # 简化错误日志
        print(f"[market_api] ⚠️ 策略信号计算失败: {str(e)[:100]}")
    
    return markers


# ============ FastAPI 应用 ============
if FASTAPI_AVAILABLE:
    import logging
    
    # 自定义日志过滤器：屏蔽 /kline 和 /ticker 的常规访问日志
    class EndpointFilter(logging.Filter):
        """过滤掉高频访问端点的 INFO 日志"""
        def filter(self, record: logging.LogRecord) -> bool:
            # 获取日志消息
            msg = record.getMessage()
            # 屏蔽 /kline 和 /ticker 的 200 OK 日志
            if any(path in msg for path in ['/kline', '/ticker']):
                if '200' in msg:  # 只屏蔽成功的请求
                    return False
            return True
    
    # 应用过滤器到 uvicorn 的 access logger
    logging.getLogger("uvicorn.access").addFilter(EndpointFilter())
    
    app = FastAPI(
        title="Market Data API",
        description="为 Streamlit UI 提供 K线数据的独立服务",
        version="1.0.0"
    )
    
    # CORS 配置（允许 Streamlit 跨域访问）
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        """健康检查"""
        return {
            "status": "ok",
            "service": "Market Data API",
            "timestamp": int(time.time() * 1000)
        }
    
    @app.get("/kline")
    async def get_kline(
        symbol: str = Query(..., description="交易对，如 BTC/USDT:USDT"),
        tf: str = Query("1m", description="时间周期，如 1m, 5m, 15m, 1h"),
        limit: int = Query(500, description="K线数量，最大1000"),
        strategy: str = Query(None, description="策略ID，如 strategy_v1, strategy_v2")
    ):
        """
        获取 K线数据（可选：附带策略信号标记）
        
        返回格式:
        {
            "symbol": "BTC/USDT:USDT",
            "timeframe": "1m",
            "data": [[timestamp, open, high, low, close, volume], ...],
            "markers": [{"time": 1700000000, "position": "belowBar", "color": "green", "shape": "arrowUp", "text": "BUY"}, ...],
            "count": 500,
            "cached": true/false,
            "timestamp": 1702800000000
        }
        """
        # 参数校验
        if limit > 1000:
            limit = 1000
        if limit < 1:
            limit = 1
        
        # 标准化 symbol 格式
        symbol = symbol.strip()
        if '/' not in symbol:
            # 自动补全格式：BTC -> BTC/USDT:USDT
            symbol = f"{symbol}/USDT:USDT"
        elif ':' not in symbol:
            # 自动补全结算货币：BTC/USDT -> BTC/USDT:USDT
            symbol = f"{symbol}:USDT"
        
        # 如果需要计算策略信号，强制拉取至少 1000 条数据
        actual_limit = limit
        if strategy:
            actual_limit = max(limit, 1000)
        
        # 检查缓存
        cached_data = cache.get(symbol, tf)
        ohlcv = None
        is_cached = False
        
        if cached_data and len(cached_data) >= actual_limit:
            ohlcv = cached_data[-actual_limit:]
            is_cached = True
        else:
            # 从交易所获取
            try:
                ohlcv = okx_client.fetch_ohlcv(symbol, tf, actual_limit)
                # 更新缓存
                cache.set(symbol, tf, ohlcv)
            except Exception as e:
                # 简化错误日志，避免打印完整堆栈
                error_msg = str(e)
                # 提取关键错误信息
                if 'NetworkError' in error_msg or 'timeout' in error_msg.lower():
                    print(f"[market_api] ⚠️ 网络错误 {symbol} {tf}: 请检查网络连接或代理设置")
                else:
                    print(f"[market_api] ⚠️ 获取K线失败 {symbol} {tf}: {error_msg[:100]}")
                raise HTTPException(status_code=500, detail=f"获取K线失败: {error_msg[:100]}")
        
        # 计算策略信号标记（需要至少 1000 条数据）
        markers = []
        if strategy and ohlcv and len(ohlcv) >= 1000:
            markers = _calculate_strategy_markers(ohlcv, symbol, tf, strategy)
        
        return {
            "symbol": symbol,
            "timeframe": tf,
            "data": ohlcv,
            "markers": markers,
            "count": len(ohlcv) if ohlcv else 0,
            "cached": is_cached,
            "timestamp": int(time.time() * 1000)
        }
    
    @app.get("/ticker")
    async def get_ticker(
        symbol: str = Query(..., description="交易对，如 BTC/USDT:USDT")
    ):
        """
        获取实时行情
        
        返回格式:
        {
            "symbol": "BTC/USDT:USDT",
            "last": 45000.0,
            "bid": 44999.0,
            "ask": 45001.0,
            "timestamp": 1702800000000
        }
        """
        # 标准化 symbol 格式
        symbol = symbol.strip()
        if '/' not in symbol:
            symbol = f"{symbol}/USDT:USDT"
        elif ':' not in symbol:
            symbol = f"{symbol}:USDT"
        
        try:
            if not okx_client.exchange:
                raise Exception("交易所未连接")
            
            ticker = okx_client.exchange.fetch_ticker(symbol)
            
            return {
                "symbol": symbol,
                "last": ticker.get('last'),
                "bid": ticker.get('bid'),
                "ask": ticker.get('ask'),
                "high": ticker.get('high'),
                "low": ticker.get('low'),
                "volume": ticker.get('baseVolume'),
                "timestamp": int(time.time() * 1000)
            }
        except Exception as e:
            error_msg = str(e)
            if 'NetworkError' in error_msg or 'timeout' in error_msg.lower():
                print(f"[market_api] ⚠️ 网络错误 {symbol}: 请检查网络连接或代理设置")
            else:
                print(f"[market_api] ⚠️ 获取Ticker失败 {symbol}: {error_msg[:100]}")
            raise HTTPException(status_code=500, detail=f"获取Ticker失败: {error_msg[:100]}")
    
    @app.get("/symbols")
    async def get_symbols(top: int = Query(100, description="返回成交量前N的币种")):
        """
        获取成交量前N的交易对列表（实时从交易所获取）
        
        返回按24h成交量降序排列的永续合约交易对
        """
        try:
            if not okx_client.exchange:
                raise Exception("交易所未连接")
            
            # 获取所有永续合约的 tickers
            tickers = okx_client.exchange.fetch_tickers()
            
            # 筛选 USDT 永续合约并按成交量排序
            usdt_swaps = []
            for symbol, ticker in tickers.items():
                # 只要 USDT 永续合约
                if ':USDT' in symbol and '/USDT' in symbol:
                    volume = ticker.get('quoteVolume', 0) or 0  # 24h USDT 成交额
                    usdt_swaps.append({
                        'symbol': symbol,
                        'volume': volume,
                        'last': ticker.get('last', 0)
                    })
            
            # 按成交量降序排序
            usdt_swaps.sort(key=lambda x: x['volume'], reverse=True)
            
            # 取前 N 个
            top_symbols = [item['symbol'] for item in usdt_swaps[:top]]
            
            return {
                "symbols": top_symbols,
                "count": len(top_symbols),
                "total_available": len(usdt_swaps),
                "timestamp": int(time.time() * 1000)
            }
        except Exception as e:
            print(f"[market_api] 获取交易对列表失败: {e}")
            # 回退到静态列表
            fallback = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT", 
                       "DOGE/USDT:USDT", "XRP/USDT:USDT"]
            return {
                "symbols": fallback,
                "count": len(fallback),
                "error": str(e)[:100],
                "timestamp": int(time.time() * 1000)
            }


# ============ 主入口 ============
if __name__ == "__main__":
    if not FASTAPI_AVAILABLE:
        print("❌ 请先安装 FastAPI: pip install fastapi uvicorn")
        exit(1)
    
    print("=" * 60)
    print("🚀 Market Data API 启动中...")
    print("=" * 60)
    print(f"🌐 服务地址: http://127.0.0.1:8000")
    print(f"📖 API 文档: http://127.0.0.1:8000/docs")
    print(f"⏱️ 缓存 TTL: 2 秒")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
