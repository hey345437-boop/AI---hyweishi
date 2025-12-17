# symbol_utils.py
# 交易对符号规范化工具

import re
from typing import Optional, List, Tuple, Set

# 统一输出格式: CCXT swap 统一 symbol，如 "BTC/USDT:USDT"
# 这是 ccxt 对 OKX 永续合约的标准格式

# 🔥 动态白名单：从 Market API 获取成交量前100的币种
# 缓存机制：避免频繁请求
import time
import requests
import os

_WHITELIST_CACHE: Set[str] = set()
_WHITELIST_CACHE_TIME: float = 0
_WHITELIST_CACHE_TTL: int = 300  # 缓存5分钟

MARKET_API_URL = os.getenv("MARKET_API_URL", "http://127.0.0.1:8000")

def _fetch_dynamic_whitelist() -> Set[str]:
    """从 Market API 获取成交量前100的币种"""
    global _WHITELIST_CACHE, _WHITELIST_CACHE_TIME
    
    now = time.time()
    
    # 检查缓存是否有效
    if _WHITELIST_CACHE and (now - _WHITELIST_CACHE_TIME) < _WHITELIST_CACHE_TTL:
        return _WHITELIST_CACHE
    
    try:
        response = requests.get(f"{MARKET_API_URL}/symbols?top=100", timeout=10)
        if response.status_code == 200:
            data = response.json()
            symbols = data.get('symbols', [])
            # 提取 base currency (如 "BTC/USDT:USDT" -> "BTC")
            whitelist = set()
            for sym in symbols:
                if '/' in sym:
                    base = sym.split('/')[0]
                    whitelist.add(base.upper())
            
            if whitelist:
                _WHITELIST_CACHE = whitelist
                _WHITELIST_CACHE_TIME = now
                return whitelist
    except Exception:
        pass
    
    # 回退到静态白名单
    return {
        "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "LINK", "MATIC",
        "LTC", "BCH", "UNI", "ATOM", "ETC", "XLM", "FIL", "APT", "ARB", "OP"
    }

# 兼容旧代码的静态白名单（回退用）
SYMBOL_WHITELIST: Set[str] = {
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "DOT", "LINK", "MATIC",
    "LTC", "BCH", "UNI", "ATOM", "ETC", "XLM", "FIL", "APT", "ARB", "OP"
}

def is_symbol_whitelisted(base_currency: str) -> bool:
    """检查币种是否在白名单中（动态获取）"""
    whitelist = _fetch_dynamic_whitelist()
    return base_currency.upper() in whitelist

def get_whitelist() -> Set[str]:
    """获取当前白名单"""
    return _fetch_dynamic_whitelist()

def normalize_symbol(raw: str, market_type: str = 'swap', quote: str = 'USDT') -> str:
    """
    将任意格式的交易对符号规范化为 CCXT swap 统一格式
    
    支持的输入格式:
    - "btc" / "BTC" / " btc "
    - "BTCUSDT" / "BTC-USDT"
    - "BTC/USDT"
    - "BTC/USDT:USDT" (ccxt swap 统一格式)
    - "BTC-USDT-SWAP" (OKX instId)
    
    输出格式: "BTC/USDT:USDT" (CCXT swap 统一格式)
    
    Args:
        raw: 原始输入字符串
        market_type: 市场类型，默认 'swap' (永续合约)
        quote: 计价货币，默认 'USDT'
    
    Returns:
        规范化后的 symbol，如 "BTC/USDT:USDT"
    """
    if not raw or not isinstance(raw, str):
        return ""
    
    # 清理输入：去除空白、转大写
    symbol = raw.strip().upper()
    
    if not symbol:
        return ""
    
    # 移除可能的斜杠前缀
    if symbol.startswith("/"):
        symbol = symbol[1:]
    
    # 情况1: 已经是 CCXT swap 格式 "BTC/USDT:USDT"
    if "/" in symbol and ":" in symbol:
        # 验证格式正确性
        parts = symbol.split(":")
        if len(parts) == 2:
            base_quote = parts[0]
            settle = parts[1]
            if "/" in base_quote:
                return symbol  # 已经是正确格式
    
    # 情况2: OKX instId 格式 "BTC-USDT-SWAP"
    if "-SWAP" in symbol:
        # 移除 -SWAP 后缀
        symbol = symbol.replace("-SWAP", "")
        # 继续处理 "BTC-USDT" 格式
    
    # 情况3: 带分隔符的格式 "BTC-USDT" 或 "BTC/USDT"
    if "-" in symbol:
        parts = symbol.split("-")
        if len(parts) >= 2:
            base = parts[0]
            quote_part = parts[1]
            return f"{base}/{quote_part}:{quote_part}"
    
    if "/" in symbol:
        parts = symbol.split("/")
        if len(parts) >= 2:
            base = parts[0]
            quote_part = parts[1]
            return f"{base}/{quote_part}:{quote_part}"
    
    # 情况4: 连续格式 "BTCUSDT"
    # 尝试识别常见的计价货币后缀
    quote_currencies = ["USDT", "USDC", "USD", "BUSD", "BTC", "ETH"]
    for qc in quote_currencies:
        if symbol.endswith(qc) and len(symbol) > len(qc):
            base = symbol[:-len(qc)]
            return f"{base}/{qc}:{qc}"
    
    # 情况5: 只有基础货币 "BTC"
    # 使用默认计价货币
    return f"{symbol}/{quote}:{quote}"


