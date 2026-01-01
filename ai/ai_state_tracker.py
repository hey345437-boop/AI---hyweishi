# -*- coding: utf-8 -*-
"""
AI 状态追踪模块

追踪指标和价格的历史状态，计算变化量，生成状态摘要。
用于减少 AI 输入的冗余信息，提供更有价值的变化信息。
"""
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class IndicatorSnapshot:
    """指标快照"""
    timestamp: int
    values: Dict[str, float]
    price: float


@dataclass
class MarketState:
    """市场状态摘要"""
    trend: str  # up / down / sideways
    momentum: str  # strong / weak / neutral
    volatility: str  # high / normal / low
    volume_trend: str  # increasing / decreasing / stable
    key_levels: Dict[str, float]  # support / resistance
    signals: List[str]  # 关键信号列表


class StateTracker:
    """
    状态追踪器
    
    为每个 symbol+timeframe 维护历史状态，计算变化量
    """
    
    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        # {(symbol, timeframe): deque[IndicatorSnapshot]}
        self._history: Dict[Tuple[str, str], deque] = {}
    
    def _get_key(self, symbol: str, timeframe: str) -> Tuple[str, str]:
        return (symbol, timeframe)
    
    def record(
        self, 
        symbol: str, 
        timeframe: str, 
        values: Dict[str, float], 
        price: float
    ) -> None:
        """记录当前状态"""
        key = self._get_key(symbol, timeframe)
        if key not in self._history:
            self._history[key] = deque(maxlen=self.max_history)
        
        snapshot = IndicatorSnapshot(
            timestamp=int(time.time() * 1000),
            values=values.copy(),
            price=price
        )
        self._history[key].append(snapshot)
    
    def get_previous(
        self, 
        symbol: str, 
        timeframe: str, 
        offset: int = 1
    ) -> Optional[IndicatorSnapshot]:
        """获取历史快照"""
        key = self._get_key(symbol, timeframe)
        history = self._history.get(key)
        if not history or len(history) <= offset:
            return None
        return history[-(offset + 1)]
    
    def calc_changes(
        self, 
        symbol: str, 
        timeframe: str, 
        current_values: Dict[str, float],
        current_price: float
    ) -> Dict[str, Dict[str, Any]]:
        """
        计算指标变化量
        
        返回:
            {
                'indicator_name': {
                    'current': float,
                    'previous': float,
                    'change': float,
                    'change_pct': float,
                    'direction': str  # up / down / flat
                }
            }
        """
        prev = self.get_previous(symbol, timeframe)
        changes = {}
        
        for name, current in current_values.items():
            if current is None:
                continue
            
            change_info = {
                'current': current,
                'previous': None,
                'change': 0.0,
                'change_pct': 0.0,
                'direction': 'new'  # 首次记录标记为 new
            }
            
            if prev and name in prev.values and prev.values[name] is not None:
                previous = prev.values[name]
                change_info['previous'] = previous
                change_info['change'] = current - previous
                
                if previous != 0:
                    change_info['change_pct'] = (current - previous) / abs(previous) * 100
                
                # 根据变化幅度判断方向
                threshold = abs(previous) * 0.001 if previous != 0 else 0.001
                if change_info['change'] > threshold:
                    change_info['direction'] = 'up'
                elif change_info['change'] < -threshold:
                    change_info['direction'] = 'down'
                else:
                    change_info['direction'] = 'flat'
            
            changes[name] = change_info
        
        # 价格变化
        price_change = {
            'current': current_price,
            'previous': prev.price if prev else None,
            'change': 0.0,
            'change_pct': 0.0,
            'direction': 'new'
        }
        if prev and prev.price:
            price_change['change'] = current_price - prev.price
            price_change['change_pct'] = (current_price - prev.price) / prev.price * 100
            if price_change['change'] > 0:
                price_change['direction'] = 'up'
            elif price_change['change'] < 0:
                price_change['direction'] = 'down'
            else:
                price_change['direction'] = 'flat'
        
        changes['_price'] = price_change
        
        return changes
    
    def analyze_market_state(
        self,
        symbol: str,
        timeframe: str,
        current_values: Dict[str, float],
        current_price: float,
        ohlcv: List[List]
    ) -> MarketState:
        """
        分析市场状态，生成摘要
        """
        signals = []
        
        # 趋势判断
        trend = 'sideways'
        ma = current_values.get('MA')
        ema = current_values.get('EMA')
        if ma and ema:
            if current_price > ma and current_price > ema:
                trend = 'up'
            elif current_price < ma and current_price < ema:
                trend = 'down'
        
        # 动量判断
        momentum = 'neutral'
        rsi = current_values.get('RSI')
        macd_hist = current_values.get('MACD_Hist')
        
        if rsi:
            if rsi > 70:
                momentum = 'overbought'
                signals.append('RSI超买(>70)')
            elif rsi < 30:
                momentum = 'oversold'
                signals.append('RSI超卖(<30)')
            elif rsi > 60:
                momentum = 'strong'
            elif rsi < 40:
                momentum = 'weak'
        
        if macd_hist:
            if macd_hist > 0:
                if momentum == 'neutral':
                    momentum = 'bullish'
            else:
                if momentum == 'neutral':
                    momentum = 'bearish'
        
        # 波动性判断
        volatility = 'normal'
        atr = current_values.get('ATR')
        boll_upper = current_values.get('BOLL_Upper')
        boll_lower = current_values.get('BOLL_Lower')
        
        if boll_upper and boll_lower and current_price:
            boll_width = (boll_upper - boll_lower) / current_price * 100
            if boll_width > 5:
                volatility = 'high'
            elif boll_width < 2:
                volatility = 'low'
        
        # 成交量趋势
        volume_trend = 'stable'
        if ohlcv and len(ohlcv) >= 5:
            recent_vols = [c[5] for c in ohlcv[-5:]]
            older_vols = [c[5] for c in ohlcv[-10:-5]] if len(ohlcv) >= 10 else recent_vols
            avg_recent = sum(recent_vols) / len(recent_vols)
            avg_older = sum(older_vols) / len(older_vols)
            if avg_recent > avg_older * 1.2:
                volume_trend = 'increasing'
                signals.append('成交量放大')
            elif avg_recent < avg_older * 0.8:
                volume_trend = 'decreasing'
        
        # 关键价位
        key_levels = {}
        if boll_upper:
            key_levels['resistance'] = boll_upper
        if boll_lower:
            key_levels['support'] = boll_lower
        if current_values.get('VWAP'):
            key_levels['vwap'] = current_values['VWAP']
        
        # KDJ 信号
        kdj_k = current_values.get('KDJ_K')
        kdj_d = current_values.get('KDJ_D')
        if kdj_k and kdj_d:
            if kdj_k > 80 and kdj_d > 80:
                signals.append('KDJ超买区')
            elif kdj_k < 20 and kdj_d < 20:
                signals.append('KDJ超卖区')
        
        # MACD 金叉/死叉检测
        changes = self.calc_changes(symbol, timeframe, current_values, current_price)
        macd_change = changes.get('MACD_Hist', {})
        if macd_change.get('previous') is not None:
            prev_hist = macd_change['previous']
            curr_hist = macd_change['current']
            if prev_hist < 0 and curr_hist > 0:
                signals.append('MACD金叉')
            elif prev_hist > 0 and curr_hist < 0:
                signals.append('MACD死叉')
        
        # 布林带突破
        if boll_upper and current_price > boll_upper:
            signals.append('突破布林上轨')
        elif boll_lower and current_price < boll_lower:
            signals.append('跌破布林下轨')
        
        return MarketState(
            trend=trend,
            momentum=momentum,
            volatility=volatility,
            volume_trend=volume_trend,
            key_levels=key_levels,
            signals=signals
        )
    
    def clear(self, symbol: str = None, timeframe: str = None):
        """清空历史"""
        if symbol and timeframe:
            key = self._get_key(symbol, timeframe)
            if key in self._history:
                del self._history[key]
        else:
            self._history.clear()


