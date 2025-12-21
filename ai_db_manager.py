"""
AI 决策数据库管理模块

管理 AI 决策记录和绩效统计
使用独立的 arena.db 数据库
"""

import sqlite3
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from contextlib import contextmanager
import threading
import logging

logger = logging.getLogger(__name__)

# 数据库文件路径（独立数据库）
ARENA_DB_PATH = "arena.db"

# 线程锁（SQLite 线程安全）
_db_lock = threading.Lock()

# 系统版本号（用于审计追踪）
SYSTEM_VERSION = "1.0.0"


@dataclass
class AIDecision:
    """AI 决策记录"""
    id: Optional[int] = None
    timestamp: int = 0  # 毫秒时间戳
    agent_name: str = ""  # AI 名称: deepseek, qwen, perplexity
    symbol: str = ""  # 交易对
    signal: str = ""  # BUY / SELL / HOLD
    price: float = 0.0  # 决策时价格
    confidence: float = 0.0  # 置信度 0-1
    reasoning: str = ""  # 推理过程
    thinking: str = ""  # 思考过程（DeepSeek <think> 标签内容）
    user_prompt_snapshot: str = ""  # 用户提示词快照
    indicators_snapshot: str = ""  # 指标快照 JSON
    timeframe: str = ""  # 时间周期
    latency_ms: float = 0.0  # API 延迟
    version: str = SYSTEM_VERSION  # 系统版本号（审计追踪）
    created_at: str = ""  # 创建时间（数据库自动填充）
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AIStats:
    """AI 绩效统计"""
    agent_name: str = ""
    total_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    current_streak: int = 0  # 正数=连胜，负数=连败
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_pnl: float = 0.0
    last_signal: str = ""
    last_updated: int = 0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@contextmanager
