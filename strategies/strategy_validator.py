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
策略代码验证器

验证用户提交的策略代码是否符合系统要求，并支持自动转换
"""
import ast
import re
from typing import Dict, List, Any, Optional


class StrategyValidator:
    """策略代码验证器"""
    
    REQUIRED_METHODS = ["analyze"]
    # 高级策略模板的必需方法
    ADVANCED_REQUIRED_METHODS = ["check_entry_signal"]
    # 传统引擎格式（推荐）
    VALID_ACTIONS = ["LONG", "SHORT", "HOLD", "CLOSE_LONG", "CLOSE_SHORT"]
    # 简化格式（兼容）
    VALID_SIGNALS = ["open_long", "open_short", "close_long", "close_short", "wait"]
    # 旧格式信号（兼容）
    LEGACY_SIGNALS = ["BUY", "SELL"]
    
    # 信号映射表
    SIGNAL_TO_ACTION = {
        "open_long": "LONG",
        "open_short": "SHORT",
        "close_long": "CLOSE_LONG",
        "close_short": "CLOSE_SHORT",
        "wait": "HOLD",
        "BUY": "LONG",
        "SELL": "SHORT",
        "HOLD": "HOLD",
        "buy": "LONG",
        "sell": "SHORT",
        "hold": "HOLD",
        "long": "LONG",
        "short": "SHORT",
    }
    
    def validate(self, code: str) -> Dict[str, Any]:
        """
        验证策略代码
        
        Args:
            code: Python 策略代码字符串
        
        Returns:
            {
                "valid": bool,
                "errors": List[str],
                "warnings": List[str],
                "info": List[str],
                "can_convert": bool,  # 是否可以自动转换
                "class_name": str,
                "is_advanced": bool  # 是否是高级策略模板
            }
        """
        errors = []
        warnings = []
        info = []
        can_convert = False
        is_advanced = False
        
        # 1. 语法检查
        syntax_ok, syntax_error = self._check_syntax(code)
        if not syntax_ok:
            errors.append(f"语法错误: {syntax_error}")
            return {"valid": False, "errors": errors, "warnings": warnings, "info": info, "can_convert": False, "is_advanced": False}
        
        # 2. 解析 AST
        try:
            tree = ast.parse(code)
        except Exception as e:
            errors.append(f"解析失败: {str(e)}")
            return {"valid": False, "errors": errors, "warnings": warnings, "info": info, "can_convert": False, "is_advanced": False}
        
        # 3. 查找类定义
        classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
        if not classes:
            errors.append("未找到策略类定义（需要一个 class）")
            return {"valid": False, "errors": errors, "warnings": warnings, "info": info, "can_convert": False, "is_advanced": False}
        
        # 4. 检测是否是高级策略模板
        is_advanced = self._is_advanced_strategy(code, classes)
        
        # 5. 检查必需方法
        strategy_class = classes[0]
        class_name = strategy_class.name
        methods = {node.name for node in strategy_class.body if isinstance(node, ast.FunctionDef)}
        
        if is_advanced:
            # 高级策略模板：检查 check_entry_signal 或继承自 AdvancedStrategyBase
            info.append("✓ 检测到高级策略模板（支持动态止盈止损）")
            
            # 检查是否有 Wrapper 类（兼容传统引擎）
            wrapper_classes = [c for c in classes if 'Wrapper' in c.name]
            if wrapper_classes:
                wrapper_methods = {node.name for node in wrapper_classes[0].body if isinstance(node, ast.FunctionDef)}
                if 'analyze' in wrapper_methods:
                    info.append("✓ 包含 Wrapper 类，兼容传统引擎")
                else:
                    warnings.append("Wrapper 类缺少 analyze 方法")
            else:
                # 检查主类是否有 analyze 方法（可能继承自基类）
                if 'analyze' not in methods and 'check_entry_signal' not in methods:
                    warnings.append("高级策略需要实现 check_entry_signal() 方法")
        else:
            # 传统策略：检查 analyze 方法
            for method in self.REQUIRED_METHODS:
                if method not in methods:
                    errors.append(f"缺少必需方法: {method}(self, ohlcv, symbol)")
        
        # 6. 检查 __init__ 方法（警告级别）
        if "__init__" not in methods:
            warnings.append("建议添加 __init__(self, config=None) 方法")
        
        # 7. 检查返回值格式（仅对非高级策略）
        if not is_advanced:
            has_action = '"action"' in code or "'action'" in code
            has_signal = '"signal"' in code or "'signal'" in code
            
            if not has_action and not has_signal:
                errors.append("analyze() 返回值必须包含 'action' 或 'signal' 字段")
            
            # 8. 检查信号/动作值
            has_valid_action = any(act in code for act in self.VALID_ACTIONS)
            has_valid_signal = any(sig in code for sig in self.VALID_SIGNALS)
            has_legacy_signal = any(sig in code for sig in self.LEGACY_SIGNALS)
            
            if has_action and has_valid_action:
                info.append("✓ 使用传统引擎格式（推荐）")
            elif has_signal and has_valid_signal:
                warnings.append("使用简化格式，可自动转换为传统引擎格式")
                info.append("简化格式可以自动转换")
                can_convert = True
            elif has_legacy_signal:
                warnings.append(f"检测到旧格式信号（BUY/SELL），可自动转换")
                can_convert = True
            elif not has_valid_action and not has_valid_signal:
                warnings.append(f"未找到有效信号值，推荐使用: LONG, SHORT, HOLD")
            
            # 9. 检查 type 字段（传统引擎需要）
            if has_action and ('"type"' not in code and "'type'" not in code):
                warnings.append("建议添加 'type' 字段（如 'CUSTOM'）以兼容传统引擎")
                can_convert = True
            
            # 10. 检查 reason 字段（建议）
            if '"reason"' not in code and "'reason'" not in code:
                warnings.append("建议在返回值中添加 'reason' 字段说明信号原因")
        else:
            # 高级策略：检查 PositionSide 使用
            if 'PositionSide.LONG' in code or 'PositionSide.SHORT' in code:
                info.append("✓ 使用 PositionSide 枚举返回信号")
        
        # 11. 检测策略类型
        strategy_features = self._detect_strategy_features(code)
        if strategy_features:
            info.extend(strategy_features)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "can_convert": can_convert,
            "class_name": class_name,
            "is_advanced": is_advanced
        }
    
    def _is_advanced_strategy(self, code: str, classes: List[ast.ClassDef]) -> bool:
        """检测是否是高级策略模板"""
        # 检查是否导入或继承 AdvancedStrategyBase
        if 'AdvancedStrategyBase' in code:
            return True
        if 'advanced_strategy_template' in code:
            return True
        
        # 检查类是否继承自 AdvancedStrategyBase
        for cls in classes:
            for base in cls.bases:
                if isinstance(base, ast.Name) and base.id == 'AdvancedStrategyBase':
                    return True
                if isinstance(base, ast.Attribute) and base.attr == 'AdvancedStrategyBase':
                    return True
        
        # 检查是否有高级策略特有的方法
        if 'check_entry_signal' in code and 'get_config_schema' in code:
            return True
        
        return False
    
    def convert_to_engine_format(self, code: str) -> Dict[str, Any]:
        """
        将策略代码转换为传统引擎格式
        
        Args:
            code: 原始策略代码
        
        Returns:
            {
                "success": bool,
                "code": str,  # 转换后的代码
                "changes": List[str]  # 修改说明
            }
        """
        changes = []
        converted_code = code
        
        # 1. 检查是否需要转换
        validation = self.validate(code)
        if not validation['valid']:
            return {
                "success": False,
                "code": code,
                "changes": [],
                "error": "代码验证失败，请先修复错误"
            }
        
        # 2. 转换 signal 为 action
        if '"signal"' in converted_code or "'signal'" in converted_code:
            # 替换返回值中的 signal 为 action
            for old_sig, new_act in self.SIGNAL_TO_ACTION.items():
                # 匹配 "signal": "xxx" 或 'signal': 'xxx'
                pattern1 = rf'(["\'])signal\1\s*:\s*(["\']){old_sig}\2'
                replacement1 = rf'"action": "{new_act}"'
                if re.search(pattern1, converted_code):
                    converted_code = re.sub(pattern1, replacement1, converted_code)
                    changes.append(f"signal: {old_sig} → action: {new_act}")
        
        # 3. 添加 type 字段（如果缺失）
        if '"type"' not in converted_code and "'type'" not in converted_code:
            # 在 action 后面添加 type
            pattern = r'("action"\s*:\s*"[^"]+")(\s*[,}])'
            replacement = r'\1, "type": "CUSTOM"\2'
            if re.search(pattern, converted_code):
                converted_code = re.sub(pattern, replacement, converted_code)
                changes.append("添加 type: CUSTOM")
        
        # 4. 添加 position_pct 和 leverage（如果缺失）
        if 'position_pct' not in converted_code:
            # 在 __init__ 中添加
            if 'def __init__' in converted_code:
                # 在 __init__ 方法体中添加
                pattern = r'(def __init__\s*\([^)]*\)\s*:.*?)((?=\n\s*def )|$)'
                def add_position_pct(match):
                    init_body = match.group(1)
                    rest = match.group(2)
                    if 'self.position_pct' not in init_body:
                        # 找到 __init__ 的最后一行，添加属性
                        lines = init_body.split('\n')
                        indent = '        '  # 默认缩进
                        for line in lines:
                            if line.strip().startswith('self.'):
                                indent = line[:len(line) - len(line.lstrip())]
                                break
                        new_lines = [
                            f"{indent}self.position_pct = 2.0  # 仓位比例 %",
                            f"{indent}self.leverage = 50  # 杠杆"
                        ]
                        return init_body.rstrip() + '\n' + '\n'.join(new_lines) + '\n' + rest
                    return match.group(0)
                
                converted_code = re.sub(pattern, add_position_pct, converted_code, flags=re.DOTALL)
                changes.append("添加 self.position_pct 和 self.leverage")
        
        # 5. 更新 analyze 方法签名（添加 timeframe 参数）
        if 'def analyze(self, ohlcv, symbol)' in converted_code:
            converted_code = converted_code.replace(
                'def analyze(self, ohlcv, symbol)',
                "def analyze(self, ohlcv, symbol, timeframe='5m')"
            )
            changes.append("analyze() 添加 timeframe 参数")
        
        # 6. 在返回值中添加 position_pct 和 leverage
        if 'self.position_pct' in converted_code and '"position_pct"' not in converted_code:
            # 在 return 语句中添加
            pattern = r'return\s*\{([^}]+)\}'
            def add_fields(match):
                content = match.group(1)
                if 'position_pct' not in content:
                    content = content.rstrip()
                    if not content.endswith(','):
                        content += ','
                    content += '\n            "position_pct": self.position_pct,\n            "leverage": self.leverage'
                return 'return {' + content + '\n        }'
            
            converted_code = re.sub(pattern, add_fields, converted_code)
            changes.append("返回值添加 position_pct 和 leverage")
        
        return {
            "success": True,
            "code": converted_code,
            "changes": changes
        }
    
    def _check_syntax(self, code: str) -> tuple:
        """检查 Python 语法"""
        try:
            compile(code, '<string>', 'exec')
            return True, None
        except SyntaxError as e:
            return False, f"行 {e.lineno}: {e.msg}"
        except Exception as e:
            return False, str(e)
    
    def _detect_strategy_features(self, code: str) -> List[str]:
        """检测策略特性"""
        features = []
        code_lower = code.lower()
        
        # 检测使用的指标
        indicators = []
        if 'ema' in code_lower:
            indicators.append("EMA")
        if 'sma' in code_lower or 'calc_ma' in code_lower:
            indicators.append("SMA")
        if 'rsi' in code_lower:
            indicators.append("RSI")
        if 'macd' in code_lower:
            indicators.append("MACD")
        if 'boll' in code_lower or 'bbands' in code_lower:
            indicators.append("布林带")
        if 'kdj' in code_lower or 'stoch' in code_lower:
            indicators.append("KDJ")
        if 'atr' in code_lower:
            indicators.append("ATR")
        
        if indicators:
            features.append(f"使用指标: {', '.join(indicators)}")
        
        # 检测信号类型
        signals = []
        if 'LONG' in code or 'open_long' in code:
            signals.append("做多")
        if 'SHORT' in code or 'open_short' in code:
            signals.append("做空")
        if 'CLOSE_LONG' in code or 'close_long' in code:
            signals.append("平多")
        if 'CLOSE_SHORT' in code or 'close_short' in code:
            signals.append("平空")
        
        if signals:
            features.append(f"信号类型: {', '.join(signals)}")
        
        # 检测是否有止损止盈
        if 'stop_loss' in code_lower:
            features.append("包含止损逻辑")
        if 'take_profit' in code_lower:
            features.append("包含止盈逻辑")
        
        # 检测是否使用加速计算
        if 'calc_ema' in code or 'calc_rsi' in code or 'USE_ACCELERATED' in code:
            features.append(" 使用加速指标计算")
        
        return features
