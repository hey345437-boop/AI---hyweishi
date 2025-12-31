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
AI 策略代码生成器

从自然语言描述生成符合系统模板的策略代码
"""
from typing import Dict, Any, Optional


class StrategyGenerator:
    """AI 策略代码生成器"""
    
    def __init__(self):
        self.ai_config = self._load_ai_config()
        self.template = self._get_template()
    
    def _load_ai_config(self) -> Dict[str, Any]:
        """加载 AI API 配置"""
        try:
            from ai_config_manager import get_ai_config_manager
            config_mgr = get_ai_config_manager()
            configs = config_mgr.get_all_ai_api_configs()
            # 找到第一个已验证的 AI
            for ai_id, config in configs.items():
                if config.get('verified') and config.get('enabled'):
                    return {
                        "ai_id": ai_id,
                        "api_key": config.get('api_key'),
                        "enabled": True
                    }
        except ImportError:
            pass
        return {"enabled": False}
    
    def _get_template(self) -> str:
        """获取策略模板 - 兼容传统交易引擎格式"""
        return '''"""
{description}

自动生成的策略代码
使用 ai_indicators 加速计算
兼容传统交易引擎格式
"""
import numpy as np

# 尝试导入加速指标模块
try:
    from ai_indicators import calc_ema, calc_ma, calc_rsi, calc_macd, calc_boll, calc_kdj, calc_atr, calc_obv, calc_vwap
    USE_ACCELERATED = True
except ImportError:
    import pandas_ta as ta
    USE_ACCELERATED = False


class {class_name}:
    """自动生成的策略"""
    
    def __init__(self, config=None):
        self.config = config or {{}}
        # 仓位比例（可在前端配置覆盖）
        self.position_pct = 2.0  # 默认 2%
        self.leverage = 50  # 默认杠杆
    
    def analyze(self, ohlcv, symbol, timeframe='5m'):
        """
        分析K线数据，返回交易信号
        
        Args:
            ohlcv: pandas DataFrame，包含 open, high, low, close, volume
            symbol: 交易对，如 "BTC/USDT:USDT"
            timeframe: 时间周期，如 "5m"
        
        Returns:
            dict: 兼容传统引擎的信号格式
                  {{"action": "LONG/SHORT/HOLD", "type": "CUSTOM", "reason": "..."}}
        """
        if ohlcv is None or len(ohlcv) < 30:
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "数据不足"}}
        
        # 提取价格数据
        close = ohlcv['close'].values if hasattr(ohlcv['close'], 'values') else np.array(ohlcv['close'])
        high = ohlcv['high'].values if hasattr(ohlcv['high'], 'values') else np.array(ohlcv['high'])
        low = ohlcv['low'].values if hasattr(ohlcv['low'], 'values') else np.array(ohlcv['low'])
        
{indicator_code}
        
{signal_logic}
        
        # 转换为传统引擎格式
        return self._to_engine_format(signal, reason)
    
    def _to_engine_format(self, signal, reason):
        """将简单信号转换为传统引擎格式"""
        signal_map = {{
            "open_long": "LONG",
            "open_short": "SHORT",
            "close_long": "CLOSE_LONG",
            "close_short": "CLOSE_SHORT",
            "wait": "HOLD"
        }}
        action = signal_map.get(signal, "HOLD")
        return {{
            "action": action,
            "type": "CUSTOM",  # 用户自定义策略统一使用 CUSTOM 类型
            "position_pct": self.position_pct,
            "leverage": self.leverage,
            "reason": reason
        }}
'''

    def generate_from_description(self, description: str) -> Dict[str, Any]:
        """
        从自然语言描述生成策略代码
        
        Args:
            description: 用户的策略描述（中英文）
        
        Returns:
            {"success": True, "code": "...", "explanation": "..."} 或
            {"success": False, "error": "..."}
        """
        if not self.ai_config.get('enabled'):
            # AI 未配置，使用规则匹配生成
            return self._generate_by_rules(description)
        
        # 使用 AI 生成
        return self._generate_by_ai(description)
    
    def _generate_by_rules(self, description: str) -> Dict[str, Any]:
        """基于规则匹配生成策略（无 AI 时的回退方案）"""
        description_lower = description.lower()
        
        # 检测策略类型
        indicator_code = ""
        signal_logic = ""
        class_name = "CustomStrategy"
        
        # EMA/均线策略
        if 'ema' in description_lower or '均线' in description:
            indicator_code, signal_logic = self._gen_ema_strategy(description)
            class_name = "EmaStrategy"
        # RSI 策略
        elif 'rsi' in description_lower:
            indicator_code, signal_logic = self._gen_rsi_strategy(description)
            class_name = "RsiStrategy"
        # MACD 策略
        elif 'macd' in description_lower:
            indicator_code, signal_logic = self._gen_macd_strategy(description)
            class_name = "MacdStrategy"
        # 布林带策略
        elif 'boll' in description_lower or '布林' in description:
            indicator_code, signal_logic = self._gen_boll_strategy(description)
            class_name = "BollStrategy"
        else:
            # 默认 EMA 策略
            indicator_code, signal_logic = self._gen_ema_strategy(description)
            class_name = "CustomStrategy"
        
        code = self.template.format(
            class_name=class_name,
            description=description,
            indicator_code=indicator_code,
            signal_logic=signal_logic
        )
        
        return {
            "success": True,
            "code": code,
            "explanation": f"基于规则生成的 {class_name} 策略"
        }

    def _gen_ema_strategy(self, description: str) -> tuple:
        """生成 EMA 策略代码 - 使用加速指标，兼容传统引擎"""
        # 尝试从描述中提取参数
        import re
        
        # 默认参数
        fast_period = 12
        slow_period = 26
        
        # 尝试提取数字
        numbers = re.findall(r'\d+', description)
        if len(numbers) >= 2:
            fast_period = int(numbers[0])
            slow_period = int(numbers[1])
            if fast_period > slow_period:
                fast_period, slow_period = slow_period, fast_period
        
        indicator_code = f'''        # 计算 EMA 指标（优先使用加速计算）
        if USE_ACCELERATED:
            ema_fast = calc_ema(close, {fast_period})
            ema_slow = calc_ema(close, {slow_period})
        else:
            ema_fast = ta.ema(ohlcv['close'], length={fast_period}).values
            ema_slow = ta.ema(ohlcv['close'], length={slow_period}).values
        
        if ema_fast is None or ema_slow is None or len(ema_fast) < 2:
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "指标计算失败"}}
        
        # 获取最新值
        ema_fast_now = ema_fast[-1]
        ema_slow_now = ema_slow[-1]
        ema_fast_prev = ema_fast[-2]
        ema_slow_prev = ema_slow[-2]
        
        # 检查 NaN
        if np.isnan(ema_fast_now) or np.isnan(ema_slow_now):
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "指标数据不足"}}'''
        
        signal_logic = f'''        # 判断金叉死叉
        signal = "wait"
        reason = ""
        
        # 金叉：快线从下方穿越慢线
        if ema_fast_prev <= ema_slow_prev and ema_fast_now > ema_slow_now:
            signal = "open_long"
            reason = f"EMA{fast_period}上穿EMA{slow_period}，金叉做多"
        
        # 死叉：快线从上方穿越慢线
        elif ema_fast_prev >= ema_slow_prev and ema_fast_now < ema_slow_now:
            signal = "open_short"
            reason = f"EMA{fast_period}下穿EMA{slow_period}，死叉做空"'''
        
        return indicator_code, signal_logic
    
    def _gen_rsi_strategy(self, description: str) -> tuple:
        """生成 RSI 策略代码 - 使用加速指标，兼容传统引擎"""
        import re
        
        # 默认参数
        period = 14
        oversold = 30
        overbought = 70
        
        # 尝试提取数字
        numbers = re.findall(r'\d+', description)
        if len(numbers) >= 1:
            period = int(numbers[0])
        if len(numbers) >= 3:
            oversold = int(numbers[1])
            overbought = int(numbers[2])
        
        indicator_code = f'''        # 计算 RSI 指标（优先使用加速计算）
        if USE_ACCELERATED:
            rsi = calc_rsi(close, {period})
        else:
            rsi = ta.rsi(ohlcv['close'], length={period}).values
        
        if rsi is None or len(rsi) < 2:
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "RSI计算失败"}}
        
        rsi_now = rsi[-1]
        rsi_prev = rsi[-2]
        
        # 检查 NaN
        if np.isnan(rsi_now):
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "RSI数据不足"}}'''
        
        signal_logic = f'''        # RSI 超买超卖判断
        signal = "wait"
        reason = ""
        
        # 超卖区域做多
        if rsi_now < {oversold}:
            signal = "open_long"
            reason = f"RSI={{rsi_now:.1f}}进入超卖区域，做多"
        
        # 超买区域做空
        elif rsi_now > {overbought}:
            signal = "open_short"
            reason = f"RSI={{rsi_now:.1f}}进入超买区域，做空"'''
        
        return indicator_code, signal_logic

    def _gen_macd_strategy(self, description: str) -> tuple:
        """生成 MACD 策略代码 - 使用加速指标，兼容传统引擎"""
        indicator_code = '''        # 计算 MACD 指标（优先使用加速计算）
        if USE_ACCELERATED:
            macd_result = calc_macd(close, fast=12, slow=26, signal=9)
            macd_line = macd_result['macd']
            signal_line = macd_result['signal']
            histogram = macd_result['histogram']
        else:
            macd_df = ta.macd(ohlcv['close'], fast=12, slow=26, signal=9)
            macd_line = macd_df.iloc[:, 0].values
            signal_line = macd_df.iloc[:, 2].values
            histogram = macd_df.iloc[:, 1].values
        
        if macd_line is None or len(macd_line) < 2:
            return {"action": "HOLD", "type": "CUSTOM", "reason": "MACD计算失败"}
        
        macd_now = macd_line[-1]
        signal_now = signal_line[-1]
        macd_prev = macd_line[-2]
        signal_prev = signal_line[-2]
        hist_now = histogram[-1]
        
        # 检查 NaN
        if np.isnan(macd_now) or np.isnan(signal_now):
            return {"action": "HOLD", "type": "CUSTOM", "reason": "MACD数据不足"}'''
        
        signal_logic = '''        # MACD 金叉死叉判断
        signal = "wait"
        reason = ""
        
        # 金叉：MACD线从下方穿越信号线
        if macd_prev <= signal_prev and macd_now > signal_now:
            signal = "open_long"
            reason = f"MACD金叉，柱状图={hist_now:.4f}"
        
        # 死叉：MACD线从上方穿越信号线
        elif macd_prev >= signal_prev and macd_now < signal_now:
            signal = "open_short"
            reason = f"MACD死叉，柱状图={hist_now:.4f}"'''
        
        return indicator_code, signal_logic
    
    def _gen_boll_strategy(self, description: str) -> tuple:
        """生成布林带策略代码 - 使用加速指标，兼容传统引擎"""
        import re
        
        # 默认参数
        period = 20
        std = 2.0
        
        numbers = re.findall(r'\d+', description)
        if len(numbers) >= 1:
            period = int(numbers[0])
        
        indicator_code = f'''        # 计算布林带指标（优先使用加速计算）
        if USE_ACCELERATED:
            boll_result = calc_boll(close, {period}, {std})
            upper = boll_result['upper']
            middle = boll_result['middle']
            lower = boll_result['lower']
        else:
            bbands = ta.bbands(ohlcv['close'], length={period}, std={std})
            upper = bbands.iloc[:, 0].values
            middle = bbands.iloc[:, 1].values
            lower = bbands.iloc[:, 2].values
        
        if upper is None or len(upper) < 1:
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "布林带计算失败"}}
        
        close_now = close[-1]
        upper_now = upper[-1]
        lower_now = lower[-1]
        middle_now = middle[-1]
        
        # 检查 NaN
        if np.isnan(upper_now) or np.isnan(lower_now):
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "布林带数据不足"}}'''
        
        signal_logic = '''        # 布林带突破判断
        signal = "wait"
        reason = ""
        
        # 价格触及下轨，做多
        if close_now <= lower_now:
            signal = "open_long"
            reason = f"价格触及布林带下轨，做多"
        
        # 价格触及上轨，做空
        elif close_now >= upper_now:
            signal = "open_short"
            reason = f"价格触及布林带上轨，做空"'''
        
        return indicator_code, signal_logic

    def _generate_by_ai(self, description: str) -> Dict[str, Any]:
        """使用 AI 生成策略代码"""
        try:
            from ai_providers import UniversalAIClient, get_provider
            
            ai_id = self.ai_config.get('ai_id')
            api_key = self.ai_config.get('api_key')
            model_id = self.ai_config.get('model_id')  # 支持指定模型
            
            if not ai_id or not api_key:
                return self._generate_by_rules(description)
            
            # 构建提示词
            prompt = self._build_ai_prompt(description)
            system_prompt = "你是一个专业的量化交易策略开发助手。只返回 Python 代码，不要其他解释。"
            
            # 使用通用 AI 客户端
            try:
                client = UniversalAIClient(ai_id, api_key, model_id)
                client.timeout = 90  # 策略生成需要更长时间
                response = client.chat(prompt, system_prompt=system_prompt, max_tokens=4096)
            except Exception as e:
                print(f"[StrategyGenerator] AI 客户端错误: {e}")
                return self._generate_by_rules(description)
            
            if response and ('class' in response or 'def analyze' in response):
                # 提取代码块
                code = self._extract_code_from_response(response)
                
                # 获取服务商名称
                provider = get_provider(ai_id)
                provider_name = provider.name if provider else ai_id.upper()
                
                return {
                    "success": True,
                    "code": code,
                    "explanation": f"由 {provider_name} 生成的策略代码"
                }
            else:
                # AI 返回无效，回退到规则生成
                return self._generate_by_rules(description)
                
        except ImportError:
            # ai_providers 模块不存在，使用旧方法
            return self._generate_by_ai_legacy(description)
        except Exception as e:
            # AI 调用失败，回退到规则生成
            print(f"[StrategyGenerator] AI 调用失败: {e}")
            return self._generate_by_rules(description)
    
    def _generate_by_ai_legacy(self, description: str) -> Dict[str, Any]:
        """旧版 AI 生成方法（兼容）"""
        import httpx
        
        try:
            ai_id = self.ai_config.get('ai_id')
            api_key = self.ai_config.get('api_key')
            
            if not ai_id or not api_key:
                return self._generate_by_rules(description)
            
            # 构建提示词
            prompt = self._build_ai_prompt(description)
            
            # 根据 AI 类型选择 API
            api_configs = {
                "deepseek": {
                    "url": "https://api.deepseek.com/v1/chat/completions",
                    "model": "deepseek-chat",
                    "max_tokens": 4000
                },
                "qwen": {
                    "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                    "model": "qwen-max",
                    "max_tokens": 4000
                },
                "spark": {
                    "url": "https://spark-api-open.xf-yun.com/v1/chat/completions",
                    "model": "generalv3.5",
                    "max_tokens": 4000
                },
                "spark_lite": {
                    "url": "https://spark-api-open.xf-yun.com/v1/chat/completions",
                    "model": "lite",
                    "max_tokens": 4000
                },
                "hunyuan": {
                    "url": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                    "model": "hunyuan-lite",
                    "max_tokens": 4000
                },
                "glm": {
                    "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                    "model": "glm-4-flash",
                    "max_tokens": 4000
                },
                "doubao": {
                    "url": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                    "model": "doubao-pro-4k",
                    "max_tokens": 4000
                },
                "openai": {
                    "url": "https://api.openai.com/v1/chat/completions",
                    "model": "gpt-4o-mini",
                    "max_tokens": 4000
                },
                "perplexity": {
                    "url": "https://api.perplexity.ai/chat/completions",
                    "model": "llama-3.1-sonar-small-128k-online",
                    "max_tokens": 4000
                }
            }
            
            config = api_configs.get(ai_id)
            if not config:
                return self._generate_by_rules(description)
            
            # 同步调用 API
            response = self._call_ai_api_sync(
                url=config["url"],
                api_key=api_key,
                model=config["model"],
                prompt=prompt,
                max_tokens=config["max_tokens"]
            )
            
            if response and ('class' in response or 'def analyze' in response):
                code = self._extract_code_from_response(response)
                return {
                    "success": True,
                    "code": code,
                    "explanation": f"由 {ai_id.upper()} 生成的策略代码"
                }
            else:
                return self._generate_by_rules(description)
                
        except Exception as e:
            print(f"[StrategyGenerator] AI 调用失败: {e}")
            return self._generate_by_rules(description)
    
    def _build_ai_prompt(self, description: str) -> str:
        """构建 AI 提示词 - 支持高级策略模板和传统格式"""
        # 检测是否需要高级功能
        advanced_keywords = ['止损', '止盈', 'stop', 'loss', 'profit', 'trailing', '追踪',
                            '分批', '平仓', 'atr', 'ATR', '风控', '仓位计算', '动态',
                            '时间过滤', '新闻', '冷却', '防抖']
        
        needs_advanced = any(kw in description.lower() for kw in advanced_keywords)
        
        if needs_advanced:
            return self._build_advanced_prompt(description)
        else:
            return self._build_simple_prompt(description)
    
    def _build_simple_prompt(self, description: str) -> str:
        """构建简单策略提示词 - 兼容传统引擎格式"""
        return f"""你是一个专业的量化交易策略开发助手。请根据以下描述生成 Python 策略代码。