def get_db_connection(db_path: str = ARENA_DB_PATH):
    """获取数据库连接（上下文管理器）"""
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class AIDBManager:
    """AI 数据库管理器"""
    
    def __init__(self, db_path: str = ARENA_DB_PATH):
        self.db_path = db_path
        self._init_tables()
    
    def _init_tables(self):
        """初始化数据库表"""
        with _db_lock:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                
                # AI 决策记录表（含 version 字段用于审计追踪）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_decisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp INTEGER NOT NULL,
                        agent_name TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        signal TEXT NOT NULL,
                        price REAL NOT NULL,
                        confidence REAL DEFAULT 0.5,
                        reasoning TEXT,
                        thinking TEXT,
                        user_prompt_snapshot TEXT,
                        indicators_snapshot TEXT,
                        timeframe TEXT,
                        latency_ms REAL DEFAULT 0,
                        version TEXT DEFAULT '1.0.0',
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 迁移：为旧表添加 version 字段
                try:
                    cursor.execute("ALTER TABLE ai_decisions ADD COLUMN version TEXT DEFAULT '1.0.0'")
                    logger.info("[AIDBManager] 已添加 version 字段到 ai_decisions 表")
                except sqlite3.OperationalError:
                    pass  # 字段已存在
                
                # AI 绩效统计表
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_stats (
                        agent_name TEXT PRIMARY KEY,
                        total_trades INTEGER DEFAULT 0,
                        win_count INTEGER DEFAULT 0,
                        loss_count INTEGER DEFAULT 0,
                        win_rate REAL DEFAULT 0.0,
                        total_pnl REAL DEFAULT 0.0,
                        current_streak INTEGER DEFAULT 0,
                        best_trade REAL DEFAULT 0.0,
                        worst_trade REAL DEFAULT 0.0,
                        avg_pnl REAL DEFAULT 0.0,
                        last_signal TEXT DEFAULT '',
                        last_updated INTEGER DEFAULT 0
                    )
                """)
                
                # AI 虚拟持仓表（字段与主系统 SimulatedPosition 对齐）
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ai_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        agent_name TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        pos_side TEXT,
                        qty REAL NOT NULL,
                        entry_price REAL NOT NULL,
                        leverage INTEGER DEFAULT 50,
                        contract_value REAL DEFAULT 1.0,
                        signal_type TEXT,
                        created_at INTEGER NOT NULL,
                        decision_id INTEGER,
                        status TEXT DEFAULT 'open',
                        exit_price REAL,
                        exit_time INTEGER,
                        pnl REAL,
                        FOREIGN KEY (decision_id) REFERENCES ai_decisions(id)
                    )
                """)
                
                # 创建索引
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_decisions_timestamp 
                    ON ai_decisions(timestamp DESC)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_decisions_agent 
                    ON ai_decisions(agent_name, timestamp DESC)
                """)
                
                # 初始化 AI 统计记录（包含所有支持的 AI）
                all_agents = ['deepseek', 'qwen', 'perplexity', 'gpt', 'claude', 'spark_lite', 'hunyuan']
                for agent in all_agents:
                    cursor.execute("""
                        INSERT OR IGNORE INTO ai_stats (agent_name, last_updated)
                        VALUES (?, ?)
                    """, (agent, int(time.time() * 1000)))
                
                conn.commit()
                logger.info(f"[AIDBManager] 数据库初始化完成: {self.db_path}")
    
    # ========== 决策记录 ==========
    
    def save_decision(self, decision: AIDecision) -> int:
        """保存 AI 决策（含版本号用于审计追踪）"""
        with _db_lock:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ai_decisions 
                    (timestamp, agent_name, symbol, signal, price, confidence, 
                     reasoning, thinking, user_prompt_snapshot, indicators_snapshot, 
                     timeframe, latency_ms, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    decision.timestamp or int(time.time() * 1000),
                    decision.agent_name,
                    decision.symbol,
                    decision.signal,
                    decision.price,
                    decision.confidence,
                    decision.reasoning,
                    decision.thinking,
                    decision.user_prompt_snapshot,
                    decision.indicators_snapshot,
                    decision.timeframe,
                    decision.latency_ms,
                    decision.version or SYSTEM_VERSION
                ))
                conn.commit()
                decision_id = cursor.lastrowid
                
                # 更新最后信号
                cursor.execute("""
                    UPDATE ai_stats SET last_signal = ?, last_updated = ?
                    WHERE agent_name = ?
                """, (decision.signal, decision.timestamp, decision.agent_name))
                conn.commit()
                
                return decision_id
    
    def get_latest_decisions(
        self, 
        limit: int = 10, 
        agent_name: Optional[str] = None,
        symbol: Optional[str] = None,
        since_timestamp: Optional[int] = None
    ) -> List[AIDecision]:
        """获取最新决策记录"""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM ai_decisions WHERE 1=1"
            params = []
            
            if agent_name:
                query += " AND agent_name = ?"
                params.append(agent_name)
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            if since_timestamp:
                query += " AND timestamp > ?"
                params.append(since_timestamp)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [AIDecision(**dict(row)) for row in rows]
    
    def get_decisions_by_round(self, timestamp: int, tolerance_ms: int = 5000) -> List[AIDecision]:
        """获取同一轮次的所有 AI 决策"""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ai_decisions 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY agent_name
            """, (timestamp - tolerance_ms, timestamp + tolerance_ms))
            rows = cursor.fetchall()
            return [AIDecision(**dict(row)) for row in rows]
    
    def get_latest_round_timestamp(self) -> Optional[int]:
        """获取最新一轮决策的时间戳"""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM ai_decisions")
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
    
    # ========== 绩效统计 ==========
    
    def get_stats(self, agent_name: str) -> Optional[AIStats]:
        """获取 AI 绩效"""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM ai_stats WHERE agent_name = ?",
                (agent_name,)
            )
            row = cursor.fetchone()
            if row:
                return AIStats(**dict(row))
            return None
    
    def get_all_stats(self) -> List[AIStats]:
        """获取所有 AI 绩效（排行榜）"""
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ai_stats 
                ORDER BY total_pnl DESC
            """)
            rows = cursor.fetchall()
            return [AIStats(**dict(row)) for row in rows]
    
    def update_stats(self, agent_name: str, pnl: float, is_win: bool):
        """更新 AI 绩效"""
        with _db_lock:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM ai_stats WHERE agent_name = ?",
                    (agent_name,)
                )
                row = cursor.fetchone()
                
                if row:
                    stats = dict(row)
                    total_trades = stats['total_trades'] + 1
                    win_count = stats['win_count'] + (1 if is_win else 0)
                    loss_count = stats['loss_count'] + (0 if is_win else 1)
                    total_pnl = stats['total_pnl'] + pnl
                    
                    # 连胜/连败
                    current_streak = stats['current_streak']
                    if is_win:
                        current_streak = max(1, current_streak + 1) if current_streak >= 0 else 1
                    else:
                        current_streak = min(-1, current_streak - 1) if current_streak <= 0 else -1
                    
                    best_trade = max(stats['best_trade'], pnl)
                    worst_trade = min(stats['worst_trade'], pnl)
                    win_rate = win_count / total_trades if total_trades > 0 else 0
                    avg_pnl = total_pnl / total_trades if total_trades > 0 else 0
                    
                    cursor.execute("""
                        UPDATE ai_stats SET
                            total_trades = ?, win_count = ?, loss_count = ?,
                            win_rate = ?, total_pnl = ?, current_streak = ?,
                            best_trade = ?, worst_trade = ?, avg_pnl = ?,
                            last_updated = ?
                        WHERE agent_name = ?
                    """, (
                        total_trades, win_count, loss_count, win_rate,
                        total_pnl, current_streak, best_trade, worst_trade,
                        avg_pnl, int(time.time() * 1000), agent_name
                    ))
                
                conn.commit()
    
    # ========== 虚拟持仓（字段与主系统 SimulatedPosition 对齐） ==========
    
    def open_position(
        self, 
        agent_name: str, 
        symbol: str, 
        side: str,
        entry_price: float, 
        qty: float,  # 改名为 qty，与主系统一致
        leverage: int = 50,
        contract_value: float = 1.0,
        signal_type: str = None,
        decision_id: Optional[int] = None
    ) -> int:
        """
        开仓（字段与主系统 SimulatedPosition 对齐）
        
        参数:
            agent_name: AI 名称
            symbol: 交易对
            side: 方向 ('long' or 'short')
            entry_price: 入场价格
            qty: 持仓数量（与主系统一致）
            leverage: 杠杆倍数
            contract_value: 合约面值
            signal_type: 信号类型
            decision_id: 关联的决策 ID
        """
        # pos_side 与 side 保持一致（OKX 格式）
        pos_side = side
        
        with _db_lock:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ai_positions 
                    (agent_name, symbol, side, pos_side, qty, entry_price, 
                     leverage, contract_value, signal_type, created_at, 
                     decision_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
                """, (
                    agent_name, symbol, side, pos_side, qty, entry_price,
                    leverage, contract_value, signal_type,
                    int(time.time() * 1000), decision_id
                ))
                conn.commit()
                return cursor.lastrowid
    
    def close_position(self, position_id: int, exit_price: float) -> float:
        """
        平仓并计算盈亏
        
        🔥 修复盈亏计算公式：
        - qty 是 USD 仓位金额，不是合约数量
        - 盈亏 = 价格变化百分比 * 仓位 * 杠杆
        - long: (exit_price - entry_price) / entry_price * qty * leverage
        - short: (entry_price - exit_price) / entry_price * qty * leverage
        """
        agent_name = None
        pnl = 0.0
        
        with _db_lock:
            with get_db_connection(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(
                    "SELECT * FROM ai_positions WHERE id = ?",
                    (position_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    return 0.0
                
                pos = dict(row)
                entry_price = pos['entry_price']
                qty = pos.get('qty', pos.get('quantity', 0))  # qty 是 USD 仓位金额
                side = pos['side']
                leverage = pos.get('leverage', 1) or 1
                agent_name = pos['agent_name']
                
                # 🔥 修复盈亏计算公式
                # qty 是 USD 仓位金额，盈亏 = 价格变化百分比 * 仓位 * 杠杆
                if entry_price > 0:
                    price_change_pct = (exit_price - entry_price) / entry_price
                    if side == 'long':
                        pnl = price_change_pct * qty * leverage
                    else:  # short
                        pnl = -price_change_pct * qty * leverage
                else:
                    pnl = 0
                
                cursor.execute("""
                    UPDATE ai_positions SET
                        status = 'closed', exit_price = ?,
                        exit_time = ?, pnl = ?
                    WHERE id = ?
                """, (exit_price, int(time.time() * 1000), pnl, position_id))
                
                conn.commit()
        
        # 更新绩效（在锁外调用，避免死锁）
        if agent_name:
            self.update_stats(agent_name, pnl, pnl > 0)
        
        return pnl
    
    def get_open_positions(self, agent_name: Optional[str] = None) -> List[Dict]:
        """
        获取未平仓持仓
        
        返回字段与主系统 SimulatedPosition 对齐：
        - symbol, side, pos_side, qty, entry_price, leverage, contract_value, signal_type, created_at
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            if agent_name:
                cursor.execute("""
                    SELECT * FROM ai_positions 
                    WHERE status = 'open' AND agent_name = ?
                """, (agent_name,))
            else:
                cursor.execute(
                    "SELECT * FROM ai_positions WHERE status = 'open'"
                )
            
            rows = cursor.fetchall()
            positions = []
            for row in rows:
                pos = dict(row)
                # 兼容旧字段名：quantity -> qty
                if 'quantity' in pos and 'qty' not in pos:
                    pos['qty'] = pos['quantity']
                positions.append(pos)
            
            return positions
    
    def get_closed_positions(self, agent_name: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """
        获取已平仓持仓（用于资金曲线）
        
        返回按平仓时间排序的交易记录
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            if agent_name:
                cursor.execute("""
                    SELECT * FROM ai_positions 
                    WHERE status = 'closed' AND agent_name = ?
                    ORDER BY exit_time ASC
                    LIMIT ?
                """, (agent_name, limit))
            else:
                cursor.execute("""
                    SELECT * FROM ai_positions 
                    WHERE status = 'closed'
                    ORDER BY exit_time ASC
                    LIMIT ?
                """, (limit,))
            
            rows = cursor.fetchall()
            positions = []
            for row in rows:
                pos = dict(row)
                # 转换时间戳为可读格式
                if pos.get('exit_time'):
                    pos['close_time'] = pos['exit_time']
                positions.append(pos)
            
            return positions
    
    def get_agent_stats(self, agent_name: str) -> Optional[AIStats]:
        """
        获取指定 AI 的绩效统计（别名方法，与 get_stats 相同）
        """
        return self.get_stats(agent_name)
    
    def get_daily_pnl(self, agent_name: str, date: datetime = None) -> float:
        """
        获取指定 AI 的单日 PnL
        
        参数:
            agent_name: AI 名称
            date: 日期（默认今天）
        
        返回:
            当日累计 PnL
        """
        if date is None:
            date = datetime.now()
        
        # 计算当日开始和结束时间戳（毫秒）
        day_start = datetime(date.year, date.month, date.day)
        day_end = day_start + timedelta(days=1)
        start_ts = int(day_start.timestamp() * 1000)
        end_ts = int(day_end.timestamp() * 1000)
        
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(pnl), 0) as daily_pnl
                FROM ai_positions
                WHERE agent_name = ? 
                  AND status = 'closed'
                  AND exit_time >= ? 
                  AND exit_time < ?
            """, (agent_name, start_ts, end_ts))
            row = cursor.fetchone()
            return float(row['daily_pnl']) if row else 0.0
    
    def get_max_drawdown(self, agent_name: str, lookback_days: int = 30) -> Tuple[float, float]:
        """
        计算指定 AI 的最大回撤
        
        参数:
            agent_name: AI 名称
            lookback_days: 回溯天数
        
        返回:
            (max_drawdown_pct, current_drawdown_pct)
            - max_drawdown_pct: 历史最大回撤百分比
            - current_drawdown_pct: 当前回撤百分比
        """
        cutoff_ts = int((datetime.now() - timedelta(days=lookback_days)).timestamp() * 1000)
        
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取所有已平仓交易，按时间排序
            cursor.execute("""
                SELECT pnl, exit_time
                FROM ai_positions
                WHERE agent_name = ? 
                  AND status = 'closed'
                  AND exit_time >= ?
                ORDER BY exit_time ASC
            """, (agent_name, cutoff_ts))
            rows = cursor.fetchall()
            
            if not rows:
                return 0.0, 0.0
            
            # 计算资金曲线和回撤
            initial_capital = 10000.0  # 假设初始资金 10000 USD
            equity = initial_capital
            peak = initial_capital
            max_drawdown = 0.0
            
            for row in rows:
                pnl = row['pnl'] or 0
                equity += pnl
                
                if equity > peak:
                    peak = equity
                
                drawdown = (peak - equity) / peak if peak > 0 else 0
                max_drawdown = max(max_drawdown, drawdown)
            
            # 当前回撤
            current_drawdown = (peak - equity) / peak if peak > 0 else 0
            
            return max_drawdown * 100, current_drawdown * 100  # 转为百分比
    
    def get_consecutive_losses(self, agent_name: str, limit: int = 10) -> int:
        """
        获取连续亏损次数
        
        参数:
            agent_name: AI 名称
            limit: 检查最近多少笔交易
        
        返回:
            连续亏损次数（0 表示最近一笔是盈利）
        """
        with get_db_connection(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pnl
                FROM ai_positions
                WHERE agent_name = ? AND status = 'closed'
                ORDER BY exit_time DESC
                LIMIT ?
            """, (agent_name, limit))
            rows = cursor.fetchall()
            
            consecutive_losses = 0
            for row in rows:
                if row['pnl'] is not None and row['pnl'] < 0:
                    consecutive_losses += 1
                else:
                    break
            
            return consecutive_losses

    def get_arena_context(self, agent_name: str) -> Dict[str, Any]:
        """
        🔥 获取完整的竞技场上下文（用于 AI 决策）
        
        包含：
        - 自己的排名、胜率、PnL、连胜/连败
        - 排行榜前 3 名的信息
        - 与领先者的差距
        - 竞争对手的最近表现
        
        返回:
            {
                'my_rank': 1,
                'my_stats': {...},
                'leader': {...},
                'gap_to_leader': 0.0,
                'leaderboard': [...],
                'total_participants': 5,
                'competition_intensity': 'high'  # high/medium/low
            }
        """
        all_stats = self.get_all_stats()
        
        if not all_stats:
            return {
                'my_rank': 0,
                'my_stats': None,
                'leader': None,
                'gap_to_leader': 0.0,
                'leaderboard': [],
                'total_participants': 0,
                'competition_intensity': 'low'
            }
        
        # 按 PnL 排序（已经排好序了）
        my_stats = None
        my_rank = 0
        
        for i, stats in enumerate(all_stats):
            if stats.agent_name == agent_name:
                my_stats = stats
                my_rank = i + 1
                break
        
        # 领先者
        leader = all_stats[0] if all_stats else None
        gap_to_leader = 0.0
        if leader and my_stats:
            gap_to_leader = leader.total_pnl - my_stats.total_pnl
        
        # 排行榜（前 5 名）
        leaderboard = []
        for i, stats in enumerate(all_stats[:5]):
            leaderboard.append({
                'rank': i + 1,
                'name': stats.agent_name,
                'pnl': stats.total_pnl,
                'win_rate': stats.win_rate,
                'trades': stats.total_trades,
                'streak': stats.current_streak
            })
        
        # 竞争激烈程度（基于 PnL 差距）
        if len(all_stats) >= 2:
            top_gap = all_stats[0].total_pnl - all_stats[-1].total_pnl
            if top_gap < 10:
                intensity = 'high'  # 差距小，竞争激烈
            elif top_gap < 50:
                intensity = 'medium'
            else:
                intensity = 'low'  # 差距大，领先者优势明显
        else:
            intensity = 'low'
        
        return {
            'my_rank': my_rank,
            'my_stats': my_stats.to_dict() if my_stats else None,
            'leader': leader.to_dict() if leader else None,
            'gap_to_leader': gap_to_leader,
            'leaderboard': leaderboard,
            'total_participants': len(all_stats),
            'competition_intensity': intensity
        }


# 全局实例
_db_manager: Optional[AIDBManager] = None


def get_ai_db_manager() -> AIDBManager:
    """获取全局数据库管理器实例"""
    global _db_manager
    if _db_manager is None:
        _db_manager = AIDBManager()
    return _db_manager
