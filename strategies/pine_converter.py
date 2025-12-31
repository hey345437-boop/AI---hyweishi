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
Pine Script 到 Python 转换器

将 TradingView Pine Script 代码转换为系统策略格式
"""
import re
from typing import Dict, Any, List, Tuple


class PineConverter:
    """Pine Script 到 Python 转换器"""
    
    # Pine Script 函数映射表
    FUNCTION_MAP = {
        "ta.ema": ("ta.ema", "close, length={0}"),
        "ta.sma": ("ta.sma", "close, length={0}"),
        "ta.rsi": ("ta.rsi", "close, length={0}"),
        "ta.macd": ("ta.macd", "close, fast={0}, slow={1}, signal={2}"),
        "ta.atr": ("ta.atr", "high, low, close, length={0}"),
        "ta.stoch": ("ta.stoch", "high, low, close, k={0}, d={1}"),
        "ta.bbands": ("ta.bbands", "close, length={0}, std={1}"),
        "ta.adx": ("ta.adx", "high, low, close, length={0}"),
    }
    
    # 需要特殊处理的函数
    SPECIAL_FUNCTIONS = ["ta.crossover", "ta.crossunder"]
    
    def __init__(self):
        self.unsupported = []
        self.variables = {}
    
    def convert(self, pine_code: str) -> Dict[str, Any]:
        """
        转换 Pine Script 为 Python
        
        Args:
            pine_code: Pine Script 代码
        
        Returns:
            {"success": True, "code": "...", "unsupported": []} 或
            {"success": False, "error": "...", "unsupported": [...]}
        """
        self.unsupported = []
        self.variables = {}
        
        try:
            # 1. 解析 Pine Script
            parsed = self._parse_pine(pine_code)
            
            # 2. 生成 Python 代码
            python_code = self._generate_python(parsed, pine_code)
            
            return {
                "success": len(self.unsupported) == 0,
                "code": python_code,
                "unsupported": self.unsupported
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "unsupported": self.unsupported
            }

    def _parse_pine(self, pine_code: str) -> Dict[str, Any]:
        """解析 Pine Script 代码"""
        result = {
            "strategy_name": "ConvertedStrategy",
            "indicators": [],
            "conditions": [],
            "entries": []
        }
        
        lines = pine_code.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('//'):
                continue
            
            # 解析策略名称
            if 'strategy(' in line or 'indicator(' in line:
                name_match = re.search(r'["\']([^"\']+)["\']', line)
                if name_match:
                    result["strategy_name"] = self._to_class_name(name_match.group(1))
            
            # 解析变量赋值（指标计算）
            elif '=' in line and not line.startswith('if'):
                var_match = re.match(r'(\w+)\s*=\s*(.+)', line)
                if var_match:
                    var_name = var_match.group(1)
                    expression = var_match.group(2)
                    indicator = self._parse_indicator(var_name, expression)
                    if indicator:
                        result["indicators"].append(indicator)
                        self.variables[var_name] = indicator
            
            # 解析条件
            elif 'Condition' in line or 'condition' in line:
                cond_match = re.match(r'(\w+)\s*=\s*(.+)', line)
                if cond_match:
                    result["conditions"].append({
                        "name": cond_match.group(1),
                        "expression": cond_match.group(2)
                    })
            
            # 解析入场信号
            elif 'strategy.entry' in line:
                entry = self._parse_entry(line)
                if entry:
                    result["entries"].append(entry)
        
        return result
    
    def _parse_indicator(self, var_name: str, expression: str) -> Dict[str, Any]:
        """解析指标表达式"""
        for pine_func, (py_func, py_args) in self.FUNCTION_MAP.items():
            if pine_func in expression:
                # 提取参数
                args_match = re.search(rf'{re.escape(pine_func)}\s*\(([^)]+)\)', expression)
                if args_match:
                    args = [a.strip() for a in args_match.group(1).split(',')]
                    return {
                        "var_name": var_name,
                        "pine_func": pine_func,
                        "py_func": py_func,
                        "args": args
                    }
        
        # 检查特殊函数
        for func in self.SPECIAL_FUNCTIONS:
            if func in expression:
                args_match = re.search(rf'{re.escape(func)}\s*\(([^)]+)\)', expression)
                if args_match:
                    args = [a.strip() for a in args_match.group(1).split(',')]
                    return {
                        "var_name": var_name,
                        "pine_func": func,
                        "py_func": "_crossover" if "crossover" in func else "_crossunder",
                        "args": args,
                        "is_special": True
                    }
        
        # 检查未支持的函数
        func_match = re.search(r'(ta\.\w+)', expression)
        if func_match and func_match.group(1) not in self.FUNCTION_MAP:
            if func_match.group(1) not in self.unsupported:
                self.unsupported.append(func_match.group(1))
        
        return None
    
    def _parse_entry(self, line: str) -> Dict[str, Any]:
        """解析入场信号"""
        # strategy.entry("Long", strategy.long)
        match = re.search(r'strategy\.entry\s*\(\s*["\'](\w+)["\'].*?(strategy\.long|strategy\.short)', line)
        if match:
            return {
                "name": match.group(1),
                "direction": "long" if "long" in match.group(2) else "short"
            }
        return None
    
    def _to_class_name(self, name: str) -> str:
        """转换为类名格式"""
        # 移除特殊字符，转为 PascalCase
        words = re.split(r'[\s_\-]+', name)
        return ''.join(word.capitalize() for word in words if word) + 'Strategy'

    def _generate_python(self, parsed: Dict[str, Any], original_pine: str) -> str:
        """生成 Python 代码"""
        class_name = parsed.get("strategy_name", "ConvertedStrategy")
        
        # 生成指标代码
        indicator_lines = []
        for ind in parsed.get("indicators", []):
            py_line = self._generate_indicator_line(ind)
            if py_line:
                indicator_lines.append(py_line)
        
        indicator_code = '\n'.join(f'        {line}' for line in indicator_lines) if indicator_lines else '        pass  # 添加指标计算'
        
        # 生成信号逻辑
        signal_code = self._generate_signal_logic(parsed)
        
        # 原始 Pine Script 作为注释
        pine_comment = '\n'.join(f'# {line}' for line in original_pine.split('\n')[:30])
        
        code = f'''"""
