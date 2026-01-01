# -*- coding: utf-8 -*-
"""
回测引擎 - 支持历史数据回测和性能分析

功能：
1. 获取历史 K 线数据
2. 模拟策略执行
3. 计算回测指标（收益率、最大回撤、夏普比率等）
4. 生成交易记录和权益曲线

⚠️ 风险提示：
- 回测结果不代表未来收益
- 过度拟合可能导致实盘表现不佳
- 请谨慎使用回测结果做决策
"""
import os
import time
import ccxt
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BacktestConfig:
    """回测配置"""
    symbol: str = "BTC/USDT:USDT"
    timeframe: str = "15m"
    start_date: datetime = None
    end_date: datetime = None
    initial_capital: float = 10000.0
    commission_rate: float = 0.0006  # 手续费率 0.06%
    slippage_rate: float = 0.0001   # 滑点 0.01%
    leverage: int = 5
    position_pct: float = 2.0       # 仓位比例 %


@dataclass
class Trade:
    """交易记录"""
    entry_time: datetime
    exit_time: datetime = None
    side: str = ""  # LONG / SHORT
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    commission: float = 0.0
    reason: str = ""
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    symbol: str = ""
    timeframe: str = ""
    start_date: str = ""
    end_date: str = ""
    total_bars: int = 0
    
    # 收益指标
    initial_capital: float = 10000.0
    final_capital: float = 10000.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    annualized_return: float = 0.0
    
    # 风险指标
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    
    # 交易统计
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_duration: float = 0.0  # 小时
    
    # 最大连续
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    # 详细数据
    trades: List[Trade] = field(default_factory=list)
    equity_curve: List[Dict] = field(default_factory=list)
    
    # 错误信息
    error: str = ""


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self):
        self.exchange = None
        self._init_exchange()
    
    def _init_exchange(self):
        """初始化交易所连接"""
        try:
            # 确保环境变量已加载
            load_dotenv(override=True)
            
            # 获取代理配置（与 market_api.py 保持一致）
            http_proxy = os.getenv('HTTP_PROXY') or os.getenv('http_proxy')
            https_proxy = os.getenv('HTTPS_PROXY') or os.getenv('https_proxy')
            
            print(f"🔍 [回测引擎] 检测代理配置...")
            print(f"   HTTP_PROXY: {http_proxy or '未设置'}")
            print(f"   HTTPS_PROXY: {https_proxy or '未设置'}")
            
            # 如果环境变量没有代理，尝试自动检测
            if not https_proxy:
                try:
                    from utils.env_validator import EnvironmentValidator
                    proxy_config = EnvironmentValidator.detect_system_proxy()
                    https_proxy = proxy_config.get('https_proxy') or proxy_config.get('http_proxy')
                    http_proxy = proxy_config.get('http_proxy') or https_proxy
                    if https_proxy:
                        print(f"🌐 [回测引擎] 自动检测到系统代理: {https_proxy}")
                except Exception as e:
                    print(f"   自动检测代理失败: {e}")
            
            config = {
                'enableRateLimit': True,
                'timeout': 30000,
                'options': {
                    'defaultType': 'swap',
                }
            }
            
            # 添加代理支持
            if https_proxy:
                config['proxies'] = {
                    'http': http_proxy or https_proxy,
                    'https': https_proxy
                }
                print(f"✅ [回测引擎] 使用代理: {https_proxy}")
            else:
                print("⚠️ [回测引擎] 未检测到代理，如果无法获取数据请配置 HTTP_PROXY 环境变量")
            
            self.exchange = ccxt.okx(config)
            print("✅ [回测引擎] OKX 交易所连接初始化成功")
            
        except Exception as e:
            import traceback
            print(f"❌ [回测引擎] 交易所连接失败: {e}")
            print(traceback.format_exc())
            self.exchange = None
    
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
        }
        return tf_map.get(timeframe, 15 * 60 * 1000)
    
    def fetch_historical_data(
        self, 
        symbol: str, 
        timeframe: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> pd.DataFrame:
        """
        获取历史 K 线数据
        
        Args:
            symbol: 交易对
            timeframe: 时间周期
            start_date: 开始时间
            end_date: 结束时间
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        if not self.exchange:
            raise Exception("交易所未连接，请检查网络和代理配置")
        
        # 标准化 symbol 格式
        original_symbol = symbol
        if '/' not in symbol:
            symbol = f"{symbol}/USDT:USDT"
        elif ':' not in symbol:
            symbol = f"{symbol}:USDT"
        
        tf_ms = self._get_timeframe_ms(timeframe)
        start_ts = int(start_date.timestamp() * 1000)
        end_ts = int(end_date.timestamp() * 1000)
        
        all_candles = []
        current_since = start_ts
        page_size = 300  # OKX 单次最多 300 根
        retry_count = 0
        max_retries = 3
        
        print(f"📊 [回测引擎] 获取历史数据: {symbol} {timeframe}")
        print(f"   时间范围: {start_date.strftime('%Y-%m-%d %H:%M')} ~ {end_date.strftime('%Y-%m-%d %H:%M')}")
        
        while current_since < end_ts:
            try:
                data = self.exchange.fetch_ohlcv(
                    symbol, timeframe,
                    since=current_since,
                    limit=page_size
                )
                
                if not data:
                    if retry_count < max_retries:
                        retry_count += 1
                        print(f"\n   ⚠️ 未获取到数据，重试 {retry_count}/{max_retries}...")
                        time.sleep(1)
                        continue
                    break
                
                retry_count = 0  # 重置重试计数
                
                for candle in data:
                    if candle[0] <= end_ts:
                        all_candles.append(candle)
                
                # 更新 since
                max_ts = max(c[0] for c in data)
                if max_ts <= current_since:
                    break
                current_since = max_ts + 1
                
                # 进度显示
                progress = (current_since - start_ts) / (end_ts - start_ts) * 100
                print(f"   进度: {min(progress, 100):.1f}% ({len(all_candles)} 根K线)", end='\r')
                
                # 避免限流
                time.sleep(0.1)
                
            except ccxt.NetworkError as e:
                print(f"\n   ❌ 网络错误: {e}")
                print(f"   请检查：1) 网络连接 2) 代理配置 (HTTP_PROXY 环境变量)")
                if retry_count < max_retries:
                    retry_count += 1
                    print(f"   重试 {retry_count}/{max_retries}...")
                    time.sleep(2)
                    continue
                break
            except ccxt.ExchangeError as e:
                print(f"\n   ❌ 交易所错误: {e}")
                if "symbol" in str(e).lower():
                    print(f"   交易对 {symbol} 可能不存在，请检查输入")
                break
            except Exception as e:
                print(f"\n   ⚠️ 获取数据出错: {type(e).__name__}: {e}")
                if retry_count < max_retries:
                    retry_count += 1
                    time.sleep(1)
                    continue
                break
        
        print(f"\n   ✅ 共获取 {len(all_candles)} 根K线")
        
        if not all_candles:
            print(f"   ❌ 未能获取任何数据，可能原因：")
            print(f"      1. 网络无法连接 OKX（需要代理）")
            print(f"      2. 交易对 {symbol} 不存在")
            print(f"      3. 时间范围内没有数据")
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset=['timestamp']).sort_values('timestamp').reset_index(drop=True)
        
        return df
    
    def run_backtest(
        self, 
        strategy_code: str,
        config: BacktestConfig,
        progress_callback=None
    ) -> BacktestResult:
        """
        运行回测
        
        Args:
            strategy_code: 策略代码字符串
            config: 回测配置
            progress_callback: 进度回调函数 (current, total, message)
        
        Returns:
            BacktestResult
        """
        result = BacktestResult(
            symbol=config.symbol,
            timeframe=config.timeframe,
            initial_capital=config.initial_capital,
        )
        
        try:
            # 1. 获取历史数据
            if progress_callback:
                progress_callback(0, 100, "正在获取历史数据...")
            
            df = self.fetch_historical_data(
                config.symbol,
                config.timeframe,
                config.start_date,
                config.end_date
            )
            
            if df.empty or len(df) < 200:
                result.error = f"数据不足，需要至少 200 根 K 线，实际获取 {len(df)} 根"
                return result
            
            result.total_bars = len(df)
            result.start_date = df['timestamp'].iloc[0].strftime('%Y-%m-%d %H:%M')
            result.end_date = df['timestamp'].iloc[-1].strftime('%Y-%m-%d %H:%M')
            
            # 2. 实例化策略
            if progress_callback:
                progress_callback(10, 100, "正在加载策略...")
            
            strategy = self._instantiate_strategy(strategy_code, config)
            if strategy is None:
                result.error = "策略实例化失败"
                return result
            
            # 3. 运行回测
            if progress_callback:
                progress_callback(20, 100, "正在运行回测...")
            
            trades, equity_curve = self._simulate_trading(
                strategy, df, config, progress_callback
            )
            
            # 4. 计算指标
            if progress_callback:
                progress_callback(90, 100, "正在计算指标...")
            
            result = self._calculate_metrics(trades, equity_curve, config, result)
            
            if progress_callback:
                progress_callback(100, 100, "回测完成")
            
            return result
            
        except Exception as e:
            import traceback
            result.error = f"回测失败: {str(e)}\n{traceback.format_exc()}"
            return result
    
    def _instantiate_strategy(self, strategy_code: str, config: BacktestConfig):
        """实例化策略"""
        try:
            # 创建执行环境
            exec_globals = {
                '__builtins__': __builtins__,
                'np': np,
                'pd': pd,
            }
            
            # 添加必要的导入
            try:
                from strategies.advanced_strategy_template import AdvancedStrategyBase, PositionSide, RiskConfig
                exec_globals['AdvancedStrategyBase'] = AdvancedStrategyBase
                exec_globals['PositionSide'] = PositionSide
                exec_globals['RiskConfig'] = RiskConfig
            except ImportError:
                pass
            
            try:
                from ai.ai_indicators import calc_ema, calc_rsi, calc_atr, calc_macd
                exec_globals['calc_ema'] = calc_ema
                exec_globals['calc_rsi'] = calc_rsi
                exec_globals['calc_atr'] = calc_atr
                exec_globals['calc_macd'] = calc_macd
            except ImportError:
                pass
            
            try:
                import pandas_ta as ta
                exec_globals['ta'] = ta
            except ImportError:
                pass
            
            # 添加 numba 支持（内置策略需要）
            try:
                from numba import njit
                exec_globals['njit'] = njit
            except ImportError:
                # 如果没有 numba，提供一个空装饰器
                def njit(*args, **kwargs):
                    def decorator(func):
                        return func
                    if len(args) == 1 and callable(args[0]):
                        return args[0]
                    return decorator
                exec_globals['njit'] = njit
            
            # 执行策略代码
            exec(strategy_code, exec_globals)
            
            # 查找策略类（优先 Wrapper，然后是 TradingStrategy）
            strategy_class = None
            for name, obj in exec_globals.items():
                if isinstance(obj, type) and name not in ['AdvancedStrategyBase', 'PositionSide', 'RiskConfig']:
                    if 'Wrapper' in name:
                        strategy_class = obj
                        break
                    elif 'TradingStrategy' in name or 'Strategy' in name:
                        if strategy_class is None:
                            strategy_class = obj
                    elif strategy_class is None:
                        strategy_class = obj
            
            if strategy_class is None:
                return None
            
            # 实例化
            strategy_config = {
                'position_pct': config.position_pct,
                'leverage': config.leverage,
            }
            
            try:
                return strategy_class(strategy_config)
            except TypeError:
                # 有些策略不接受参数
                return strategy_class()
            
        except Exception as e:
            import traceback
            print(f"策略实例化失败: {e}")
            print(traceback.format_exc())
            return None
    
    def _simulate_trading(
        self, 
        strategy, 
        df: pd.DataFrame, 
        config: BacktestConfig,
        progress_callback=None
    ) -> Tuple[List[Trade], List[Dict]]:
        """模拟交易 - 支持简单策略和高级策略"""
        trades = []
        equity_curve = []
        
        capital = config.initial_capital
        position = None  # 当前持仓（简单策略用）
        
        total_bars = len(df)
        start_idx = 200  # 需要足够的历史数据计算指标
        
        # 检测策略接口类型
        has_analyze = hasattr(strategy, 'analyze')
        has_check_signals = hasattr(strategy, 'check_signals')
        has_calculate_indicators = hasattr(strategy, 'calculate_indicators')
        
        # 检测是否为高级策略（有内部持仓管理）
        is_advanced_strategy = hasattr(strategy, 'position') and hasattr(strategy, 'set_equity')
        
        if is_advanced_strategy:
            # 高级策略：设置初始权益，禁用时间过滤（回测不需要）
            strategy.set_equity(capital)
            if hasattr(strategy, 'risk'):
                strategy.risk.allowed_hours = [(0, 24)]  # 全天可交易
            print(f"📊 [回测] 检测到高级策略，使用策略内置风控")
        
        # 对于内置策略，需要先计算指标
        df_with_indicators = df.copy()
        if has_calculate_indicators and has_check_signals:
            try:
                df_with_indicators = strategy.calculate_indicators(df.copy())
            except Exception as e:
                print(f"计算指标失败: {e}")
        
        for i in range(start_idx, total_bars):
            # 进度更新
            if progress_callback and i % 100 == 0:
                progress = 20 + (i - start_idx) / (total_bars - start_idx) * 70
                progress_callback(int(progress), 100, f"回测进度: {i}/{total_bars}")
            
            # 获取当前数据
            current_df = df.iloc[:i+1].copy()
            current_df_with_ind = df_with_indicators.iloc[:i+1].copy() if has_calculate_indicators else current_df
            current_price = df.iloc[i]['close']
            current_time = df.iloc[i]['timestamp']
            
            # 记录权益
            unrealized_pnl = 0
            if position:
                if position['side'] == 'LONG':
                    unrealized_pnl = (current_price - position['entry_price']) * position['quantity']
                else:
                    unrealized_pnl = (position['entry_price'] - current_price) * position['quantity']
            
            equity_curve.append({
                'timestamp': current_time,
                'equity': capital + unrealized_pnl,
                'capital': capital,
                'unrealized_pnl': unrealized_pnl,
            })
            
            # 更新高级策略的权益
            if is_advanced_strategy:
                strategy.set_equity(capital + unrealized_pnl)
            
            # 调用策略
            signal = None
            try:
                if has_analyze:
                    # 自定义策略使用 analyze 方法
                    signal = strategy.analyze(current_df, config.symbol, config.timeframe)
                elif has_check_signals:
                    # 内置策略使用 check_signals 方法
                    signal = strategy.check_signals(current_df_with_ind, config.timeframe)
                else:
                    continue
            except Exception as e:
                continue
            
            if not signal:
                continue
            
            action = signal.get('action', 'HOLD')
            
            # 处理信号
            if position is None:
                # 无持仓，检查开仓信号
                if action in ['LONG', 'SHORT']:
                    # 高级策略使用信号中的仓位大小
                    if is_advanced_strategy and 'position_size_usd' in signal:
                        position_value = signal['position_size_usd']
                        leverage = signal.get('leverage', config.leverage)
                    else:
                        # 简单策略使用配置的仓位
                        position_value = capital * (config.position_pct / 100) * config.leverage
                        leverage = config.leverage
                    
                    quantity = position_value / current_price
                    
                    # 计算手续费
                    commission = position_value * config.commission_rate
                    
                    # 计算滑点
                    slippage = current_price * config.slippage_rate
                    entry_price = current_price + slippage if action == 'LONG' else current_price - slippage
                    
                    # 保存止损止盈信息（高级策略）
                    stop_loss = signal.get('stop_loss', 0)
                    take_profit_1 = signal.get('take_profit_1', 0)
                    take_profit_2 = signal.get('take_profit_2', 0)
                    
                    position = {
                        'side': action,
                        'entry_price': entry_price,
                        'entry_time': current_time,
                        'quantity': quantity,
                        'initial_quantity': quantity,
                        'commission': commission,
                        'reason': signal.get('reason', ''),
                        'stop_loss': stop_loss,
                        'take_profit_1': take_profit_1,
                        'take_profit_2': take_profit_2,
                        'tp1_hit': False,
                        'tp2_hit': False,
                    }
                    
                    capital -= commission
            else:
                # 有持仓，检查平仓信号
                should_close = False
                close_pct = 1.0  # 默认全部平仓
                exit_reason = ""
                
                # 检查平仓信号
                if action in ['CLOSE_LONG', 'CLOSE_SHORT']:
                    if (position['side'] == 'LONG' and action == 'CLOSE_LONG') or \
                       (position['side'] == 'SHORT' and action == 'CLOSE_SHORT'):
                        should_close = True
                        close_pct = signal.get('close_pct', 1.0)
                        exit_reason = signal.get('reason', '平仓信号')
                
                # 反向信号平仓
                elif (position['side'] == 'LONG' and action == 'SHORT') or \
                     (position['side'] == 'SHORT' and action == 'LONG'):
                    should_close = True
                    exit_reason = signal.get('reason', '反向信号')
                
                if should_close:
                    # 计算平仓数量
                    close_quantity = position['quantity'] * close_pct
                    
                    # 计算滑点
                    slippage = current_price * config.slippage_rate
                    exit_price = current_price - slippage if position['side'] == 'LONG' else current_price + slippage
                    
                    # 计算盈亏
                    if position['side'] == 'LONG':
                        pnl = (exit_price - position['entry_price']) * close_quantity
                    else:
                        pnl = (position['entry_price'] - exit_price) * close_quantity
                    
                    # 扣除平仓手续费
                    exit_commission = close_quantity * exit_price * config.commission_rate
                    pnl -= exit_commission
                    
                    pnl_pct = pnl / (position['entry_price'] * close_quantity) * 100
                    
                    # 记录交易
                    trade = Trade(
                        entry_time=position['entry_time'],
                        exit_time=current_time,
                        side=position['side'],
                        entry_price=position['entry_price'],
                        exit_price=exit_price,
                        quantity=close_quantity,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        commission=position['commission'] * close_pct + exit_commission,
                        reason=position['reason'],
                        exit_reason=exit_reason,
                    )
                    trades.append(trade)
                    
                    capital += pnl
                    
                    # 更新剩余仓位
                    position['quantity'] -= close_quantity
                    position['commission'] *= (1 - close_pct)
                    
                    if position['quantity'] <= 0.0001:
                        position = None
        
        # 如果还有持仓，强制平仓
        if position:
            current_price = df.iloc[-1]['close']
            current_time = df.iloc[-1]['timestamp']
            
            if position['side'] == 'LONG':
                pnl = (current_price - position['entry_price']) * position['quantity']
            else:
                pnl = (position['entry_price'] - current_price) * position['quantity']
            
            exit_commission = position['quantity'] * current_price * config.commission_rate
            pnl -= exit_commission
            pnl_pct = pnl / (position['entry_price'] * position['quantity']) * 100
            
            trade = Trade(
                entry_time=position['entry_time'],
                exit_time=current_time,
                side=position['side'],
                entry_price=position['entry_price'],
                exit_price=current_price,
                quantity=position['quantity'],
                pnl=pnl,
                pnl_pct=pnl_pct,
                commission=position['commission'] + exit_commission,
                reason=position['reason'],
                exit_reason="回测结束强制平仓",
            )
            trades.append(trade)
            capital += pnl
        
        return trades, equity_curve
    
    def _calculate_metrics(
        self, 
        trades: List[Trade], 
        equity_curve: List[Dict],
        config: BacktestConfig,
        result: BacktestResult
    ) -> BacktestResult:
        """计算回测指标"""
        result.trades = trades
        result.equity_curve = equity_curve
        
        if not equity_curve:
            return result
        
        # 最终资金
        result.final_capital = equity_curve[-1]['equity']
        result.total_return = result.final_capital - result.initial_capital
        result.total_return_pct = (result.total_return / result.initial_capital) * 100
        
        # 年化收益率
        if len(equity_curve) > 1:
            start_time = equity_curve[0]['timestamp']
            end_time = equity_curve[-1]['timestamp']
            days = (end_time - start_time).total_seconds() / 86400
            if days > 0:
                result.annualized_return = ((result.final_capital / result.initial_capital) ** (365 / days) - 1) * 100
        
        # 最大回撤
        equity_values = [e['equity'] for e in equity_curve]
        peak = equity_values[0]
        max_dd = 0
        max_dd_pct = 0
        
        for equity in equity_values:
            if equity > peak:
                peak = equity
            dd = peak - equity
            dd_pct = dd / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
                max_dd_pct = dd_pct
        
        result.max_drawdown = max_dd
        result.max_drawdown_pct = max_dd_pct
        
        # 夏普比率（假设无风险利率为 0）
        if len(equity_curve) > 1:
            returns = []
            for i in range(1, len(equity_curve)):
                prev_equity = equity_curve[i-1]['equity']
                curr_equity = equity_curve[i]['equity']
                if prev_equity > 0:
                    returns.append((curr_equity - prev_equity) / prev_equity)
            
            if returns:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                if std_return > 0:
                    # 年化夏普比率（假设每天 96 个 15 分钟 K 线）
                    tf_per_year = 365 * 24 * 60 / self._get_timeframe_minutes(config.timeframe)
                    result.sharpe_ratio = avg_return / std_return * np.sqrt(tf_per_year)
                
                # Sortino 比率（只考虑下行波动）
                negative_returns = [r for r in returns if r < 0]
                if negative_returns:
                    downside_std = np.std(negative_returns)
                    if downside_std > 0:
                        result.sortino_ratio = avg_return / downside_std * np.sqrt(tf_per_year)
        
        # Calmar 比率
        if result.max_drawdown_pct > 0:
            result.calmar_ratio = result.annualized_return / result.max_drawdown_pct
        
        # 交易统计
        result.total_trades = len(trades)
        
        if trades:
            winning_trades = [t for t in trades if t.pnl > 0]
            losing_trades = [t for t in trades if t.pnl <= 0]
            
            result.winning_trades = len(winning_trades)
            result.losing_trades = len(losing_trades)
            result.win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
            
            if winning_trades:
                result.avg_win = np.mean([t.pnl for t in winning_trades])
            if losing_trades:
                result.avg_loss = abs(np.mean([t.pnl for t in losing_trades]))
            
            # 盈亏比
            total_profit = sum(t.pnl for t in winning_trades) if winning_trades else 0
            total_loss = abs(sum(t.pnl for t in losing_trades)) if losing_trades else 0
            if total_loss > 0:
                result.profit_factor = total_profit / total_loss
            
            # 平均持仓时间
            durations = []
            for t in trades:
                if t.exit_time and t.entry_time:
                    duration = (t.exit_time - t.entry_time).total_seconds() / 3600
                    durations.append(duration)
            if durations:
                result.avg_trade_duration = np.mean(durations)
            
            # 最大连续盈亏
            result.max_consecutive_wins = self._max_consecutive(trades, True)
            result.max_consecutive_losses = self._max_consecutive(trades, False)
        
        return result
    
    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """获取时间周期的分钟数"""
        tf_map = {
            '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '2h': 120, '4h': 240, '6h': 360, '12h': 720, '1d': 1440,
        }
        return tf_map.get(timeframe, 15)
    
    def _max_consecutive(self, trades: List[Trade], is_win: bool) -> int:
        """计算最大连续盈/亏次数"""
        max_count = 0
        current_count = 0
        
        for trade in trades:
            if (is_win and trade.pnl > 0) or (not is_win and trade.pnl <= 0):
                current_count += 1
                max_count = max(max_count, current_count)
            else:
                current_count = 0
        
        return max_count


# 全局实例
_backtest_engine: Optional[BacktestEngine] = None


def get_backtest_engine() -> BacktestEngine:
    """获取回测引擎单例"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine
