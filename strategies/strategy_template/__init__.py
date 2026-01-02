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
策略模板: 自定义策略的基础框架

使用说明：
1. 复制此目录到 strategies/ 下，修改 manifest.json 中的 strategy_id、display_name、description 等
2. 修改此文件中的类名和实现逻辑
3. 重启应用，新策略将自动出现在下拉列表中
"""

import pandas as pd
import numpy as np


class TemplateStrategy:
    """
    模板策略类
    
    所有策略必须实现以下接口：
    - __init__(): 初始化策略参数
    - analyze(df): 给定 OHLCV DataFrame，返回信号字典
    - get_position_size(symbol, balance, leverage): 计算仓位大小
    """
    
    def __init__(self):
        """初始化策略参数"""
        # 参数配置示例
        self.period_short = 12      # 短周期
        self.period_long = 26       # 长周期
        self.signal_period = 9      # 信号周期
        
        # 风控参数
        self.max_leverage = 50      # 最大杠杆
        self.position_size = 0.05   # 基础仓位比例
    
    def analyze(self, df: pd.DataFrame) -> dict:
        """
        分析 K 线数据并生成交易信号
        
        参数:
            df: OHLCV DataFrame，包含列：open, high, low, close, volume
        
        返回:
            dict: 包含以下字段的信号字典
                - signal: 'BUY', 'SELL', 'HOLD'
                - confidence: 0.0-1.0 的信心度
                - entry_price: 建议入场价格
                - stop_loss: 止损价格
                - take_profit: 止盈价格
                - reason: 信号生成的原因说明
        """
        if df.empty or len(df) < self.period_long:
            return {
                'signal': 'HOLD',
                'confidence': 0,
                'entry_price': None,
                'stop_loss': None,
                'take_profit': None,
                'reason': 'insufficient data'
            }
        
        # === 示例：简单 MACD 策略 ===
        # 计算 EMA
        ema_short = df['close'].ewm(span=self.period_short).mean()
        ema_long = df['close'].ewm(span=self.period_long).mean()
        
        # MACD 和信号线
        macd = ema_short - ema_long
        signal_line = macd.ewm(span=self.signal_period).mean()
        histogram = macd - signal_line
        
        # 获取最新值和前一个值
        latest_histogram = histogram.iloc[-1]
        prev_histogram = histogram.iloc[-2] if len(histogram) > 1 else 0
        
        latest_price = df['close'].iloc[-1]
        
        # 生成信号
        signal = 'HOLD'
        confidence = 0
        reason = ''
        
        if prev_histogram <= 0 and latest_histogram > 0:
            # MACD 从负转正 -> 买入信号
            signal = 'BUY'
            confidence = min(0.5 + abs(latest_histogram) / 100, 1.0)
            reason = 'MACD 金叉'
        elif prev_histogram >= 0 and latest_histogram < 0:
            # MACD 从正转负 -> 卖出信号
            signal = 'SELL'
            confidence = min(0.5 + abs(latest_histogram) / 100, 1.0)
            reason = 'MACD 死叉'
        else:
            reason = 'no signal crossover'
        
        # 计算止损和止盈（可选）
        atr_period = 14
        tr = np.maximum(
            df['high'].iloc[-atr_period:] - df['low'].iloc[-atr_period:],
            np.maximum(
                np.abs(df['high'].iloc[-atr_period:] - df['close'].shift(1).iloc[-atr_period:]),
                np.abs(df['low'].iloc[-atr_period:] - df['close'].shift(1).iloc[-atr_period:])
            )
        )
        atr = tr.mean()
        
        stop_loss = latest_price - atr * 2
        take_profit = latest_price + atr * 3
        
        return {
            'signal': signal,
            'confidence': confidence,
            'entry_price': latest_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'reason': reason
        }
    
    def get_position_size(self, symbol: str, balance: float, leverage: float = 1.0) -> float:
        """
        计算指定交易对的仓位大小
        
        参数:
            symbol: 交易对（如 'BTC/USDT'）
            balance: 账户余额（USDT）
            leverage: 使用杠杆倍数
        
        返回:
            float: 仓位大小（USDT）
        """
        position_usd = balance * self.position_size * leverage
        # 限制杠杆不超过 max_leverage
        position_usd = min(position_usd, balance * self.max_leverage)
        return position_usd
    
    def set_parameters(self, **kwargs):
        """
        动态设置策略参数
        
        用法:
            strategy.set_parameters(period_short=10, period_long=24)
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# 策略配置示例（可选，用于 UI 显示参数调整界面）
STRATEGY_PARAMS = {
    'period_short': {
        'type': 'int',
        'min': 5,
        'max': 50,
        'default': 12,
        'description': 'EMA 短周期'
    },
    'period_long': {
        'type': 'int',
        'min': 10,
        'max': 200,
        'default': 26,
        'description': 'EMA 长周期'
    },
    'signal_period': {
        'type': 'int',
        'min': 3,
        'max': 20,
        'default': 9,
        'description': 'MACD 信号线周期'
    },
    'position_size': {
        'type': 'float',
        'min': 0.01,
        'max': 0.2,
        'step': 0.01,
        'default': 0.05,
        'description': '基础仓位比例'
    }
}