转换自 Pine Script 的策略

原始代码：
{pine_comment}
"""


def _crossover(series1, series2):
    """判断 series1 是否上穿 series2"""
    if len(series1) < 2 or len(series2) < 2:
        return False
    return series1.iloc[-2] <= series2.iloc[-2] and series1.iloc[-1] > series2.iloc[-1]


def _crossunder(series1, series2):
    """判断 series1 是否下穿 series2"""
    if len(series1) < 2 or len(series2) < 2:
        return False
    return series1.iloc[-2] >= series2.iloc[-2] and series1.iloc[-1] < series2.iloc[-1]


class {class_name}:
    """从 Pine Script 转换的策略"""
    
    def __init__(self, config=None):
        self.config = config or {{}}
    
    def analyze(self, ohlcv, symbol):
        """分析K线数据，返回交易信号"""
        import pandas_ta as ta
        
        if ohlcv is None or len(ohlcv) < 30:
            return {{"signal": "wait", "confidence": 0, "reason": "数据不足"}}
        
        close = ohlcv['close']
        high = ohlcv['high']
        low = ohlcv['low']
        
        # 计算指标
{indicator_code}
        
        # 信号逻辑
{signal_code}
        
        return {{
            "signal": signal,
            "confidence": confidence,
            "reason": reason
        }}
    
    def get_position_size(self, symbol, signal, account_equity):
        """计算仓位大小"""
        return account_equity * 0.1
'''
        return code

    def _generate_indicator_line(self, indicator: Dict[str, Any]) -> str:
        """生成单个指标的 Python 代码"""
        var_name = indicator.get("var_name")
        py_func = indicator.get("py_func")
        args = indicator.get("args", [])
        
        if indicator.get("is_special"):
            # crossover/crossunder 特殊处理
            if len(args) >= 2:
                return f'{var_name} = {py_func}({args[0]}, {args[1]})'
            return None
        
        # 标准指标
        if py_func == "ta.ema" and len(args) >= 2:
            return f'{var_name} = ta.ema(close, length={args[1]})'
        elif py_func == "ta.sma" and len(args) >= 2:
            return f'{var_name} = ta.sma(close, length={args[1]})'
        elif py_func == "ta.rsi" and len(args) >= 2:
            return f'{var_name} = ta.rsi(close, length={args[1]})'
        elif py_func == "ta.macd":
            fast = args[1] if len(args) > 1 else "12"
            slow = args[2] if len(args) > 2 else "26"
            signal = args[3] if len(args) > 3 else "9"
            return f'{var_name} = ta.macd(close, fast={fast}, slow={slow}, signal={signal})'
        elif py_func == "ta.atr" and len(args) >= 2:
            return f'{var_name} = ta.atr(high, low, close, length={args[1]})'
        elif py_func == "ta.bbands" and len(args) >= 2:
            length = args[1] if len(args) > 1 else "20"
            std = args[2] if len(args) > 2 else "2"
            return f'{var_name} = ta.bbands(close, length={length}, std={std})'
        
        return None
    
    def _generate_signal_logic(self, parsed: Dict[str, Any]) -> str:
        """生成信号逻辑代码"""
        entries = parsed.get("entries", [])
        indicators = parsed.get("indicators", [])
        
        # 检查是否有 crossover/crossunder
        has_crossover = any(ind.get("pine_func") == "ta.crossover" for ind in indicators)
        has_crossunder = any(ind.get("pine_func") == "ta.crossunder" for ind in indicators)
        
        if has_crossover or has_crossunder:
            # 使用交叉信号
            crossover_var = next((ind["var_name"] for ind in indicators if ind.get("pine_func") == "ta.crossover"), None)
            crossunder_var = next((ind["var_name"] for ind in indicators if ind.get("pine_func") == "ta.crossunder"), None)
            
            code = '''        signal = "wait"
        confidence = 0
        reason = ""
        '''
            
            if crossover_var:
                code += f'''
        if {crossover_var}:
            signal = "open_long"
            confidence = 70
            reason = "金叉信号"
        '''
            
            if crossunder_var:
                code += f'''
        elif {crossunder_var}:
            signal = "open_short"
            confidence = 70
            reason = "死叉信号"
        '''
            
            return code
        
        # 默认信号逻辑
        return '''        signal = "wait"
        confidence = 0
        reason = ""
        
        # TODO: 根据指标添加信号逻辑
        '''