用户描述：{description}

要求：
1. 生成一个完整的 Python 类
2. 必须实现 __init__(self, config=None) 方法，包含 self.position_pct = 2.0 和 self.leverage = 50
3. 必须实现 analyze(self, ohlcv, symbol, timeframe='5m') 方法
4. analyze 返回格式必须是：{{"action": "LONG/SHORT/HOLD", "type": "CUSTOM", "position_pct": self.position_pct, "leverage": self.leverage, "reason": "..."}}
5. action 值必须是: LONG（做多）, SHORT（做空）, HOLD（等待）, CLOSE_LONG（平多）, CLOSE_SHORT（平空）之一
6. type 固定为 "CUSTOM"
7. 优先使用 ai_indicators 模块的加速函数（calc_ema, calc_rsi, calc_macd, calc_boll, calc_kdj, calc_atr）
8. 如果 ai_indicators 不可用，回退到 pandas_ta
9. ohlcv 是 pandas DataFrame，包含 open, high, low, close, volume 列
10. 代码要有中文注释

返回格式示例：
```python
import numpy as np

try:
    from ai_indicators import calc_ema, calc_rsi, calc_macd
    USE_ACCELERATED = True
except ImportError:
    import pandas_ta as ta
    USE_ACCELERATED = False


class MyStrategy:
    def __init__(self, config=None):
        self.config = config or {{}}
        self.position_pct = 2.0  # 仓位比例
        self.leverage = 50  # 杠杆
    
    def analyze(self, ohlcv, symbol, timeframe='5m'):
        if ohlcv is None or len(ohlcv) < 30:
            return {{"action": "HOLD", "type": "CUSTOM", "reason": "数据不足"}}
        
        close = ohlcv['close'].values
        
        # 使用加速计算
        if USE_ACCELERATED:
            ema = calc_ema(close, 12)
        else:
            ema = ta.ema(ohlcv['close'], length=12).values
        
        # ... 信号逻辑 ...
        
        return {{
            "action": "HOLD",  # LONG/SHORT/HOLD/CLOSE_LONG/CLOSE_SHORT
            "type": "CUSTOM",
            "position_pct": self.position_pct,
            "leverage": self.leverage,
            "reason": "等待信号"
        }}
```