# 全局状态追踪器
_state_tracker: Optional[StateTracker] = None


def get_state_tracker() -> StateTracker:
    """获取全局状态追踪器"""
    global _state_tracker
    if _state_tracker is None:
        _state_tracker = StateTracker()
    return _state_tracker


def format_with_changes(
    latest_values: Dict[str, Any],
    symbol: str,
    timeframe: str,
    current_price: float,
    ohlcv: List[List] = None
) -> str:
    """
    格式化指标，包含变化量和状态摘要
    
    这是 format_for_ai 的增强版，输出更紧凑且包含变化信息
    """
    tracker = get_state_tracker()
    
    # 计算变化量
    changes = tracker.calc_changes(symbol, timeframe, latest_values, current_price)
    
    # 分析市场状态
    state = tracker.analyze_market_state(
        symbol, timeframe, latest_values, current_price, ohlcv or []
    )
    
    # 记录当前状态（供下次比较）
    tracker.record(symbol, timeframe, latest_values, current_price)
    
    lines = []
    
    # 价格变化
    price_info = changes.get('_price', {})
    price_dir = price_info.get('direction', 'new')
    price_chg = price_info.get('change_pct', 0)
    
    if price_dir == 'new':
        lines.append(f"价格: {current_price:.2f}")
    else:
        arrow = '↑' if price_dir == 'up' else ('↓' if price_dir == 'down' else '→')
        lines.append(f"价格: {current_price:.2f} {arrow}{abs(price_chg):.2f}%")
    
    # 市场状态摘要
    trend_cn = {'up': '上涨', 'down': '下跌', 'sideways': '横盘'}
    momentum_cn = {
        'strong': '强势', 'weak': '弱势', 'neutral': '中性',
        'bullish': '偏多', 'bearish': '偏空',
        'overbought': '超买', 'oversold': '超卖'
    }
    vol_cn = {'high': '高', 'normal': '正常', 'low': '低'}
    
    lines.append(f"状态: {trend_cn.get(state.trend, state.trend)} | {momentum_cn.get(state.momentum, state.momentum)} | 波动{vol_cn.get(state.volatility, state.volatility)}")
    
    # 关键指标（带变化量）
    def fmt_change(name: str, decimals: int = 2) -> str:
        info = changes.get(name, {})
        val = info.get('current')
        if val is None:
            return ''
        
        direction = info.get('direction', 'new')
        chg = info.get('change', 0)
        
        # 首次记录或无变化
        if direction == 'new' or direction == 'flat':
            return f"{val:.{decimals}f}"
        
        arrow = '↑' if direction == 'up' else '↓'
        return f"{val:.{decimals}f}({arrow}{abs(chg):.{decimals}f})"
    
    # RSI
    rsi_str = fmt_change('RSI')
    if rsi_str:
        lines.append(f"RSI: {rsi_str}")
    
    # MACD
    macd_str = fmt_change('MACD', 4)
    macd_hist_str = fmt_change('MACD_Hist', 4)
    if macd_str:
        lines.append(f"MACD: {macd_str} | Hist: {macd_hist_str}")
    
    # KDJ
    kdj_k = fmt_change('KDJ_K')
    kdj_d = fmt_change('KDJ_D')
    if kdj_k:
        lines.append(f"KDJ: K={kdj_k} D={kdj_d}")
    
    # 布林带位置
    boll_upper = latest_values.get('BOLL_Upper')
    boll_lower = latest_values.get('BOLL_Lower')
    if boll_upper and boll_lower:
        boll_pos = (current_price - boll_lower) / (boll_upper - boll_lower) * 100
        lines.append(f"BOLL位置: {boll_pos:.0f}% (上:{boll_upper:.2f} 下:{boll_lower:.2f})")
    
    # ATR
    atr = latest_values.get('ATR')
    if atr:
        atr_pct = atr / current_price * 100
        lines.append(f"ATR: {atr:.2f} ({atr_pct:.2f}%)")
    
    # 关键信号
    if state.signals:
        lines.append(f"信号: {', '.join(state.signals)}")
    
    return '\n'.join(lines)


