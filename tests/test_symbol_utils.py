# tests/test_symbol_utils.py
# Symbol 规范化工具的 pytest 测试

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from symbol_utils import normalize_symbol, parse_symbol_input, to_okx_inst_id, from_okx_inst_id


class TestNormalizeSymbol:
    """测试 normalize_symbol 函数"""
    
    @pytest.mark.parametrize("raw,expected", [
        # 基础货币名称
        ("btc", "BTC/USDT:USDT"),
        ("BTC", "BTC/USDT:USDT"),
        (" btc ", "BTC/USDT:USDT"),
        ("eth", "ETH/USDT:USDT"),
        ("sol", "SOL/USDT:USDT"),
        ("xrp", "XRP/USDT:USDT"),
        ("doge", "DOGE/USDT:USDT"),
        
        # 连续格式
        ("BTCUSDT", "BTC/USDT:USDT"),
        ("ETHUSDT", "ETH/USDT:USDT"),
        ("SOLUSDT", "SOL/USDT:USDT"),
        ("DOGEUSDT", "DOGE/USDT:USDT"),
        
        # 带分隔符格式
        ("BTC-USDT", "BTC/USDT:USDT"),
        ("ETH-USDT", "ETH/USDT:USDT"),
        ("BTC/USDT", "BTC/USDT:USDT"),
        ("ETH/USDT", "ETH/USDT:USDT"),
        
        # CCXT swap 格式（已规范化）
        ("BTC/USDT:USDT", "BTC/USDT:USDT"),
        ("ETH/USDT:USDT", "ETH/USDT:USDT"),
        
        # OKX instId 格式
        ("BTC-USDT-SWAP", "BTC/USDT:USDT"),
        ("ETH-USDT-SWAP", "ETH/USDT:USDT"),
        ("SOL-USDT-SWAP", "SOL/USDT:USDT"),
        
        # 边界情况
        ("", ""),
        ("  ", ""),
    ])
    def test_normalize_symbol(self, raw, expected):
        """测试各种输入格式的规范化"""
        assert normalize_symbol(raw) == expected
    
    def test_normalize_symbol_none(self):
        """测试 None 输入"""
        assert normalize_symbol(None) == ""
    
    def test_normalize_symbol_case_insensitive(self):
        """测试大小写不敏感"""
        assert normalize_symbol("btc") == normalize_symbol("BTC")
        assert normalize_symbol("Btc") == normalize_symbol("BTC")


class TestParseSymbolInput:
    """测试 parse_symbol_input 函数"""
    
    def test_newline_separated(self):
        """测试换行分隔"""
        result = parse_symbol_input("btc\neth\nsol")
        assert result == ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    
    def test_comma_separated(self):
        """测试逗号分隔"""
        result = parse_symbol_input("BTC, ETH, SOL")
        assert result == ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    
    def test_space_separated(self):
        """测试空格分隔"""
        result = parse_symbol_input("BTCUSDT ETHUSDT")
        assert result == ["BTC/USDT:USDT", "ETH/USDT:USDT"]
    
    def test_deduplication(self):
        """测试去重"""
        result = parse_symbol_input("btc\nBTC\nBTCUSDT")
        assert result == ["BTC/USDT:USDT"]
    
    def test_empty_input(self):
        """测试空输入"""
        assert parse_symbol_input("") == []
        assert parse_symbol_input("   ") == []
    
    def test_mixed_formats(self):
        """测试混合格式"""
        result = parse_symbol_input("btc, ETH-USDT\nSOL/USDT:USDT")
        assert result == ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


class TestOkxConversion:
    """测试 OKX 格式转换"""
    
    def test_to_okx_inst_id(self):
        """测试转换为 OKX instId"""
        assert to_okx_inst_id("BTC/USDT:USDT") == "BTC-USDT-SWAP"
        assert to_okx_inst_id("ETH/USDT:USDT") == "ETH-USDT-SWAP"
    
    def test_from_okx_inst_id(self):
        """测试从 OKX instId 转换"""
        assert from_okx_inst_id("BTC-USDT-SWAP") == "BTC/USDT:USDT"
        assert from_okx_inst_id("ETH-USDT-SWAP") == "ETH/USDT:USDT"
    
    def test_round_trip(self):
        """测试往返转换"""
        original = "BTC/USDT:USDT"
        okx_id = to_okx_inst_id(original)
        back = from_okx_inst_id(okx_id)
        assert back == original


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
