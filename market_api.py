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
    """OKX 交易所客户端（只读，用于获取行情）"""
    
    def __init__(self):
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            # 从环境变量读取 API 密钥（可选，公开行情不需要）
            api_key = os.getenv("OKX_API_KEY", "")
            api_secret = os.getenv("OKX_API_SECRET", "")
            api_passphrase = os.getenv("OKX_API_PASSPHRASE", "")
            
            # 获取代理配置
            http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
            https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            
            config = {
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # 永续合约
                }
            }
            
            # 🔥 添加代理支持
            if https_proxy:
                config['proxies'] = {
                    'http': http_proxy or https_proxy,
                    'https': https_proxy
                }
                print(f"📡 使用代理: {https_proxy}")
            
            # 如果有 API 密钥，添加认证
            if api_key and api_secret and api_passphrase:
                config['apiKey'] = api_key
                config['secret'] = api_secret
                config['password'] = api_passphrase
            
            self.exchange = ccxt.okx(config)
            print("✅ OKX 交易所连接初始化成功")
        except Exception as e:
            print(f"❌ OKX 交易所连接失败: {e}")
            self.exchange = None
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = '1m', limit: int = 500) -> List[List]:
        """
        获取 K线数据
        
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
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            raise Exception(f"获取K线失败: {e}")


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
        
        # 检查数据量是否足够
        min_bars = 200 if strategy_id == 'strategy_v1' else 1000
        if len(df) < min_bars:
            print(f"[market_api] K线数据不足: {len(df)} < {min_bars}，跳过信号计算")
            return markers
        
        # 计算技术指标
        try:
            df_with_indicators = strategy.calculate_indicators(df)
        except ValueError as e:
            print(f"[market_api] 指标计算失败: {e}")
            return markers
        
        # 🔥 遍历历史 K线，检查每根 K线的信号
        # 从第 min_bars 根开始（确保有足够的历史数据计算指标）
        # 为了性能，只检查最近 200 根 K线的信号
        start_idx = max(min_bars, len(df) - 200)
        
        # 北京时间偏移（秒）
        BEIJING_OFFSET_SEC = 8 * 3600
        
        for i in range(start_idx, len(df) - 1):
            # 构造截止到当前 K线的子 DataFrame
            # 策略的 check_signals 使用 df.iloc[-1] 和 df.iloc[-2]
            # 所以我们需要传入截止到 i+1 的数据（让 iloc[-1] 指向第 i 根）
            sub_df = df_with_indicators.iloc[:i+2].copy()
            
            try:
                # 调用策略的信号检查方法
                signal = strategy.check_signals(sub_df, timeframe=timeframe)
                
                if signal and signal.get('action') in ['LONG', 'SHORT']:
                    action = signal['action']
                    signal_type = signal.get('type', 'UNKNOWN')
                    reason = signal.get('reason', '')
                    
                    # 获取信号 K线的时间戳（第 i 根 K线）
                    ts_ms = int(df.iloc[i]['timestamp'])
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
            except Exception as e:
                # 单根 K线计算失败，跳过
                continue
        
        print(f"[market_api] 策略 {strategy_id} 计算完成，发现 {len(markers)} 个信号")
        
    except Exception as e:
        print(f"[market_api] 策略信号计算失败: {e}")
        traceback.print_exc()
    
    return markers


# ============ FastAPI 应用 ============
if FASTAPI_AVAILABLE:
    import logging
    
    # 🔥 自定义日志过滤器：屏蔽 /kline 和 /ticker 的常规访问日志
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
        
        # 检查缓存
        cached_data = cache.get(symbol, tf)
        ohlcv = None
        is_cached = False
        
        if cached_data:
            ohlcv = cached_data[-limit:]
            is_cached = True
        else:
            # 从交易所获取
            try:
                ohlcv = okx_client.fetch_ohlcv(symbol, tf, limit)
                # 更新缓存
                cache.set(symbol, tf, ohlcv)
            except Exception as e:
                print(f"[market_api] 获取K线失败 symbol={symbol} tf={tf} limit={limit}: {e}")
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=str(e))
        
        # 🔥 计算策略信号标记
        markers = []
        if strategy and ohlcv and len(ohlcv) > 200:
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
            print(f"[market_api] 获取Ticker失败 symbol={symbol}: {e}")
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/symbols")
    async def get_symbols():
        """
        获取支持的交易对列表
        """
        # 常用交易对
        common_symbols = [
            "BTC/USDT:USDT",
            "ETH/USDT:USDT",
            "SOL/USDT:USDT",
            "DOGE/USDT:USDT",
            "XRP/USDT:USDT",
            "BNB/USDT:USDT",
            "ADA/USDT:USDT",
            "AVAX/USDT:USDT",
            "DOT/USDT:USDT",
            "MATIC/USDT:USDT",
        ]
        
        return {
            "symbols": common_symbols,
            "count": len(common_symbols),
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
    print(f"📡 服务地址: http://127.0.0.1:8000")
    print(f"📖 API 文档: http://127.0.0.1:8000/docs")
    print(f"⏱️ 缓存 TTL: 2 秒")
    print("=" * 60)
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