def normalize_symbol_list(raw_list: List[str], market_type: str = 'swap', quote: str = 'USDT') -> List[str]:
    """
    批量规范化交易对列表
    
    Args:
        raw_list: 原始交易对列表
        market_type: 市场类型
        quote: 计价货币
    
    Returns:
        规范化后的交易对列表（去重、去空）
    """
    result = []
    seen = set()
    
    for raw in raw_list:
        normalized = normalize_symbol(raw, market_type, quote)
        if normalized and normalized not in seen:
            result.append(normalized)
            seen.add(normalized)
    
    return result


def parse_symbol_input(text: str, market_type: str = 'swap', quote: str = 'USDT') -> List[str]:
    """
    解析多行文本输入为规范化的交易对列表
    
    支持:
    - 每行一个交易对
    - 逗号分隔
    - 空格分隔
    
    Args:
        text: 多行文本输入
        market_type: 市场类型
        quote: 计价货币
    
    Returns:
        规范化后的交易对列表
    """
    if not text:
        return []
    
    # 分割：支持换行、逗号、空格
    raw_symbols = re.split(r'[\n,\s]+', text)
    
    # 过滤空字符串并规范化
    return normalize_symbol_list([s for s in raw_symbols if s.strip()], market_type, quote)


def to_okx_inst_id(ccxt_symbol: str) -> str:
    """
    将 CCXT 格式转换为 OKX instId 格式
    
    "BTC/USDT:USDT" -> "BTC-USDT-SWAP"
    
    Args:
        ccxt_symbol: CCXT 格式的 symbol
    
    Returns:
        OKX instId 格式
    """
    if not ccxt_symbol:
        return ""
    
    # 移除结算货币部分
    if ":" in ccxt_symbol:
        ccxt_symbol = ccxt_symbol.split(":")[0]
    
    # 替换分隔符
    if "/" in ccxt_symbol:
        parts = ccxt_symbol.split("/")
        if len(parts) == 2:
            return f"{parts[0]}-{parts[1]}-SWAP"
    
    return ccxt_symbol


def from_okx_inst_id(inst_id: str) -> str:
    """
    将 OKX instId 格式转换为 CCXT 格式
    
    "BTC-USDT-SWAP" -> "BTC/USDT:USDT"
    
    Args:
        inst_id: OKX instId 格式
    
    Returns:
        CCXT 格式的 symbol
    """
    return normalize_symbol(inst_id)


# ============ 单元测试 ============
def test_normalize_symbol():
    """测试 normalize_symbol 函数"""
    test_cases = [
        # (输入, 期望输出)
        ("btc", "BTC/USDT:USDT"),
        ("BTC", "BTC/USDT:USDT"),
        (" btc ", "BTC/USDT:USDT"),
        ("BTCUSDT", "BTC/USDT:USDT"),
        ("BTC-USDT", "BTC/USDT:USDT"),
        ("BTC/USDT", "BTC/USDT:USDT"),
        ("BTC/USDT:USDT", "BTC/USDT:USDT"),
        ("BTC-USDT-SWAP", "BTC/USDT:USDT"),
        ("eth", "ETH/USDT:USDT"),
        ("ETHUSDT", "ETH/USDT:USDT"),
        ("ETH-USDT", "ETH/USDT:USDT"),
        ("ETH/USDT", "ETH/USDT:USDT"),
        ("ETH/USDT:USDT", "ETH/USDT:USDT"),
        ("ETH-USDT-SWAP", "ETH/USDT:USDT"),
        ("sol", "SOL/USDT:USDT"),
        ("SOLUSDT", "SOL/USDT:USDT"),
        ("SOL-USDT", "SOL/USDT:USDT"),
        ("SOL/USDT", "SOL/USDT:USDT"),
        ("xrp", "XRP/USDT:USDT"),
        ("XRPUSDT", "XRP/USDT:USDT"),
        ("doge", "DOGE/USDT:USDT"),
        ("DOGEUSDT", "DOGE/USDT:USDT"),
        # 边界情况
        ("", ""),
        ("  ", ""),
        (None, ""),
    ]
    
    passed = 0
    failed = 0
    
    for raw, expected in test_cases:
        result = normalize_symbol(raw)
        if result == expected:
            passed += 1
            print(f"✅ PASS: normalize_symbol({repr(raw)}) = {repr(result)}")
        else:
            failed += 1
            print(f"❌ FAIL: normalize_symbol({repr(raw)}) = {repr(result)}, expected {repr(expected)}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


def test_parse_symbol_input():
    """测试 parse_symbol_input 函数"""
    test_cases = [
        # (输入, 期望输出)
        ("btc\neth\nsol", ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]),
        ("BTC, ETH, SOL", ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]),
        ("BTCUSDT ETHUSDT", ["BTC/USDT:USDT", "ETH/USDT:USDT"]),
        ("BTC/USDT:USDT\nETH/USDT:USDT", ["BTC/USDT:USDT", "ETH/USDT:USDT"]),
        # 去重
        ("btc\nBTC\nBTCUSDT", ["BTC/USDT:USDT"]),
    ]
    
    passed = 0
    failed = 0
    
    for raw, expected in test_cases:
        result = parse_symbol_input(raw)
        if result == expected:
            passed += 1
            print(f"✅ PASS: parse_symbol_input({repr(raw)[:30]}...) = {result}")
        else:
            failed += 1
            print(f"❌ FAIL: parse_symbol_input({repr(raw)[:30]}...) = {result}, expected {expected}")
    
    print(f"\n总计: {passed} 通过, {failed} 失败")
    return failed == 0


if __name__ == "__main__":
    print("=" * 60)
    print("测试 normalize_symbol")
    print("=" * 60)
    test_normalize_symbol()
    
    print("\n" + "=" * 60)
    print("测试 parse_symbol_input")
    print("=" * 60)
    test_parse_symbol_input()