只返回 Python 代码，不要其他解释。"""
    
    def _build_advanced_prompt(self, description: str) -> str:
        """构建高级策略提示词 - 简化版本，避免输出被截断"""
        return f"""你是量化策略开发助手。根据描述生成继承 AdvancedStrategyBase 的策略代码。

用户描述：{description}

【重要】基类 AdvancedStrategyBase 已实现以下功能，你不需要重复实现：
- 动态 ATR 止损（_calculate_stop_loss）
- 分批止盈 TP1/TP2/TP3（_check_take_profit）
- 追踪止损（_update_trailing_stop）
- 时间过滤（_is_allowed_trading_time，通过 self.risk.allowed_hours 配置）
- 仓位计算（_calculate_position_size）
- 动态杠杆（_calculate_leverage）
- 止损后冷却期（_is_in_cooldown）

你只需实现：
1. _calculate_indicators() - 计算技术指标
2. check_entry_signal() - 返回 PositionSide.LONG/SHORT/None
3. check_exit_signal() - 返回 True/False（可选，反向信号平仓）

【禁止】不要自己实现 calculate_stop_loss、calculate_take_profit_levels、_is_trading_hour、_calculate_position_size、_calculate_leverage 等方法，这些基类已有。

完整代码模板：
```python
import numpy as np
from typing import Dict, Any, Optional

try:
    from strategies.advanced_strategy_template import AdvancedStrategyBase, PositionSide
except ImportError:
    from advanced_strategy_template import AdvancedStrategyBase, PositionSide

try:
    from ai_indicators import calc_ema, calc_rsi, calc_atr
    USE_ACCELERATED = True
except ImportError:
    import pandas_ta as ta
    USE_ACCELERATED = False


class TrendStrategy(AdvancedStrategyBase):
    \"\"\"
    趋势跟随策略
    - 入场：EMA 金叉/死叉 + 趋势过滤 + RSI 过滤 + 成交量确认
    - 止损/止盈/时间过滤：由基类自动管理，通过前端配置参数
    \"\"\"
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)  # 基类会加载所有风控参数
        # 只定义策略特有的指标参数
        self.ema_fast = config.get('ema_fast', 12) if config else 12
        self.ema_slow = config.get('ema_slow', 26) if config else 26
        self.ema_trend = config.get('ema_trend', 200) if config else 200
        self.rsi_period = config.get('rsi_period', 14) if config else 14
        self.volume_threshold = config.get('volume_threshold', 1.2) if config else 1.2
        # 止损后增强信号参数
        self.enhanced_volume_threshold = config.get('enhanced_volume_threshold', 1.4) if config else 1.4
        self.enhanced_rsi_long_min = config.get('enhanced_rsi_long_min', 50) if config else 50
        self.enhanced_rsi_long_max = config.get('enhanced_rsi_long_max', 65) if config else 65
        self.enhanced_rsi_short_min = config.get('enhanced_rsi_short_min', 35) if config else 35
        self.enhanced_rsi_short_max = config.get('enhanced_rsi_short_max', 50) if config else 50
    
    def _calculate_indicators(self, ohlcv) -> Dict[str, np.ndarray]:
        \"\"\"计算策略所需的技术指标\"\"\"
        close = ohlcv['close'].values if hasattr(ohlcv['close'], 'values') else np.array(ohlcv['close'])
        high = ohlcv['high'].values if hasattr(ohlcv['high'], 'values') else np.array(ohlcv['high'])
        low = ohlcv['low'].values if hasattr(ohlcv['low'], 'values') else np.array(ohlcv['low'])
        volume = ohlcv['volume'].values if hasattr(ohlcv['volume'], 'values') else np.array(ohlcv['volume'])
        
        if USE_ACCELERATED:
            ema_fast = calc_ema(close, self.ema_fast)
            ema_slow = calc_ema(close, self.ema_slow)
            ema_trend = calc_ema(close, self.ema_trend)
            rsi = calc_rsi(close, self.rsi_period)
            atr = calc_atr(high, low, close, 14)
        else:
            ema_fast = ta.ema(ohlcv['close'], length=self.ema_fast).values
            ema_slow = ta.ema(ohlcv['close'], length=self.ema_slow).values
            ema_trend = ta.ema(ohlcv['close'], length=self.ema_trend).values
            rsi_s = ta.rsi(ohlcv['close'], length=self.rsi_period)
            rsi = rsi_s.values if rsi_s is not None else np.zeros(len(close))
            atr_df = ta.atr(ohlcv['high'], ohlcv['low'], ohlcv['close'], length=14)
            atr = atr_df.values if atr_df is not None else np.zeros(len(close))
        
        vol_sma = np.convolve(volume, np.ones(20)/20, mode='same')
        
        return {{'close': close, 'high': high, 'low': low, 'volume': volume,
                'ema_fast': ema_fast, 'ema_slow': ema_slow, 'ema_trend': ema_trend,
                'rsi': rsi, 'atr': atr, 'vol_sma': vol_sma}}
    
    def check_entry_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> Optional[PositionSide]:
        \"\"\"检查入场信号 - 只负责判断方向，止损止盈由基类管理\"\"\"
        ema_fast = indicators['ema_fast']
        ema_slow = indicators['ema_slow']
        ema_trend = indicators['ema_trend']
        rsi = indicators['rsi']
        volume = indicators['volume']
        vol_sma = indicators['vol_sma']
        close = indicators['close']
        
        if len(ema_fast) < 2 or np.isnan(ema_fast[-1]) or np.isnan(rsi[-1]):
            return None
        
        # 检查是否需要增强信号（止损后重入）
        need_enhanced = self._needs_enhanced_signal()
        vol_threshold = self.enhanced_volume_threshold if need_enhanced else self.volume_threshold
        
        # 成交量过滤
        if volume[-1] < vol_sma[-1] * vol_threshold:
            return None
        
        # RSI 区间（止损后使用更严格的区间）
        if need_enhanced:
            rsi_long_min, rsi_long_max = self.enhanced_rsi_long_min, self.enhanced_rsi_long_max
            rsi_short_min, rsi_short_max = self.enhanced_rsi_short_min, self.enhanced_rsi_short_max
        else:
            rsi_long_min, rsi_long_max = 45, 70
            rsi_short_min, rsi_short_max = 30, 55
        
        # 金叉做多：EMA快线上穿慢线 + 价格在趋势线上方 + RSI 在区间内
        if (ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1] and
            close[-1] > ema_trend[-1] and rsi_long_min <= rsi[-1] <= rsi_long_max):
            return PositionSide.LONG
        
        # 死叉做空：EMA快线下穿慢线 + 价格在趋势线下方 + RSI 在区间内
        if (ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1] and
            close[-1] < ema_trend[-1] and rsi_short_min <= rsi[-1] <= rsi_short_max):
            return PositionSide.SHORT
        
        return None
    
    def check_exit_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> bool:
        \"\"\"检查出场信号 - 反向交叉时平仓\"\"\"
        if self.position.side is None:
            return False
        ema_fast = indicators['ema_fast']
        ema_slow = indicators['ema_slow']
        if len(ema_fast) < 2:
            return False
        # 多头遇到死叉平仓
        if self.position.side == PositionSide.LONG:
            return ema_fast[-2] >= ema_slow[-2] and ema_fast[-1] < ema_slow[-1]
        # 空头遇到金叉平仓
        if self.position.side == PositionSide.SHORT:
            return ema_fast[-2] <= ema_slow[-2] and ema_fast[-1] > ema_slow[-1]
        return False


# 兼容传统引擎的包装类
class TrendStrategyWrapper:
    def __init__(self, config=None):
        self.strategy = TrendStrategy(config)
        self.config = config or {{}}
        self.position_pct = self.config.get('position_pct', 2.0)
        self.leverage = self.config.get('leverage', 5)
    
    def analyze(self, ohlcv, symbol: str, timeframe: str = '15m') -> Dict[str, Any]:
        result = self.strategy.analyze(ohlcv, symbol, timeframe)
        result['position_pct'] = self.position_pct
        result['leverage'] = self.leverage
        return result
    
    def run_analysis_with_data(self, symbol: str, preloaded_data: dict, due_tfs: list) -> list:
        \"\"\"兼容交易引擎的调用方式\"\"\"
        return self.strategy.run_analysis_with_data(symbol, preloaded_data, due_tfs)
    
    def get_config_schema(self) -> Dict[str, Any]:
        return self.strategy.get_config_schema()
```

根据用户描述修改：
1. __init__ 中的指标参数
2. _calculate_indicators 中计算的指标
3. check_entry_signal 中的入场条件
4. check_exit_signal 中的出场条件（可选）

【再次强调】不要自己实现止损、止盈、时间过滤、仓位计算等方法，这些由基类和前端配置管理。
只返回完整 Python 代码，不要解释。"""
    
    def _extract_code_from_response(self, response: str) -> str:
        """从 AI 响应中提取代码"""
        # 尝试提取 ```python ... ``` 代码块
        import re
        
        code_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # 尝试提取 ``` ... ``` 代码块
        code_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # 如果没有代码块，检查是否整个响应就是代码
        if 'class' in response and ('def analyze' in response or 'def check_entry_signal' in response):
            return response.strip()
        
        return response
