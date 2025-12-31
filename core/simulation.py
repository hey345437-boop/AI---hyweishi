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
# simulation.py - 模拟交易与回测引擎（修复版）
# 修复回测崩溃问题 + 添加状态持久化功能

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import threading
import json
import os
import sqlite3
from pathlib import Path


class SimulationEngine:
    """
    实时模拟账户引擎（增强版）
    在实盘测试模式下模拟真实交易，实时计算资金曲线
    
    新增功能：
    - 状态持久化：保存/加载余额、净值、历史数据
    - 数据库同步：从数据库读取持仓，计算实时浮盈
    """
    
    def __init__(self, initial_balance: float = 200.0, state_file: str = "simulation_state.json", db_path: str = "quant_system.db"):
        """
        初始化模拟账户

        参数：
        - initial_balance: 初始余额（USDT），默认200
        - state_file: 状态文件路径
        - db_path: 数据库路径（用于持久化曲线数据）
        """
        self.state_file = state_file
        self.db_path = db_path
        self.username = "admin"  # 硬编码为默认用户
        self.initial_balance = initial_balance
        self.lock = threading.Lock()  # 线程安全

        # 尝试从数据库加载之前的状态
        if os.path.exists(db_path):
            try:
                self.load_state_from_db(db_path, "admin")
                print(f" 模拟账户已从数据库恢复 | 余额: ${self.balance:.2f} | 净值: ${self.equity:.2f}")
            except Exception as e:
                print(f"⚠️ 从数据库加载状态失败，尝试从JSON文件加载: {e}")
                if os.path.exists(state_file):
                    try:
                        self.load_state(state_file)
                        print(f" 模拟账户已从JSON文件恢复 | 余额: ${self.balance:.2f} | 净值: ${self.equity:.2f}")
                    except Exception as e2:
                        print(f"⚠️ JSON加载失败，使用默认值: {e2}")
                        self._initialize_default()
                else:
                    self._initialize_default()
        else:
            # 数据库不存在，尝试从JSON加载
            if os.path.exists(state_file):
                try:
                    self.load_state(state_file)
                    print(f" 模拟账户已从JSON文件恢复 | 余额: ${self.balance:.2f} | 净值: ${self.equity:.2f}")
                except Exception as e:
                    print(f"⚠️ JSON加载失败，使用默认值: {e}")
                    self._initialize_default()
            else:
                self._initialize_default()
    
    def _initialize_default(self):
        """初始化为默认状态"""
        self.balance = self.initial_balance  # 可用余额（已实现盈亏）
        self.equity = self.initial_balance   # 净值（余额 + 未实现盈亏）
        self.history = []  # [(timestamp, equity), ...]
        
        # 性能统计
        self.total_trades = 0
        self.winning_trades = 0
        self.total_pnl = 0.0
        self.max_equity = self.initial_balance
        self.max_drawdown = 0.0
        
        print(f" 模拟账户初始化完成 | 初始余额: ${self.initial_balance:.2f}")
    
    def load_state(self, filepath: str):
        """
         从 JSON文件加载状态
        
        参数：
        - filepath: 状态文件路径
        """
        with self.lock:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.initial_balance = data.get('initial_balance', 200.0)
            self.balance = data.get('balance', self.initial_balance)
            self.equity = data.get('equity', self.initial_balance)
            
            # 恢复历史数据（转换时间戳）
            history_raw = data.get('history', [])
            self.history = [(datetime.fromisoformat(item[0]), item[1]) for item in history_raw]
            
            # 恢复统计数据
            self.total_trades = data.get('total_trades', 0)
            self.winning_trades = data.get('winning_trades', 0)
            self.total_pnl = data.get('total_pnl', 0.0)
            self.max_equity = data.get('max_equity', self.initial_balance)
            self.max_drawdown = data.get('max_drawdown', 0.0)
    
    def save_state(self, filepath: str = None):
        """
         保存状态到 JSON文件
        
        参数：
        - filepath: 状态文件路径（默认使用 self.state_file）
        """
        if filepath is None:
            filepath = self.state_file
        
        with self.lock:
            # 准备数据
            data = {
                'initial_balance': self.initial_balance,
                'balance': self.balance,
                'equity': self.equity,
                'history': [(ts.isoformat(), eq) for ts, eq in self.history],
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'total_pnl': self.total_pnl,
                'max_equity': self.max_equity,
                'max_drawdown': self.max_drawdown
            }
            
            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_state_from_db(self, db_path: str, username: str = "admin"):
        """
         从数据库加载持久化的曲线和统计数据

        参数：
        - db_path: 数据库路径
        - username: 用户名（默认为 "admin"）
        """
        with self.lock:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()

            try:
                # 先创建表（如果不存在）
                c.execute('''CREATE TABLE IF NOT EXISTS simulation_history (
                    username TEXT,
                    timestamp TEXT,
                    equity REAL,
                    balance REAL,
                    total_pnl REAL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    max_equity REAL,
                    max_drawdown REAL,
                    PRIMARY KEY (username, timestamp)
                )''')

                # 获取该用户的最新记录
                c.execute(
                    "SELECT * FROM simulation_history WHERE username=? ORDER BY timestamp DESC LIMIT 1",
                    (username,)
                )
                row = c.fetchone()

                if row:
                    # 恢复最新的状态
                    self.balance = float(row['balance'])
                    self.equity = float(row['equity'])
                    self.total_pnl = float(row['total_pnl'])
                    self.total_trades = int(row['total_trades'])
                    self.winning_trades = int(row['winning_trades'])
                    self.max_equity = float(row['max_equity'])
                    self.max_drawdown = float(row['max_drawdown'])

                    # 加载历史数据（最近1000条）
                    c.execute(
                        "SELECT timestamp, equity FROM simulation_history WHERE username=? ORDER BY timestamp ASC LIMIT 1000",
                        (username,)
                    )
                    self.history = [(datetime.fromisoformat(r['timestamp']), float(r['equity'])) for r in c.fetchall()]
                else:
                    self._initialize_default()
            finally:
                conn.close()
    
    def save_state_to_db(self, db_path: str = None, username: str = "admin"):
        """
         保存状态到数据库

        参数：
        - db_path: 数据库路径（默认使用 self.db_path）
        - username: 用户名（默认为 "admin"）
        """
        if db_path is None:
            db_path = self.db_path

        with self.lock:
            try:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()

                # 创建表（如果不存在）
                c.execute('''CREATE TABLE IF NOT EXISTS simulation_history (
                    username TEXT,
                    timestamp TEXT,
                    equity REAL,
                    balance REAL,
                    total_pnl REAL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    max_equity REAL,
                    max_drawdown REAL,
                    PRIMARY KEY (username, timestamp)
                )''')

                # 保存当前状态（只保存最新时间点）
                timestamp_now = datetime.now().isoformat()
                c.execute(
                    """INSERT OR REPLACE INTO simulation_history
                       (username, timestamp, equity, balance, total_pnl, total_trades, winning_trades, max_equity, max_drawdown)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("admin", timestamp_now, self.equity, self.balance, self.total_pnl,
                     self.total_trades, self.winning_trades, self.max_equity, self.max_drawdown)
                )

                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ 保存到数据库失败: {e}")
    
    def update(self, current_positions: Dict, current_prices: Dict) -> float:
        """
         核心方法：更新账户状态（轻量级，可频繁调用）
        在 auto_trading_engine 的空闲时间调用（每分钟15秒和45秒）
        
        参数：
        - current_positions:  从数据库/Session读取的持仓字典
          格式: {symbol: {'side': 'LONG', 'size': 100, 'entry_price': 50000}}
        - current_prices: 当前价格字典 {symbol: current_price}
        
        返回：
        - 当前净值
        """
        with self.lock:
            # 计算未实现盈亏（基于数据库持仓）
            unrealized_pnl = 0.0
            
            for symbol, pos in current_positions.items():
                if symbol not in current_prices:
                    continue
                
                current_price = current_prices[symbol]
                entry_price = pos.get('entry_price', current_price)
                size = pos.get('size', 0)
                side = pos.get('side', 'LONG')
                
                # 计算盈亏（考虑多空方向）
                if side == 'LONG':
                    pnl = (current_price - entry_price) / entry_price * size
                else:  # SHORT
                    pnl = (entry_price - current_price) / entry_price * size
                
                unrealized_pnl += pnl
            
            # 更新净值：Equity = Balance (已实现余额) + Unrealized PnL (浮盈)
            self.equity = self.balance + unrealized_pnl
            
            # 记录历史
            timestamp = datetime.now()
            self.history.append((timestamp, self.equity))
            
            # 更新最大净值和回撤
            if self.equity > self.max_equity:
                self.max_equity = self.equity
            
            drawdown = (self.max_equity - self.equity) / self.max_equity * 100 if self.max_equity > 0 else 0
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown
            
            # 每10条记录保存一次数据库（优化性能）
            if len(self.history) % 10 == 0:
                self.save_state_to_db()
            
            return self.equity
    
    def realize_pnl(self, amount: float, reason: str = "平仓") -> float:
        """
         实现盈亏（平仓时调用）
        将未实现盈亏转为已实现，加入余额
        
        参数：
        - amount: 已实现盈亏（USDT）
        - reason: 平仓原因（日志用）
        
        返回：
        - 更新后的余额
        """
        with self.lock:
            # 将盈亏加入余额
            self.balance += amount
            self.equity = self.balance  # 平仓后暂无持仓，净值 = 余额
            self.total_pnl += amount
            
            # 更新统计
            self.total_trades += 1
            if amount > 0:
                self.winning_trades += 1
            
            # 记录历史
            timestamp = datetime.now()
            self.history.append((timestamp, self.equity))
            
            # 立即保存状态到数据库和JSON文件
            self.save_state_to_db()
            self.save_state()
            
            print(f"   {reason}盈亏已实现 | 金额: ${amount:+.2f} | 新余额: ${self.balance:.2f}")
            return self.balance
    
    def open_position(self, symbol: str, side: str, entry_price: float, size: float) -> bool:
        """
        开仓（记录持仓信息）- 已废弃，仅保留以兼容旧代码
        
         注意：模拟引擎不再自己维护持仓，而是直接读取数据库中的 open_positions
        """
        print(f"⚠️ open_position() 已废弃，请直接调用 update() 方法传入数据库持仓")
        return True
    
    def get_history_dataframe(self) -> pd.DataFrame:
        """
        获取历史数据（用于UI绘图）
        
        返回：
        - DataFrame with columns: ['timestamp', 'equity']
        """
        with self.lock:
            if not self.history:
                return pd.DataFrame(columns=['timestamp', 'equity'])
            
            df = pd.DataFrame(self.history, columns=['timestamp', 'equity'])
            return df
    
    def get_stats(self) -> Dict:
        """
        获取统计数据
        
        返回：
        - 包含各项统计指标的字典
        """
        with self.lock:
            win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
            total_return = (self.equity - self.initial_balance) / self.initial_balance * 100
            
            return {
                'initial_balance': self.initial_balance,
                'current_balance': self.balance,
                'current_equity': self.equity,
                'total_return': total_return,
                'total_pnl': self.total_pnl,
                'total_trades': self.total_trades,
                'winning_trades': self.winning_trades,
                'win_rate': win_rate,
                'max_drawdown': self.max_drawdown
            }
    
    def reset(self):
        """重置账户到初始状态"""
        with self.lock:
            self.balance = self.initial_balance
            self.equity = self.initial_balance
            self.history = []
            self.total_trades = 0
            self.winning_trades = 0
            self.total_pnl = 0.0
            self.max_equity = self.initial_balance
            self.max_drawdown = 0.0
            
            # 清空数据库中的simulation_history表
            try:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                c.execute("DELETE FROM simulation_history WHERE username = ?", ("admin",))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ 清空simulation_history失败: {e}")
            
            # 保存重置后的状态
            self.save_state_to_db()
            self.save_state()
            
            print(f"🔄 模拟账户已重置 | 余额: ${self.initial_balance:.2f}")


class BacktestEngine:
    """
    历史回测引擎（增强版）
    完全遵循实盘交易逻辑：盈利反手、对冲机制、风控检查
    支持任意日期范围回测
    """
    
    def __init__(self, strategy_engine, initial_capital: float = 1000.0, leverage: int = 50,
                 main_signal_pct: float = 0.05, sub_signal_pct: float = 0.025):
        """
        初始化回测引擎
        
        参数：
        - strategy_engine: 策略引擎实例
        - initial_capital: 初始资金
        - leverage: 杠杆倍数
        - main_signal_pct: 主信号仓位占比（杠杆后）
        - sub_signal_pct: 次信号仓位占比（杠杆后）
        """
        self.strategy = strategy_engine
        self.initial_capital = initial_capital
        self.leverage = leverage
        self.main_signal_pct = main_signal_pct
        self.sub_signal_pct = sub_signal_pct
        
        # 回测状态（完全模拟实盘）
        self.balance = initial_capital
        self.equity = initial_capital
        
        # 持仓管理（模拟实盘的 open_positions 和 hedge_positions）
        self.main_position = None  # {'side': 'LONG', 'entry_price': 50000, 'size': 100, 'entry_time': timestamp}
        self.hedge_positions = []  # [{'side': 'SHORT', ...}, ...]
        
        # 历史记录
        self.equity_curve = []  # [(timestamp, equity), ...]
        self.trade_list = []    # [{'entry_time', 'entry_price', 'exit_time', 'exit_price', 'side', 'pnl', 'pnl_pct', 'reason'}, ...]
        
        # 性能指标
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_equity = initial_capital
        self.max_drawdown = 0.0
        
        # K线去重记录
        self.last_signal_candle = {}  # {(action, tf): candle_time}
    
    def run(self, df: pd.DataFrame, symbol: str = "BTC/USDT", 
            start_date: str = None, end_date: str = None,
            timeframes: List[str] = ['3m', '5m', '15m', '30m', '1h'],
            fetch_klines_func = None, api_key: str = None, secret: str = None, 
            password: str = None, is_sandbox: bool = False) -> Dict:
        """
        运行回测（增强版）
        
        参数：
        - df: 备用OHLCV数据（如果fetch_klines_func为None则使用）
        - symbol: 交易对名称
        - start_date: 开始日期（格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）
        - end_date: 结束日期（格式: 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS'）
        - timeframes: 要回测的时间周期列表
        - fetch_klines_func: K线获取函数（用于从交易所拉取数据）
        - api_key, secret, password, is_sandbox: API凭证
        
        返回：
        - 回测结果字典
        """
        print(f"\n{'='*60}")
        print(f"🔬 开始回测 | {symbol}")
        print(f" 周期: {timeframes}")
        print(f"{'='*60}\n")
        
        # 重置状态
        self._reset()
        
        # 模拟实盘逻辑：对每个时间周期都从交易所拉取完整数据
        tf_data = {}  # {tf: df_with_indicators}
        
        for tf in timeframes:
            try:
                # 直接从交易所拉取该周期的完整数据
                if fetch_klines_func and api_key:
                    print(f"📥 正在拉取 {tf} 周期数据...")
                    
                    # 根据日期范围计算需要拉取的K线数量
                    if start_date and end_date:
                        # 计算日期跨度
                        import pandas as pd
                        start_dt = pd.to_datetime(start_date)
                        end_dt = pd.to_datetime(end_date)
                        days_diff = (end_dt - start_dt).days
                        
                        # 根据周期计算需要的K线数量（加200根缓冲用于指标计算）
                        tf_minutes = self._tf_to_minutes(tf)
                        required_bars = int((days_diff * 24 * 60) / tf_minutes) + 200
                        
                        print(f"   预计需要 {required_bars} 根K线，分批拉取...")
                    else:
                        # 没有指定日期，拉取足够的历史数据（至少1000根）
                        required_bars = 1000
                    
                    # 分批拉取数据（交易所API限制每次最多1000根）
                    all_data = []
                    batch_size = 1000
                    fetched_count = 0
                    
                    # 最多拉取3批（3000根），避免API限流
                    max_batches = min(3, (required_bars // batch_size) + 1)
                    
                    for batch in range(max_batches):
                        try:
                            import time
                            if batch > 0:
                                time.sleep(1)  # 批次间延迟，避免限流
                            
                            # 拉取一批数据
                            df_batch = fetch_klines_func(api_key, secret, password, symbol, tf, batch_size, is_sandbox)
                            
                            if df_batch is not None and len(df_batch) > 0:
                                all_data.append(df_batch)
                                fetched_count += len(df_batch)
                                print(f"    批次 {batch+1}: 拉取 {len(df_batch)} 根K线 (累计: {fetched_count})")
                                
                                # 如果拉取的数据已经足够，提前结束
                                if fetched_count >= required_bars:
                                    break
                                
                                # 如果这批数据不足1000根，说明已经到了最早的数据
                                if len(df_batch) < batch_size:
                                    print(f"   ⚠️ 已到达最早可用数据")
                                    break
                            else:
                                break
                                
                        except Exception as e:
                            print(f"    批次 {batch+1} 拉取失败: {e}")
                            break
                    
                    # 合并所有批次的数据
                    if all_data:
                        df_tf = pd.concat(all_data, ignore_index=True)
                        # 按时间排序并去重
                        df_tf = df_tf.sort_values('timestamp').drop_duplicates(subset=['timestamp'], keep='first').reset_index(drop=True)
                        print(f"    {tf} 周期总共拉取: {len(df_tf)} 根K线")
                    else:
                        print(f"   ⚠️ {tf} 数据拉取失败，跳过")
                        continue
                    
                    # 日期过滤
                    if start_date:
                        start_dt = pd.to_datetime(start_date)
                        df_tf = df_tf[df_tf['timestamp'] >= start_dt]
                    
                    if end_date:
                        end_dt = pd.to_datetime(end_date)
                        df_tf = df_tf[df_tf['timestamp'] <= end_dt]
                    
                else:
                    # 使用提供的df进行重采样（旧逻辑，保持兼容性）
                    df_tf = self._resample_timeframe(df.copy(), tf)
                    
                    # 日期过滤
                    if start_date:
                        start_dt = pd.to_datetime(start_date)
                        df_tf = df_tf[df_tf['timestamp'] >= start_dt]
                    
                    if end_date:
                        end_dt = pd.to_datetime(end_date)
                        df_tf = df_tf[df_tf['timestamp'] <= end_dt]
                
                if len(df_tf) < 200:
                    print(f"   ⚠️ {tf} 数据不足 ({len(df_tf)} < 200)，跳过")
                    continue
                
                # 计算技术指标
                df_with_indicators = self.strategy.calculate_indicators(df_tf)
                tf_data[tf] = df_with_indicators
                print(f"    {tf} 指标计算完成 | K线数: {len(df_with_indicators)}")
                
            except Exception as e:
                print(f"    {tf} 处理失败: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        if not tf_data:
            print(" 所有周期都无法处理！")
            return self._get_results()
        
        # 显示日期范围
        all_timestamps = []
        for df_tf in tf_data.values():
            all_timestamps.extend(df_tf['timestamp'].tolist())
        
        if all_timestamps:
            min_time = min(all_timestamps)
            max_time = max(all_timestamps)
            print(f"\n📅 实际回测时间范围: {min_time} ~ {max_time}\n")
        
        print(f" 开始回测交易...\n")
        
        # 遍历每个时间点（使用最小周期的时间序列）
        base_tf = min(tf_data.keys(), key=lambda x: self._tf_to_minutes(x))
        base_df = tf_data[base_tf]
        
        # 使用 iloc[-1] 模拟实盘的激进模式（基于当前K线判断）
        for i in range(200, len(base_df)):  # 确保有足够的历史数据
            current_bar = base_df.iloc[i]
            timestamp = current_bar.get('timestamp', i)
            close_price = current_bar['close']
            
            # 检查所有周期的信号
            signals = []  # [(tf, signal, action, signal_type), ...]
            
            for tf, df_tf in tf_data.items():
                # 找到对应的时间点
                tf_idx = self._find_closest_index(df_tf, timestamp)
                if tf_idx is None or tf_idx < 3:
                    continue
                
                # 提供到当前时间点的所有数据（模拟实时数据）
                signal_df = df_tf.iloc[:tf_idx+1]
                
                try:
                    signal = self.strategy.check_signals(signal_df, timeframe=tf)
                    action = signal.get('action', 'HOLD')
                    signal_type = signal.get('type', 'NONE')
                    
                    # 过滤 TP_ORDER_BLOCK
                    if signal_type == 'TP_ORDER_BLOCK':
                        continue
                    
                    # 1m周期的顶底信号只用于止盈，不用于开仓
                    if tf == '1m' and ('TOP' in signal_type.upper() or 'BOTTOM' in signal_type.upper()):
                        continue
                    
                    if action != 'HOLD':
                        # K线去重检查
                        candle_time = signal_df.iloc[-1].get('timestamp')
                        candle_key = (action, tf)
                        
                        if candle_key in self.last_signal_candle and self.last_signal_candle[candle_key] == candle_time:
                            continue  # 同一根K线已经处理过
                        
                        self.last_signal_candle[candle_key] = candle_time
                        
                        # 分类主次信号（模拟实盘逻辑）
                        is_primary = "TREND" in signal_type.upper() and tf in ['1m', '3m', '5m']
                        weight_pct = self.main_signal_pct if is_primary else self.sub_signal_pct
                        
                        signals.append((tf, signal, action, signal_type, weight_pct))
                except Exception as e:
                    continue
            
            # 优先处理主信号
            signals.sort(key=lambda x: (x[4], self._tf_to_minutes(x[0])), reverse=True)
            
            # 更新权益曲线
            self._update_equity(timestamp, close_price)
            
            # 执行交易逻辑（完全模拟实盘）
            if signals:
                tf, signal, action, signal_type, weight_pct = signals[0]  # 取最高优先级信号
                self._execute_trading_logic(action, signal_type, close_price, timestamp, weight_pct, tf)
        
        # 最后一根K线：平掉所有持仓
        if self.main_position or self.hedge_positions:
            last_bar = base_df.iloc[-1]
            self._close_all_positions(last_bar['close'], last_bar.get('timestamp', len(base_df)), "回测结束")
        
        return self._get_results()
    
    def _execute_trading_logic(self, action: str, signal_type: str, price: float, 
                               timestamp, weight_pct: float, tf: str):
        """
         执行交易逻辑（完全模拟实盘）
        
        包括：
        1. 差值套利逻辑（主仓+对冲仓同时存在，净收益>0.5%全平）
        2. 顺势解对冲（新信号方向==主仓方向，平掉对冲仓）
        3. 对冲转正（主仓不存在，对冲仓方向==新信号，转为主仓）
        4. 盈利反手（主仓有盈利，反向信号平主仓并开反向仓）
        5. 亏损对冲（主仓亏损，反向信号开对冲仓）
        6. 无主仓开仓（无主仓且无对冲仓，直接开主仓）
        """
        # 逻辑1：差值套利（主仓+对冲仓同时存在）
        if self.main_position and self.hedge_positions:
            main_side = self.main_position['side']
            main_entry = self.main_position['entry_price']
            main_size = self.main_position['size']
            
            # 计算主仓浮盈
            if main_side == 'LONG':
                uPnL_main = (price - main_entry) / main_entry * main_size
            else:
                uPnL_main = (main_entry - price) / main_entry * main_size
            
            # 计算对冲仓总浮盈
            uPnL_hedge = 0.0
            total_hedge_size = 0.0
            for hedge_pos in self.hedge_positions:
                hedge_side = hedge_pos['side']
                hedge_entry = hedge_pos['entry_price']
                hedge_size = hedge_pos['size']
                
                if hedge_side == 'LONG':
                    uPnL_hedge += (price - hedge_entry) / hedge_entry * hedge_size
                else:
                    uPnL_hedge += (hedge_entry - price) / hedge_entry * hedge_size
                
                total_hedge_size += hedge_size
            
            # 计算净浮盈和收益率
            Net_PnL = uPnL_main + uPnL_hedge
            total_margin = (main_size + total_hedge_size) / self.leverage
            Net_ROI = Net_PnL / total_margin if total_margin > 0 else 0
            
            # 净收益率 > 0.5% 全仓逃生
            if Net_ROI > 0.005:
                print(f"\n💠 [逃生] 差值套利成功！")
                print(f"   主仓浮盈: ${uPnL_main:+.2f} | 对冲仓浮盈: ${uPnL_hedge:+.2f}")
                print(f"   净浮盈: ${Net_PnL:+.2f} | 收益率: {Net_ROI*100:.2f}% > 0.5%")
                print(f"    执行全仓平仓，整体止盈离场\n")
                
                self._close_all_positions(price, timestamp, f"套利逃生ROI={Net_ROI*100:.2f}%")
                return
        
        # 逻辑2：顺势解对冲（主仓+对冲仓同时存在，新信号方向==主仓方向）
        if self.main_position and self.hedge_positions:
            if action == self.main_position['side']:
                print(f"\n🔄 [解套] 趋势回归主方向 ({action})")
                print(f"   对冲仓数量: {len(self.hedge_positions)}个")
                print(f"    平掉所有对冲单，保留主仓\n")
                
                # 平掉所有对冲仓
                for hedge_pos in self.hedge_positions:
                    self._close_position_internal(hedge_pos, price, timestamp, f"{tf}解对冲")
                
                self.hedge_positions = []
                return  # 解对冲后跳过，不再加仓
        
        # 逻辑3：对冲转正（主仓不存在，对冲仓方向==新信号）
        if not self.main_position and self.hedge_positions:
            for hedge_pos in self.hedge_positions:
                if hedge_pos['side'] == action:
                    print(f"\n♻️ [继承] 遗留对冲单转正")
                    print(f"   对冲单方向: {hedge_pos['side']} | 入场价: ${hedge_pos['entry_price']:.4f}")
                    print(f"    标记为新主仓，跳过开新单\n")
                    
                    # 移动到主仓
                    self.main_position = hedge_pos
                    self.hedge_positions.remove(hedge_pos)
                    return  # 转正后跳过
        
        # 逻辑4：盈利反手 / 亏损对冲（有主仓，反向信号）
        if self.main_position:
            main_side = self.main_position['side']
            
            # 反向信号
            if (main_side == 'LONG' and action == 'SHORT') or (main_side == 'SHORT' and action == 'LONG'):
                main_entry = self.main_position['entry_price']
                main_size = self.main_position['size']
                
                # 计算主仓盈亏
                if main_side == 'LONG':
                    pnl = (price - main_entry) / main_entry * main_size
                else:
                    pnl = (main_entry - price) / main_entry * main_size
                
                # 盈利反手：平主仓并开反向仓
                if pnl > 0:
                    print(f"\n🔁 [反手] 盈利反手 | 主仓盈利: ${pnl:.2f}")
                    print(f"    平掉主仓 {main_side} 并开新仓 {action}\n")
                    
                    # 平掉主仓
                    self._close_position_internal(self.main_position, price, timestamp, f"{tf}盈利反手")
                    self.main_position = None
                    
                    # 开新主仓
                    self._open_position(action, price, timestamp, weight_pct)
                    return
                
                # 亏损对冲：开对冲仓（最多2个）
                else:
                    if len(self.hedge_positions) >= 2:
                        print(f"\n⚠️ [熔断] 对冲仓已达上限 (2个)，拒绝开仓")
                        return
                    
                    print(f"\n [对冲] 主仓亏损 ${pnl:.2f}，开对冲仓 {action}")
                    
                    # 开对冲仓
                    size = self.balance * weight_pct * self.leverage
                    
                    hedge_pos = {
                        'side': action,
                        'entry_price': price,
                        'size': size,
                        'entry_time': timestamp,
                        'entry_tf': tf
                    }
                    
                    self.hedge_positions.append(hedge_pos)
                    print(f"   📍 开对冲仓 | {action} @ ${price:.2f} | 仓位=${size:.2f} | [{tf}]")
                    return
        
        # 逻辑5：无主仓，直接开主仓
        if not self.main_position:
            self._open_position(action, price, timestamp, weight_pct)
    
    def _open_position(self, side: str, price: float, timestamp, weight_pct: float):
        """开主仓"""
        size = self.balance * weight_pct * self.leverage
        
        self.main_position = {
            'side': side,
            'entry_price': price,
            'size': size,
            'entry_time': timestamp
        }
        
        print(f"   📍 开主仓 | {side} @ ${price:.2f} | 仓位=${size:.2f}")
    
    def _close_position_internal(self, position: Dict, price: float, timestamp, reason: str):
        """
        关闭单个持仓（内部方法）
        用于关闭主仓或对冲仓
        """
        if position is None:
            return
        
        entry_price = position['entry_price']
        size = position['size']
        side = position['side']
        entry_time = position['entry_time']
        
        # 计算盈亏
        if side == 'LONG':
            pnl = (price - entry_price) / entry_price * size
        else:
            pnl = (entry_price - price) / entry_price * size
        
        pnl_pct = pnl / size * 100
        
        # 更新余额
        self.balance += pnl
        
        # 记录交易
        self.trade_list.append({
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': timestamp,
            'exit_price': price,
            'side': side,
            'size': size,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        })
        
        # 更新统计
        self.total_trades += 1
        if pnl > 0:
            self.winning_trades += 1
            self.total_profit += pnl
        else:
            self.losing_trades += 1
            self.total_loss += abs(pnl)
        
        print(f"    平仓 | {side} @ ${price:.2f} | 盈亏=${pnl:.2f} ({pnl_pct:+.2f}%) | {reason}")
    
    def _close_all_positions(self, price: float, timestamp, reason: str):
        """关闭所有持仓（主仓+对冲仓）"""
        # 平主仓
        if self.main_position:
            self._close_position_internal(self.main_position, price, timestamp, reason)
            self.main_position = None
        
        # 平对冲仓
        for hedge_pos in self.hedge_positions:
            self._close_position_internal(hedge_pos, price, timestamp, reason)
        
        self.hedge_positions = []
    
    def _resample_timeframe(self, df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
        """
        重采样数据到指定时间周期
        
        参数：
        - df: 原始 OHLCV 数据
        - timeframe: 目标时间周期（如 '3m', '5m', '15m', '30m', '1h'）
        
        返回：
        - 重采样后的 DataFrame
        """
        # 转换为 pandas 采样频率格式
        freq_map = {
            '1m': '1T', '3m': '3T', '5m': '5T', 
            '15m': '15T', '30m': '30T', '1h': '1H',
            '2h': '2H', '4h': '4H', '1d': '1D'
        }
        
        if timeframe not in freq_map:
            raise ValueError(f"不支持的时间周期: {timeframe}")
        
        freq = freq_map[timeframe]
        
        # 设置 timestamp 为索引
        df_resampled = df.set_index('timestamp')
        
        # 重采样
        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        df_result = df_resampled.resample(freq).agg(ohlc_dict).dropna()
        df_result = df_result.reset_index()
        
        return df_result
    
    def _find_closest_index(self, df: pd.DataFrame, target_timestamp) -> Optional[int]:
        """
        找到最接近目标时间戳的索引
        
        参数：
        - df: 带 timestamp 列的 DataFrame
        - target_timestamp: 目标时间戳
        
        返回：
        - 最接近的索引，如果找不到返回 None
        """
        try:
            # 找到小于或等于目标时间的最后一个索引
            idx = df[df['timestamp'] <= target_timestamp].index[-1]
            return idx
        except:
            return None
    
    def _tf_to_minutes(self, tf: str) -> int:
        """将时间周期转换为分钟数"""
        tf_minutes = {
            '1m': 1, '3m': 3, '5m': 5, 
            '15m': 15, '30m': 30, '1h': 60,
            '2h': 120, '4h': 240, '1d': 1440
        }
        return tf_minutes.get(tf, 999999)
    
    def _update_equity(self, timestamp, current_price: float):
        """更新权益曲线（考虑主仓+对冲仓）"""
        equity = self.balance
        
        # 计算主仓浮盈
        if self.main_position:
            entry_price = self.main_position['entry_price']
            size = self.main_position['size']
            side = self.main_position['side']
            
            if side == 'LONG':
                unrealized_pnl = (current_price - entry_price) / entry_price * size
            else:
                unrealized_pnl = (entry_price - current_price) / entry_price * size
            
            equity += unrealized_pnl
        
        # 计算对冲仓浮盈
        for hedge_pos in self.hedge_positions:
            entry_price = hedge_pos['entry_price']
            size = hedge_pos['size']
            side = hedge_pos['side']
            
            if side == 'LONG':
                unrealized_pnl = (current_price - entry_price) / entry_price * size
            else:
                unrealized_pnl = (entry_price - current_price) / entry_price * size
            
            equity += unrealized_pnl
        
        self.equity = equity
        self.equity_curve.append((timestamp, equity))
        
        # 更新最大回撤
        if equity > self.max_equity:
            self.max_equity = equity
        
        drawdown = (self.max_equity - equity) / self.max_equity * 100
        if drawdown > self.max_drawdown:
            self.max_drawdown = drawdown
    
    def _reset(self):
        """重置回测状态"""
        self.balance = self.initial_capital
        self.equity = self.initial_capital
        self.main_position = None
        self.hedge_positions = []
        self.equity_curve = []
        self.trade_list = []
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_equity = self.initial_capital
        self.max_drawdown = 0.0
        self.last_signal_candle = {}
    
    def _get_results(self) -> Dict:
        """获取回测结果"""
        total_return = (self.equity - self.initial_capital) / self.initial_capital * 100
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        profit_factor = (self.total_profit / self.total_loss) if self.total_loss > 0 else 0
        
        avg_win = (self.total_profit / self.winning_trades) if self.winning_trades > 0 else 0
        avg_loss = (self.total_loss / self.losing_trades) if self.losing_trades > 0 else 0
        
        print(f"\n{'='*60}")
        print(f" 回测结果")
        print(f"{'='*60}")
        print(f"  初始资金: ${self.initial_capital:.2f}")
        print(f"  最终权益: ${self.equity:.2f}")
        print(f"  总收益率: {total_return:+.2f}%")
        print(f"  最大回撤: {self.max_drawdown:.2f}%")
        print(f"  总交易次数: {self.total_trades}")
        print(f"  盈利次数: {self.winning_trades}")
        print(f"  亏损次数: {self.losing_trades}")
        print(f"  胜率: {win_rate:.2f}%")
        print(f"  盈亏比: {profit_factor:.2f}")
        print(f"  平均盈利: ${avg_win:.2f}")
        print(f"  平均亏损: ${avg_loss:.2f}")
        print(f"{'='*60}\n")
        
        return {
            'initial_capital': self.initial_capital,
            'final_equity': self.equity,
            'total_return': total_return,
            'max_drawdown': self.max_drawdown,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_profit': self.total_profit,
            'total_loss': self.total_loss,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'equity_curve': self.get_equity_dataframe(),
            'trade_list': self.get_trades_dataframe()
        }
    
    def get_equity_dataframe(self) -> pd.DataFrame:
        """获取权益曲线DataFrame"""
        if not self.equity_curve:
            return pd.DataFrame(columns=['timestamp', 'equity'])
        
        df = pd.DataFrame(self.equity_curve, columns=['timestamp', 'equity'])
        return df
    
    def get_trades_dataframe(self) -> pd.DataFrame:
        """获取交易列表DataFrame"""
        if not self.trade_list:
            return pd.DataFrame(columns=['entry_time', 'entry_price', 'exit_time', 
                                        'exit_price', 'side', 'pnl', 'pnl_pct', 'reason'])
        
        df = pd.DataFrame(self.trade_list)
        return df


# 工具函数：创建全局模拟引擎实例
_simulation_engine_instance = None
_simulation_engine_username = None  # 跟踪当前引擎的用户
_simulation_engine_db = None  # 跟踪当前引擎的数据库

def get_simulation_engine(initial_balance: float = 200.0, db_path: str = "quant_system.db") -> SimulationEngine:
    """
    获取全局模拟引擎实例（单例模式，数据库改变时重置）

    参数：
    - initial_balance: 初始余额
    - db_path: 数据库路径（用于持久化曲线数据）

    返回：
    - SimulationEngine实例
    """
    global _simulation_engine_instance, _simulation_engine_db

    # 如果数据库改变，重置单例实例，强制重新加载
    if db_path != _simulation_engine_db:
        _simulation_engine_instance = None
        _simulation_engine_db = db_path

    if _simulation_engine_instance is None:
        # 使用完整路径，确保状态文件保存到正确位置
        state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "simulation_state.json")
        _simulation_engine_instance = SimulationEngine(initial_balance, state_file, db_path)
        print(f" 模拟引擎初始化 | 状态文件: {state_file} | 数据库: {db_path}")
    return _simulation_engine_instance


def reset_simulation_engine():
    """重置全局模拟引擎"""
    global _simulation_engine_instance
    if _simulation_engine_instance is not None:
        _simulation_engine_instance.reset()