def format_candles_summary(ohlcv: List[List], count: int = 10) -> str:
    """
    K线摘要（替代原始 OHLCV 数据）
    
    分析最近 K 线的形态，输出摘要而非原始数据
    """
    if not ohlcv or len(ohlcv) < 3:
        return "K线数据不足"
    
    recent = ohlcv[-count:] if len(ohlcv) >= count else ohlcv
    
    # 统计阳线/阴线
    bullish = 0
    bearish = 0
    doji = 0
    
    for candle in recent:
        o, h, l, c = candle[1], candle[2], candle[3], candle[4]
        body = abs(c - o)
        range_hl = h - l
        
        if range_hl > 0 and body / range_hl < 0.1:
            doji += 1
        elif c > o:
            bullish += 1
        else:
            bearish += 1
    
    # 计算价格变化
    first_close = recent[0][4]
    last_close = recent[-1][4]
    change_pct = (last_close - first_close) / first_close * 100
    
    # 计算波动范围
    highs = [c[2] for c in recent]
    lows = [c[3] for c in recent]
    range_pct = (max(highs) - min(lows)) / first_close * 100
    
    # 判断形态
    pattern = ""
    if bullish >= count * 0.7:
        pattern = "连续上涨"
    elif bearish >= count * 0.7:
        pattern = "连续下跌"
    elif doji >= count * 0.3:
        pattern = "多十字星(犹豫)"
    elif bullish > bearish:
        pattern = "偏多震荡"
    elif bearish > bullish:
        pattern = "偏空震荡"
    else:
        pattern = "横盘整理"
    
    return f"近{len(recent)}根K线: {pattern} | 涨跌:{change_pct:+.2f}% | 振幅:{range_pct:.2f}% | 阳:{bullish} 阴:{bearish}"


def calculate_indicators(ohlcv: List[List]) -> Dict[str, Any]:
    """
    计算所有指标（供 benchmark 使用）
    
    这是一个兼容函数，保持与原有代码的兼容性
    """
    from ai.ai_indicators import IndicatorCalculator
    
    indicators = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR']
    return IndicatorCalculator.get_latest_values(indicators, ohlcv)
