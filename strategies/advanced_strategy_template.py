# -*- coding: utf-8 -*-
"""
高级策略模板 - 支持动态止盈止损、分批平仓、追踪止损

此模板提供完整的风控框架，用户只需实现信号逻辑。
所有参数都可通过前端配置覆盖。

⚠️ 风险提示：
- 本策略仅供学习和研究使用
- 加密货币交易存在高风险，可能导致全部本金损失
- 过去的表现不代表未来收益
- 请根据自身风险承受能力谨慎决策
"""
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum

# 尝试导入加速指标模块
try:
    from ai_indicators import calc_ema, calc_rsi, calc_atr, calc_macd
    USE_ACCELERATED = True
except ImportError:
    import pandas_ta as ta
    USE_ACCELERATED = False


class PositionSide(Enum):
    """持仓方向"""
    NONE = "none"
    LONG = "long"
    SHORT = "short"


@dataclass
class RiskConfig:
    """风控配置 - 所有参数可通过前端覆盖"""
    # 仓位管理
    risk_per_trade: float = 0.008  # 每笔交易最大风险 = 账户权益的 0.8%
    max_leverage: int = 5          # 杠杆上限
    high_volatility_leverage: int = 2  # 高波动时杠杆
    volatility_threshold: float = 0.015  # ATR/Price > 1.5% 视为高波动
    
    # 止损配置
    atr_sl_multiplier: float = 2.2  # 止损 = ATR * 2.2
    min_sl_pct: float = 0.005       # 最小止损距离 0.5%
    max_sl_pct: float = 0.05        # 最大止损距离 5%
    
    # 分批止盈配置
    tp1_r_multiple: float = 1.0     # TP1: +1R
    tp1_close_pct: float = 0.30     # TP1 平仓 30%
    tp2_r_multiple: float = 2.0     # TP2: +2R
    tp2_close_pct: float = 0.30     # TP2 平仓 30%
    tp3_trailing_atr: float = 2.0   # TP3: ATR*2 追踪止损
    
    # 时间过滤 (UTC)
    allowed_hours: List[tuple] = field(default_factory=lambda: [(0, 8), (12, 20)])
    
    # 防抖配置
    cooldown_bars: int = 3          # 进场后 N 根 K 线内禁止加仓
    post_sl_cooldown: int = 10      # 止损后 N 根 K 线内需要更强信号
    enhanced_volume_mult: float = 1.4  # 止损后重入需要的成交量倍数


@dataclass
class PositionState:
    """持仓状态"""
    side: PositionSide = PositionSide.NONE
    entry_price: float = 0.0
    entry_time: datetime = None
    entry_bar_index: int = 0
    initial_qty: float = 0.0
    remaining_qty: float = 0.0
    
    # 止损止盈
    stop_loss: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    trailing_stop: float = 0.0
    trailing_stop_active: bool = False
    
    # 分批平仓状态
    tp1_hit: bool = False
    tp2_hit: bool = False
    
    # ATR 快照（入场时）
    entry_atr: float = 0.0
    
    # 冷却状态
    last_sl_bar_index: int = -100  # 上次止损的 bar index
    bars_since_entry: int = 0


class AdvancedStrategyBase:
    """
    高级策略基类
    
    提供完整的风控框架：
    - 动态 ATR 止损
    - 分批止盈 (TP1/TP2/TP3)
    - 追踪止损
    - 时间过滤
    - 新闻过滤（可插拔）
    - 防抖机制
    
    子类只需实现 check_entry_signal() 方法
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        
        # 加载风控配置（支持前端覆盖）
        self.risk = RiskConfig()
        self._load_config_overrides()
        
        # 持仓状态
        self.position = PositionState()
        
        # 当前 bar index（用于冷却计算）
        self.current_bar_index = 0
        
        # 新闻过滤函数（外部注入）
        self._news_filter: Optional[Callable[[datetime], bool]] = None
        
        # 账户信息（由外部更新）
        self.equity = 10000.0  # 默认权益
    
    def _load_config_overrides(self):
        """从 config 加载参数覆盖"""
        if not self.config:
            return
        
        # 风控参数覆盖
        risk_config = self.config.get('risk', {})
        for key, value in risk_config.items():
            if hasattr(self.risk, key):
                setattr(self.risk, key, value)
        
        # 兼容旧格式 - 直接从 config 读取
        if 'risk_per_trade' in self.config:
            self.risk.risk_per_trade = self.config['risk_per_trade']
        if 'max_leverage' in self.config:
            self.risk.max_leverage = self.config['max_leverage']
        if 'high_volatility_leverage' in self.config:
            self.risk.high_volatility_leverage = self.config['high_volatility_leverage']
        if 'atr_sl_multiplier' in self.config:
            self.risk.atr_sl_multiplier = self.config['atr_sl_multiplier']
        if 'min_sl_pct' in self.config:
            self.risk.min_sl_pct = self.config['min_sl_pct']
        if 'max_sl_pct' in self.config:
            self.risk.max_sl_pct = self.config['max_sl_pct']
        
        # 止盈参数
        if 'tp1_r_multiple' in self.config:
            self.risk.tp1_r_multiple = self.config['tp1_r_multiple']
        if 'tp1_close_pct' in self.config:
            self.risk.tp1_close_pct = self.config['tp1_close_pct']
        if 'tp2_r_multiple' in self.config:
            self.risk.tp2_r_multiple = self.config['tp2_r_multiple']
        if 'tp2_close_pct' in self.config:
            self.risk.tp2_close_pct = self.config['tp2_close_pct']
        if 'tp3_trailing_atr' in self.config:
            self.risk.tp3_trailing_atr = self.config['tp3_trailing_atr']
        
        # 冷却参数
        if 'cooldown_bars' in self.config:
            self.risk.cooldown_bars = self.config['cooldown_bars']
        if 'post_sl_cooldown' in self.config:
            self.risk.post_sl_cooldown = self.config['post_sl_cooldown']
        
        # 时间过滤参数
        enable_time_filter = self.config.get('enable_time_filter', True)
        if not enable_time_filter:
            # 禁用时间过滤 - 设置为全天可交易
            self.risk.allowed_hours = [(0, 24)]
        else:
            # 从配置构建交易时段
            start1 = self.config.get('trading_start_hour_1', 0)
            end1 = self.config.get('trading_end_hour_1', 8)
            start2 = self.config.get('trading_start_hour_2', 12)
            end2 = self.config.get('trading_end_hour_2', 20)
            self.risk.allowed_hours = [(start1, end1), (start2, end2)]
    
    def set_news_filter(self, filter_func: Callable[[datetime], bool]):
        """设置新闻过滤函数"""
        self._news_filter = filter_func
    
    def set_equity(self, equity: float):
        """更新账户权益"""
        self.equity = equity
    
    def _is_high_impact_news(self, now: datetime) -> bool:
        """检查是否有高影响新闻"""
        if self._news_filter is None:
            return False
        return self._news_filter(now)
    
    def _is_allowed_trading_time(self, now: datetime) -> bool:
        """检查是否在允许交易的时间段"""
        hour = now.hour
        for start, end in self.risk.allowed_hours:
            if start <= hour < end:
                return True
        return False
    
    def _calculate_indicators(self, ohlcv) -> Dict[str, np.ndarray]:
        """计算技术指标 - 子类可覆盖"""
        close = ohlcv['close'].values if hasattr(ohlcv['close'], 'values') else np.array(ohlcv['close'])
        high = ohlcv['high'].values if hasattr(ohlcv['high'], 'values') else np.array(ohlcv['high'])
        low = ohlcv['low'].values if hasattr(ohlcv['low'], 'values') else np.array(ohlcv['low'])
        volume = ohlcv['volume'].values if hasattr(ohlcv['volume'], 'values') else np.array(ohlcv['volume'])
        
        if USE_ACCELERATED:
            ema12 = calc_ema(close, 12)
            ema26 = calc_ema(close, 26)
            ema200 = calc_ema(close, 200)
            rsi = calc_rsi(close, 14)
            atr = calc_atr(high, low, close, 14)
        else:
            ema12 = ta.ema(ohlcv['close'], length=12).values
            ema26 = ta.ema(ohlcv['close'], length=26).values
            ema200 = ta.ema(ohlcv['close'], length=200).values
            rsi = ta.rsi(ohlcv['close'], length=14).values
            atr_df = ta.atr(ohlcv['high'], ohlcv['low'], ohlcv['close'], length=14)
            atr = atr_df.values if atr_df is not None else np.zeros(len(close))
        
        # 成交量均线
        vol_sma = np.convolve(volume, np.ones(20)/20, mode='same')
        
        return {
            'close': close,
            'high': high,
            'low': low,
            'volume': volume,
            'ema12': ema12,
            'ema26': ema26,
            'ema200': ema200,
            'rsi': rsi,
            'atr': atr,
            'vol_sma': vol_sma,
        }
    
    def _calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """
        基于止损距离计算仓位大小
        
        公式: PositionSize = (Equity × Risk%) / |Entry - StopLoss|
        """
        sl_distance = abs(entry_price - stop_loss)
        if sl_distance < 1e-8:
            return 0.0
        
        risk_amount = self.equity * self.risk.risk_per_trade
        position_size = risk_amount / sl_distance
        
        return position_size
    
    def _calculate_leverage(self, atr: float, price: float) -> int:
        """根据波动率计算杠杆"""
        volatility = atr / price if price > 0 else 0
        
        if volatility > self.risk.volatility_threshold:
            return self.risk.high_volatility_leverage
        return self.risk.max_leverage
    
    def _calculate_stop_loss(self, entry_price: float, atr: float, side: PositionSide) -> float:
        """计算动态止损价格"""
        sl_distance = atr * self.risk.atr_sl_multiplier
        
        # 限制止损距离在合理范围内
        min_distance = entry_price * self.risk.min_sl_pct
        max_distance = entry_price * self.risk.max_sl_pct
        sl_distance = max(min_distance, min(sl_distance, max_distance))
        
        if side == PositionSide.LONG:
            return entry_price - sl_distance
        else:
            return entry_price + sl_distance
    
    def _calculate_take_profits(self, entry_price: float, stop_loss: float, side: PositionSide) -> tuple:
        """计算分批止盈价格"""
        r = abs(entry_price - stop_loss)  # 1R = 止损距离
        
        if side == PositionSide.LONG:
            tp1 = entry_price + r * self.risk.tp1_r_multiple
            tp2 = entry_price + r * self.risk.tp2_r_multiple
        else:
            tp1 = entry_price - r * self.risk.tp1_r_multiple
            tp2 = entry_price - r * self.risk.tp2_r_multiple
        
        return tp1, tp2
    
    def _update_trailing_stop(self, current_price: float, atr: float):
        """更新追踪止损"""
        if not self.position.trailing_stop_active:
            return
        
        trailing_distance = atr * self.risk.tp3_trailing_atr
        
        if self.position.side == PositionSide.LONG:
            new_trailing = current_price - trailing_distance
            if new_trailing > self.position.trailing_stop:
                self.position.trailing_stop = new_trailing
        else:
            new_trailing = current_price + trailing_distance
            if new_trailing < self.position.trailing_stop or self.position.trailing_stop == 0:
                self.position.trailing_stop = new_trailing

    def check_entry_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> Optional[PositionSide]:
        """
        检查入场信号 - 子类必须实现
        
        Args:
            indicators: 技术指标字典
            bar_index: 当前 K 线索引
        
        Returns:
            PositionSide.LONG / PositionSide.SHORT / None
        """
        raise NotImplementedError("子类必须实现 check_entry_signal 方法")
    
    def check_exit_signal(self, indicators: Dict[str, np.ndarray], bar_index: int) -> bool:
        """
        检查反向信号平仓 - 子类可覆盖
        
        Returns:
            True 表示应该平仓
        """
        return False
    
    def _check_stop_loss_hit(self, current_price: float) -> bool:
        """检查是否触发止损"""
        if self.position.side == PositionSide.NONE:
            return False
        
        if self.position.side == PositionSide.LONG:
            return current_price <= self.position.stop_loss
        else:
            return current_price >= self.position.stop_loss
    
    def _check_trailing_stop_hit(self, current_price: float) -> bool:
        """检查是否触发追踪止损"""
        if not self.position.trailing_stop_active:
            return False
        
        if self.position.side == PositionSide.LONG:
            return current_price <= self.position.trailing_stop
        else:
            return current_price >= self.position.trailing_stop
    
    def _check_take_profit_hit(self, current_price: float) -> Optional[str]:
        """检查是否触发止盈"""
        if self.position.side == PositionSide.NONE:
            return None
        
        if self.position.side == PositionSide.LONG:
            if not self.position.tp1_hit and current_price >= self.position.take_profit_1:
                return "TP1"
            if not self.position.tp2_hit and current_price >= self.position.take_profit_2:
                return "TP2"
        else:
            if not self.position.tp1_hit and current_price <= self.position.take_profit_1:
                return "TP1"
            if not self.position.tp2_hit and current_price <= self.position.take_profit_2:
                return "TP2"
        
        return None
    
    def _is_in_cooldown(self) -> bool:
        """检查是否在冷却期"""
        return self.position.bars_since_entry < self.risk.cooldown_bars
    
    def _needs_enhanced_signal(self) -> bool:
        """检查是否需要增强信号（止损后重入）"""
        bars_since_sl = self.current_bar_index - self.position.last_sl_bar_index
        return bars_since_sl < self.risk.post_sl_cooldown
    
    def _open_position(self, side: PositionSide, entry_price: float, atr: float, now: datetime):
        """开仓"""
        stop_loss = self._calculate_stop_loss(entry_price, atr, side)
        tp1, tp2 = self._calculate_take_profits(entry_price, stop_loss, side)
        position_size = self._calculate_position_size(entry_price, stop_loss)
        leverage = self._calculate_leverage(atr, entry_price)
        
        self.position = PositionState(
            side=side,
            entry_price=entry_price,
            entry_time=now,
            entry_bar_index=self.current_bar_index,
            initial_qty=position_size,
            remaining_qty=position_size,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            entry_atr=atr,
            bars_since_entry=0,
        )
        
        return {
            "action": "LONG" if side == PositionSide.LONG else "SHORT",
            "type": "CUSTOM",
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": tp1,
            "take_profit_2": tp2,
            "position_size_usd": position_size * entry_price,
            "leverage": leverage,
            "reason": f"入场信号触发，SL={stop_loss:.2f}, TP1={tp1:.2f}, TP2={tp2:.2f}"
        }
    
    def _close_position(self, reason: str, close_pct: float = 1.0) -> Dict[str, Any]:
        """平仓"""
        close_qty = self.position.remaining_qty * close_pct
        self.position.remaining_qty -= close_qty
        
        action = "CLOSE_LONG" if self.position.side == PositionSide.LONG else "CLOSE_SHORT"
        
        if self.position.remaining_qty <= 0:
            # 完全平仓
            self.position = PositionState()
        
        return {
            "action": action,
            "type": "CUSTOM",
            "close_pct": close_pct,
            "reason": reason
        }
    
    def analyze(self, ohlcv, symbol: str, timeframe: str = '15m') -> Dict[str, Any]:
        """
        主分析函数 - 返回交易信号
        
        Args:
            ohlcv: pandas DataFrame，包含 open, high, low, close, volume
            symbol: 交易对
            timeframe: 时间周期
        
        Returns:
            交易信号字典
        """
        if ohlcv is None or len(ohlcv) < 200:
            return {"action": "HOLD", "type": "CUSTOM", "reason": "数据不足（需要至少200根K线）"}
        
        # 更新 bar index
        self.current_bar_index += 1
        if self.position.side != PositionSide.NONE:
            self.position.bars_since_entry += 1
        
        # 计算指标
        indicators = self._calculate_indicators(ohlcv)
        
        current_price = indicators['close'][-1]
        current_atr = indicators['atr'][-1]
        
        # 获取当前时间
        if hasattr(ohlcv.index, 'to_pydatetime'):
            now = ohlcv.index[-1].to_pydatetime()
        else:
            now = datetime.now(timezone.utc)
        
        # === 1. 检查止损 ===
        if self._check_stop_loss_hit(current_price):
            self.position.last_sl_bar_index = self.current_bar_index
            return self._close_position("触发止损", 1.0)
        
        # === 2. 检查追踪止损 ===
        if self._check_trailing_stop_hit(current_price):
            return self._close_position("触发追踪止损", 1.0)
        
        # === 3. 检查分批止盈 ===
        tp_hit = self._check_take_profit_hit(current_price)
        if tp_hit == "TP1" and not self.position.tp1_hit:
            self.position.tp1_hit = True
            return self._close_position(f"TP1 止盈 (+{self.risk.tp1_r_multiple}R)", self.risk.tp1_close_pct)
        
        if tp_hit == "TP2" and not self.position.tp2_hit:
            self.position.tp2_hit = True
            # 激活追踪止损
            self.position.trailing_stop_active = True
            self.position.trailing_stop = self.position.stop_loss  # 初始化为入场止损
            return self._close_position(f"TP2 止盈 (+{self.risk.tp2_r_multiple}R)，激活追踪止损", self.risk.tp2_close_pct)
        
        # === 4. 更新追踪止损 ===
        if self.position.trailing_stop_active:
            self._update_trailing_stop(current_price, current_atr)
        
        # === 5. 检查反向信号平仓 ===
        if self.position.side != PositionSide.NONE:
            if self.check_exit_signal(indicators, self.current_bar_index):
                return self._close_position("反向信号平仓", 1.0)
        
        # === 6. 新闻过滤 ===
        if self._is_high_impact_news(now):
            if self.position.side != PositionSide.NONE:
                # 有持仓时，降低仓位一半
                return self._close_position("高影响新闻，减仓50%", 0.5)
            return {"action": "HOLD", "type": "CUSTOM", "reason": "高影响新闻期间，禁止开仓"}
        
        # === 7. 时间过滤 ===
        if not self._is_allowed_trading_time(now):
            return {"action": "HOLD", "type": "CUSTOM", "reason": f"非交易时段 (UTC {now.hour}:00)"}
        
        # === 8. 检查入场信号 ===
        if self.position.side == PositionSide.NONE:
            # 检查是否需要增强信号
            if self._needs_enhanced_signal():
                # 提高成交量阈值
                vol_threshold = self.risk.enhanced_volume_mult
            else:
                vol_threshold = 1.2
            
            # 检查入场信号
            signal = self.check_entry_signal(indicators, self.current_bar_index)
            
            if signal is not None:
                # 验证成交量
                if indicators['volume'][-1] > indicators['vol_sma'][-1] * vol_threshold:
                    return self._open_position(signal, current_price, current_atr, now)
                else:
                    return {"action": "HOLD", "type": "CUSTOM", "reason": "成交量不足，等待确认"}
        
        # === 9. 冷却期检查 ===
        if self._is_in_cooldown():
            return {"action": "HOLD", "type": "CUSTOM", "reason": f"冷却期 ({self.position.bars_since_entry}/{self.risk.cooldown_bars})"}
        
        return {"action": "HOLD", "type": "CUSTOM", "reason": "等待信号"}
    
    def run_analysis_with_data(self, symbol: str, preloaded_data: Dict[str, Any], due_tfs: list) -> list:
        """
        数据解耦版本：使用预加载的K线数据进行分析
        
        兼容交易引擎的调用方式，将 analyze() 的结果转换为引擎期望的格式。
        
        参数：
        - symbol: 交易对（如 "BTC/USDT"）
        - preloaded_data: 字典 {tf: DataFrame} 预加载的K线数据
        - due_tfs: 需要分析的周期列表
        
        返回：
        [
            {
                "tf": "15m",
                "action": "LONG",
                "type": "CUSTOM",
                "rsi": 50.0,
                "signal": {...},
                "reason": "...",
                "candle_time": Timestamp(...)
            },
            ...
        ]
        """
        scan_results = []
        
        for tf in due_tfs:
            # 使用预加载的数据
            df = preloaded_data.get(tf)
            
            if df is None or len(df) < 200:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "DATA_ERROR",
                    "rsi": 50.0,
                    "signal": None,
                    "reason": "数据不足",
                    "candle_time": None
                })
                continue
            
            try:
                # 调用 analyze 方法
                result = self.analyze(df, symbol, tf)
                
                # 获取 RSI 值（如果指标已计算）
                rsi_val = 50.0
                try:
                    indicators = self._calculate_indicators(df)
                    if 'rsi' in indicators and len(indicators['rsi']) > 0:
                        rsi_val = float(indicators['rsi'][-1])
                        if np.isnan(rsi_val):
                            rsi_val = 50.0
                except:
                    pass
                
                # 获取K线时间戳
                candle_time = None
                if len(df) >= 2:
                    if 'timestamp' in df.columns:
                        candle_time = df.iloc[-2]['timestamp']
                    elif hasattr(df.index, 'to_pydatetime'):
                        candle_time = df.index[-2]
                
                scan_results.append({
                    "tf": tf,
                    "action": result.get("action", "HOLD"),
                    "type": result.get("type", "CUSTOM"),
                    "rsi": rsi_val,
                    "signal": result,
                    "reason": result.get("reason", ""),
                    "candle_time": candle_time
                })
                
            except Exception as e:
                scan_results.append({
                    "tf": tf,
                    "action": "ERROR",
                    "type": "ANALYSIS_ERROR",
                    "rsi": 50.0,
                    "signal": None,
                    "reason": f"分析异常: {str(e)}",
                    "candle_time": None
                })
        
        return scan_results
    
    def get_position_info(self) -> Dict[str, Any]:
        """获取当前持仓信息（用于前端显示）"""
        if self.position.side == PositionSide.NONE:
            return {"has_position": False}
        
        return {
            "has_position": True,
            "side": self.position.side.value,
            "entry_price": self.position.entry_price,
            "stop_loss": self.position.stop_loss,
            "take_profit_1": self.position.take_profit_1,
            "take_profit_2": self.position.take_profit_2,
            "trailing_stop": self.position.trailing_stop if self.position.trailing_stop_active else None,
            "tp1_hit": self.position.tp1_hit,
            "tp2_hit": self.position.tp2_hit,
            "remaining_pct": self.position.remaining_qty / self.position.initial_qty if self.position.initial_qty > 0 else 0,
        }
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        返回配置参数的 schema（用于前端动态生成配置界面）
        """
        return {
            "risk_per_trade": {
                "type": "float",
                "label": "单笔风险比例",
                "default": 0.008,
                "min": 0.001,
                "max": 0.05,
                "step": 0.001,
                "description": "每笔交易最大风险占账户权益的比例"
            },
            "max_leverage": {
                "type": "int",
                "label": "最大杠杆",
                "default": 5,
                "min": 1,
                "max": 20,
                "description": "正常情况下的最大杠杆倍数"
            },
            "high_volatility_leverage": {
                "type": "int",
                "label": "高波动杠杆",
                "default": 2,
                "min": 1,
                "max": 10,
                "description": "高波动时自动降低到此杠杆"
            },
            "atr_sl_multiplier": {
                "type": "float",
                "label": "ATR止损倍数",
                "default": 2.2,
                "min": 1.0,
                "max": 5.0,
                "step": 0.1,
                "description": "止损距离 = ATR × 此倍数"
            },
            "min_sl_pct": {
                "type": "float",
                "label": "最小止损%",
                "default": 0.3,
                "min": 0.1,
                "max": 1.0,
                "step": 0.1,
                "description": "止损距离最小百分比"
            },
            "max_sl_pct": {
                "type": "float",
                "label": "最大止损%",
                "default": 2.0,
                "min": 0.5,
                "max": 5.0,
                "step": 0.1,
                "description": "止损距离最大百分比"
            },
            "tp1_r_multiple": {
                "type": "float",
                "label": "TP1 R倍数",
                "default": 1.0,
                "min": 0.5,
                "max": 3.0,
                "step": 0.1,
                "description": "第一止盈目标的R倍数"
            },
            "tp1_close_pct": {
                "type": "float",
                "label": "TP1 平仓比例",
                "default": 0.30,
                "min": 0.1,
                "max": 0.5,
                "step": 0.05,
                "description": "TP1触发时平仓的比例"
            },
            "tp2_r_multiple": {
                "type": "float",
                "label": "TP2 R倍数",
                "default": 2.0,
                "min": 1.0,
                "max": 5.0,
                "step": 0.1,
                "description": "第二止盈目标的R倍数"
            },
            "tp2_close_pct": {
                "type": "float",
                "label": "TP2 平仓比例",
                "default": 0.30,
                "min": 0.1,
                "max": 0.5,
                "step": 0.05,
                "description": "TP2触发时平仓的比例"
            },
            "tp3_trailing_atr": {
                "type": "float",
                "label": "追踪止损ATR倍数",
                "default": 2.0,
                "min": 1.0,
                "max": 4.0,
                "step": 0.1,
                "description": "TP2后追踪止损距离 = ATR × 此倍数"
            },
            "cooldown_bars": {
                "type": "int",
                "label": "入场冷却K线数",
                "default": 3,
                "min": 1,
                "max": 10,
                "description": "入场后禁止加仓的K线数"
            },
            "post_sl_cooldown": {
                "type": "int",
                "label": "止损后冷却K线数",
                "default": 10,
                "min": 5,
                "max": 20,
                "description": "止损后需要更强信号的K线数"
            },
            "trading_start_hour_1": {
                "type": "int",
                "label": "交易时段1开始(UTC)",
                "default": 0,
                "min": 0,
                "max": 23,
                "description": "第一个交易时段开始小时(UTC)"
            },
            "trading_end_hour_1": {
                "type": "int",
                "label": "交易时段1结束(UTC)",
                "default": 8,
                "min": 0,
                "max": 24,
                "description": "第一个交易时段结束小时(UTC)"
            },
            "trading_start_hour_2": {
                "type": "int",
                "label": "交易时段2开始(UTC)",
                "default": 12,
                "min": 0,
                "max": 23,
                "description": "第二个交易时段开始小时(UTC)"
            },
            "trading_end_hour_2": {
                "type": "int",
                "label": "交易时段2结束(UTC)",
                "default": 20,
                "min": 0,
                "max": 24,
                "description": "第二个交易时段结束小时(UTC)"
            },
            "enable_time_filter": {
                "type": "bool",
                "label": "启用时间过滤",
                "default": True,
                "description": "是否启用交易时段过滤"
            },
        }
