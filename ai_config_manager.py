"""
AI 配置管理模块

管理 AI 决策相关的配置，包括：
- 技术指标配置
- 时间周期配置
- 提示词预设
- 数据库持久化
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict


# ============================================================================
# 提示词预设定义
# ============================================================================

@dataclass
class PromptPreset:
    """提示词预设"""
    id: str
    name: str
    description: str
    prompt: str
    position_size: float  # 仓位比例 (0-1)
    stop_loss: float      # 止损比例 (0-1)
    take_profit: float    # 止盈比例 (0-1)
    risk_level: str       # 风险等级: low, medium, high


# 预设提示词配置
PROMPT_PRESETS: Dict[str, PromptPreset] = {
    "aggressive": PromptPreset(
        id="aggressive",
        name="猎人型",
        description="高风险高收益，积极捕捉交易机会",
        prompt="""你是"猎人型加密合约交易员（Hunter Trader）"，在合约市场进行自主决策。
唯一目标：最大化绝对收益（PnL）。你愿意承担较高风险以捕捉高回报机会，行动果断，不惧频繁交易。

【铁律（不可违背）】
1) 高频捕捉：积极寻找交易机会，不回避短线波动。
2) 风险回报比：最低接受 RR >= 1.5（按止损/止盈估算）。
3) 资金与仓位：
   - 最多同时持仓 6 个币种（机会驱动）。
   - 仓位金额和杠杆由你根据市场情况、置信度、风险回报比自主决定。
   - 杠杆范围 1-20x，可接近上限。
   - 总保证金使用率 <= 95%（但必须设置硬性止损）
4) 冷却：仅在同币种连续亏损 2 次后触发 10 分钟冷却。
5) 数据不足可小仓试仓：若关键指标缺失但盘口/情绪强烈，可用最小仓位试仓。

【决策步骤（必须执行）】
A. 市场状态：trend / momentum / volatility / reversal / unclear
B. 证据评分：至少列出 2 条"强势证据"（如放量、大单、情绪指标）
C. 风险计划：给出明确 entry / stop_loss / take_profit，计算 rr_estimate
D. 动作选择：
   - 若 rr_estimate >= 1.5 且证据明确 → 可开仓
   - 已持仓若趋势延续 → 可考虑加仓（不超过仓位上限）
E. 置信度：0-100；<65 禁止开仓""",
        position_size=0.08,
        stop_loss=0.03,
        take_profit=0.06,
        risk_level="high"
    ),
    
    "balanced": PromptPreset(
        id="balanced",
        name="均衡",
        description="风险收益平衡，适合大多数行情",
        prompt="""你是"平衡型加密合约交易员（Balanced Trader）"，在合约市场进行自主决策。
唯一目标：在控制回撤的前提下实现稳健收益。你追求风险与收益的平衡，不追求极端收益，也不回避适度风险。

【铁律（不可违背）】
1) 适度频率：根据市场状态调整交易频率；震荡市减少操作，趋势市适度参与。
2) 风险回报比：任何新开仓必须满足 RR >= 2.0（按止损/止盈估算）。
3) 资金与仓位：
   - 最多同时持仓 5 个币种（分散配置）。
   - 仓位金额和杠杆由你根据市场情况、置信度、风险回报比自主决定。
   - 杠杆范围 1-20x，建议 BTC/ETH 使用 3-10x，山寨使用 2-5x。
   - 总保证金使用率 <= 80%
4) 冷却：任一币种平仓后 10 分钟内禁止再次开同方向新仓（除非市场结构明确改变）。
5) 数据不完整则谨慎交易：如果输入缺少关键指标，可选择小仓位试仓或 WAIT。

【决策步骤（必须执行）】
A. 市场状态：trend / range / breakout / reversal / unclear
B. 证据评分：至少列出 3 条"可验证证据"（来自输入数据）
C. 风险计划：给出明确 entry / stop_loss / take_profit / time_invalidation，并计算 rr_estimate
D. 动作选择：
   - 若证据 < 3条 或 rr_estimate < 2.0 → HOLD/WAIT
   - 若市场处于震荡且无明确方向 → 减少仓位或等待突破
E. 置信度：0-100；<70 禁止开仓（只能 HOLD/WAIT）""",
        position_size=0.05,
        stop_loss=0.02,
        take_profit=0.04,
        risk_level="medium"
    ),
    
    "conservative": PromptPreset(
        id="conservative",
        name="僧侣型",
        description="追求夏普比率最大化，低频高质量交易",
        prompt="""你是"僧侣型加密合约交易员（Monk Trader）"，在合约市场进行自主决策。
唯一目标：最大化长期夏普比率（Sharpe）。你追求稳定与可解释，不追求交易次数。

【铁律（不可违背）】
1) 低频：多数周期必须选择 HOLD/WAIT；不为了"有动作"而交易。
2) 风险回报比：任何新开仓必须满足 RR >= 3.0（按止损/止盈估算）。
3) 资金与仓位：由你根据市场情况自主决定，但总保证金使用率 <= 90%。
4) 冷却：任一币种平仓后 15 分钟内禁止再次开同方向新仓（除非"止损后反转"且证据>=3条）。
5) 数据不足则不交易：如果输入缺少关键字段，必须 WAIT，并说明缺什么。

【决策步骤】
A. 市场状态：trend / range / breakout / reversal / unclear
B. 证据评分：至少列出3条"可验证证据"（来自输入数据）
C. 风险计划：给出明确 entry / stop_loss / take_profit / time_invalidation，并计算 rr_estimate
D. 动作选择：若证据 < 2条 或 rr_estimate < 3.0 或风险不可控 → HOLD/WAIT
E. 置信度：0-100；<75 禁止开仓（只能 HOLD/WAIT）""",
        position_size=0.05,  # 默认值，实际由 AI 决定
        stop_loss=0.02,
        take_profit=0.06,
        risk_level="low"
    ),
    
    "scalping": PromptPreset(
        id="scalping",
        name="闪电型",
        description="快进快出，高频小额交易累积利润",
        prompt="""你是"闪电型加密合约交易员（Flash Trader）"，在合约市场进行自主决策。
唯一目标：通过高频小额交易累积利润。你专注于分钟级机会，持仓时间短，追求胜率与速度。

【铁律（不可违背）】
1) 持仓时间：单笔持仓不超过 30 分钟（除非趋势极强）。
2) 风险回报比：接受 RR >= 1.0（甚至更低），但胜率必须高。
3) 资金与仓位：
   - 最多同时持仓 4 个币种（避免过度分散注意力）。
   - 仓位金额和杠杆由你根据市场情况自主决定。
   - 杠杆范围 1-20x。
   - 总保证金使用率 <= 70%
4) 冷却：每笔交易后必须等待 5 分钟才能进行下一笔（同币种或不同币种）。

【决策步骤（必须执行）】
A. 市场状态：momentum / mean_reversion / breakout / unclear
B. 证据评分：基于 K 线和技术指标，列出 2 条入场证据（如 RSI 超卖/超买、MACD 金叉/死叉、布林带突破、均线交叉、价格突破关键位等）
C. 风险计划：给出明确 entry / stop_loss / take_profit（通常较近），计算 rr_estimate
D. 动作选择：
   - 若证据明确且止损可控制在 1% 以内 → 开仓
   - 持仓达到 30 分钟或利润目标 → 平仓
   - 市场震荡无明确方向 → 可以挂限价单等待突破
E. 置信度：0-100；<80 禁止开仓

【重要】你只有 K 线和技术指标数据，没有订单流和盘口深度。请基于现有数据做出决策，不要因为缺少订单流数据而拒绝交易。""",
        position_size=0.10,
        stop_loss=0.01,
        take_profit=0.015,
        risk_level="high"
    ),
    
    "trend_following": PromptPreset(
        id="trend_following",
        name="冲浪型",
        description="顺势而为，捕捉并持有趋势行情",
        prompt="""你是"冲浪型加密合约交易员（Surfer Trader）"，在合约市场进行自主决策。
唯一目标：捕捉并持有趋势行情，让利润奔跑。你只在趋势明确时入场，避免逆势交易。

【铁律（不可违背）】
1) 只做趋势：市场状态必须明确为 trend 或 strong_breakout 才可开仓。
2) 风险回报比：任何新开仓必须满足 RR >= 2.5（按止损/止盈估算）。
3) 资金与仓位：
   - 最多同时持仓 3 个币种（专注最强趋势）。
   - 仓位金额和杠杆由你根据市场情况、置信度、风险回报比自主决定。
   - 杠杆范围 1-20x。
   - 总保证金使用率 <= 85%
4) 冷却：趋势结束（如 ADX 转弱或收盘价破趋势线）后 30 分钟内禁止开同方向新仓。
5) 必须有多时间框架确认：如果缺少高一级别时间框架（如 4H）趋势确认，必须 WAIT。

【决策步骤（必须执行）】
A. 市场状态：trend（uptrend/downtrend）/ consolidation / trend_exhaustion / unclear
B. 证据评分：至少列出 3 条"趋势证据"（如多 timeframe 共振、均线排列、ADX > 25）
C. 风险计划：给出明确 entry / stop_loss / take_profit（止盈可设为移动跟踪），计算 rr_estimate
D. 动作选择：
   - 若趋势确认且 RR >= 2.5 → 开仓
   - 持仓期间若趋势持续 → 移动止损，不止盈过早
E. 置信度：0-100；<80 禁止开仓""",
        position_size=0.06,
        stop_loss=0.025,
        take_profit=0.0,  # 移动止盈
        risk_level="medium"
    )
}


# ============================================================================
# 默认配置
# ============================================================================

DEFAULT_AI_CONFIG = {
    "timeframes": ["5m", "15m", "1h", "4h"],
    "kline_count": 100,  # 100 根 K 线足够计算大多数指标
    "indicators": ["MA", "RSI", "MACD"],
    "preset_id": "balanced",
    "custom_prompt": "",
    "position_size": 0.05,
    "stop_loss": 0.02,
    "take_profit": 0.04,
}


# ============================================================================
# AI 配置管理器
# ============================================================================

class AIConfigManager:
    """
    AI 配置管理器
    
    负责配置的读取、保存和数据库持久化
    """
    
    def __init__(self, db_path: str = "quant_system.db"):
        self.db_path = db_path
        self._ensure_table()
    
    def _ensure_table(self):
        """确保数据库表存在"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # AI 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # AI API 配置表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_api_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_id TEXT UNIQUE NOT NULL,
                    api_key TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    verified INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            
            # AI 交易记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ai_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL,
                    exit_price REAL,
                    quantity REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    entry_time TEXT,
                    exit_time TEXT,
                    reason TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"[AIConfigManager] 创建表失败: {e}")
    
    # ========== 配置读写 ==========
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT config_value FROM ai_config WHERE config_key = ?",
                (key,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return json.loads(row[0])
            return default
        except Exception as e:
            print(f"[AIConfigManager] 读取配置失败: {e}")
            return default
    
    def set_config(self, key: str, value: Any) -> bool:
        """保存配置值"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            value_json = json.dumps(value, ensure_ascii=False)
            
            cursor.execute("""
                INSERT INTO ai_config (config_key, config_value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = excluded.updated_at
            """, (key, value_json, now))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[AIConfigManager] 保存配置失败: {e}")
            return False
    
    # ========== AI 配置 ==========
    
    def get_ai_settings(self) -> Dict[str, Any]:
        """获取完整的 AI 设置"""
        settings = self.get_config("ai_settings", DEFAULT_AI_CONFIG.copy())
        
        # 确保所有必要字段存在
        for key, default_value in DEFAULT_AI_CONFIG.items():
            if key not in settings:
                settings[key] = default_value
        
        return settings
    
    def save_ai_settings(self, settings: Dict[str, Any]) -> bool:
        """保存 AI 设置"""
        return self.set_config("ai_settings", settings)
    
    def get_timeframes(self) -> List[str]:
        """获取时间周期配置"""
        settings = self.get_ai_settings()
        return settings.get("timeframes", DEFAULT_AI_CONFIG["timeframes"])
    
    def set_timeframes(self, timeframes: List[str]) -> bool:
        """设置时间周期"""
        settings = self.get_ai_settings()
        settings["timeframes"] = timeframes
        return self.save_ai_settings(settings)
    
    def get_indicators(self) -> List[str]:
        """获取指标配置"""
        settings = self.get_ai_settings()
        return settings.get("indicators", DEFAULT_AI_CONFIG["indicators"])
    
    def set_indicators(self, indicators: List[str]) -> bool:
        """设置指标"""
        settings = self.get_ai_settings()
        settings["indicators"] = indicators
        return self.save_ai_settings(settings)
    
    def get_kline_count(self) -> int:
        """获取 K 线数量"""
        settings = self.get_ai_settings()
        return settings.get("kline_count", DEFAULT_AI_CONFIG["kline_count"])
    
    def set_kline_count(self, count: int) -> bool:
        """设置 K 线数量"""
        settings = self.get_ai_settings()
        settings["kline_count"] = count
        return self.save_ai_settings(settings)
    
    # ========== 提示词管理 ==========
    
    def get_preset(self, preset_id: str) -> Optional[PromptPreset]:
        """获取预设提示词"""
        return PROMPT_PRESETS.get(preset_id)
    
    def get_all_presets(self) -> Dict[str, PromptPreset]:
        """获取所有预设"""
        return PROMPT_PRESETS
    
    def get_current_preset_id(self) -> str:
        """获取当前使用的预设 ID"""
        settings = self.get_ai_settings()
        return settings.get("preset_id", "balanced")
    
    def get_selected_preset(self) -> str:
        """获取当前选择的预设 ID（别名）"""
        return self.get_current_preset_id()
    
    def set_preset(self, preset_id: str) -> bool:
        """设置当前预设"""
        if preset_id not in PROMPT_PRESETS:
            return False
        
        preset = PROMPT_PRESETS[preset_id]
        settings = self.get_ai_settings()
        settings["preset_id"] = preset_id
        settings["position_size"] = preset.position_size
        settings["stop_loss"] = preset.stop_loss
        settings["take_profit"] = preset.take_profit
        
        return self.save_ai_settings(settings)
    
    def get_custom_prompt(self) -> str:
        """获取自定义提示词"""
        settings = self.get_ai_settings()
        return settings.get("custom_prompt", "")
    
    def set_custom_prompt(self, prompt: str) -> bool:
        """设置自定义提示词"""
        settings = self.get_ai_settings()
        settings["custom_prompt"] = prompt
        return self.save_ai_settings(settings)
    
    def get_effective_prompt(self) -> str:
        """
        获取有效的提示词
        
        优先使用自定义提示词，否则使用预设
        """
        custom = self.get_custom_prompt()
        if custom.strip():
            return custom
        
        preset_id = self.get_current_preset_id()
        preset = self.get_preset(preset_id)
        if preset:
            return preset.prompt
        
        return PROMPT_PRESETS["balanced"].prompt
    
    # ========== AI API 配置 ==========
    
    def get_ai_api_config(self, ai_id: str) -> Optional[Dict[str, Any]]:
        """获取 AI API 配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT api_key, enabled, verified FROM ai_api_configs WHERE ai_id = ?",
                (ai_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    "api_key": row[0],
                    "enabled": row[1] == 1,
                    "verified": row[2] == 1
                }
            return None
        except Exception as e:
            print(f"[AIConfigManager] 读取 API 配置失败: {e}")
            return None
    
    def save_ai_api_config(self, ai_id: str, api_key: str, enabled: bool = True, verified: bool = False) -> bool:
        """保存 AI API 配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO ai_api_configs (ai_id, api_key, enabled, verified, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(ai_id) DO UPDATE SET
                    api_key = excluded.api_key,
                    enabled = excluded.enabled,
                    verified = excluded.verified,
                    updated_at = excluded.updated_at
            """, (ai_id, api_key, 1 if enabled else 0, 1 if verified else 0, now, now))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[AIConfigManager] 保存 API 配置失败: {e}")
            return False
    
    def delete_ai_api_config(self, ai_id: str) -> bool:
        """删除 AI API 配置"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_api_configs WHERE ai_id = ?", (ai_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[AIConfigManager] 删除 API 配置失败: {e}")
            return False
    
    def get_all_ai_api_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有 AI API 配置
        
        优先级：数据库配置 > 环境变量
        """
        import os
        
        # 环境变量映射
        env_keys = {
            "deepseek": "DEEPSEEK_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "perplexity": "PERPLEXITY_API_KEY",
            "spark_lite": "SPARK_API_PASSWORD",
            "hunyuan": "HUNYUAN_API_KEY"
        }
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT ai_id, api_key, enabled, verified FROM ai_api_configs")
            rows = cursor.fetchall()
            conn.close()
            
            configs = {}
            for row in rows:
                configs[row[0]] = {
                    "api_key": row[1],
                    "enabled": row[2] == 1,
                    "verified": row[3] == 1
                }
            
            # 如果数据库中没有配置，尝试从环境变量读取
            for ai_id, env_key in env_keys.items():
                if ai_id not in configs or not configs[ai_id].get("api_key"):
                    env_value = os.getenv(env_key, "")
                    if env_value:
                        configs[ai_id] = {
                            "api_key": env_value,
                            "enabled": True,
                            "verified": False  # 环境变量的 Key 需要验证
                        }
            
            return configs
        except Exception as e:
            print(f"[AIConfigManager] 读取所有 API 配置失败: {e}")
            
            # 回退到环境变量
            configs = {}
            for ai_id, env_key in env_keys.items():
                env_value = os.getenv(env_key, "")
                if env_value:
                    configs[ai_id] = {
                        "api_key": env_value,
                        "enabled": True,
                        "verified": False
                    }
            return configs
    
    # ========== AI 交易记录 ==========
    
    def record_ai_trade(self, ai_id: str, symbol: str, side: str, 
                        entry_price: float, quantity: float, reason: str = "") -> int:
        """记录 AI 交易入场"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute("""
                INSERT INTO ai_trades (ai_id, symbol, side, entry_price, quantity, entry_time, reason, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ai_id, symbol, side, entry_price, quantity, now, reason, now))
            
            trade_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return trade_id
        except Exception as e:
            print(f"[AIConfigManager] 记录交易失败: {e}")
            return -1
    
    def close_ai_trade(self, trade_id: int, exit_price: float, pnl: float, pnl_pct: float) -> bool:
        """记录 AI 交易出场"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute("""
                UPDATE ai_trades 
                SET exit_price = ?, pnl = ?, pnl_pct = ?, exit_time = ?
                WHERE id = ?
            """, (exit_price, pnl, pnl_pct, now, trade_id))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"[AIConfigManager] 更新交易失败: {e}")
            return False
    
    def get_ai_trades(self, ai_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """获取 AI 交易记录"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if ai_id:
                cursor.execute("""
                    SELECT * FROM ai_trades WHERE ai_id = ? ORDER BY created_at DESC LIMIT ?
                """, (ai_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM ai_trades ORDER BY created_at DESC LIMIT ?
                """, (limit,))
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(zip(columns, row)) for row in rows]
        except Exception as e:
            print(f"[AIConfigManager] 读取交易记录失败: {e}")
            return []
    
    # ========== 调度器状态持久化 ==========
    
    def get_scheduler_state(self) -> Dict[str, Any]:
        """
        获取调度器状态（用于 UI 重启后恢复）
        
        返回:
            {
                'enabled': True/False,
                'symbols': [...],
                'timeframes': [...],
                'agents': [...],
                'ai_takeover': True/False,
                'user_prompt': '...',
                'last_updated': '...'
            }
        """
        return self.get_config("scheduler_state", {
            'enabled': False,
            'symbols': ['BTC/USDT:USDT'],
            'timeframes': ['5m'],
            'agents': [],
            'ai_takeover': False,
            'user_prompt': '',
            'last_updated': ''
        })
    
    def save_scheduler_state(
        self,
        enabled: bool,
        symbols: List[str] = None,
        timeframes: List[str] = None,
        agents: List[str] = None,
        ai_takeover: bool = False,
        user_prompt: str = ""
    ) -> bool:
        """
        保存调度器状态（持久化）
        
        在启动/停止调度器时调用，UI 重启后可恢复
        """
        state = {
            'enabled': enabled,
            'symbols': symbols or ['BTC/USDT:USDT'],
            'timeframes': timeframes or ['5m'],
            'agents': agents or [],
            'ai_takeover': ai_takeover,
            'user_prompt': user_prompt,
            'last_updated': datetime.now().isoformat()
        }
        return self.set_config("scheduler_state", state)
    
    def clear_scheduler_state(self) -> bool:
        """清除调度器状态（停止时调用）"""
        return self.save_scheduler_state(enabled=False)


# ============================================================================
# 全局实例
# ============================================================================

_config_manager: Optional[AIConfigManager] = None


def get_ai_config_manager(db_path: str = "quant_system.db") -> AIConfigManager:
    """获取 AI 配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = AIConfigManager(db_path)
    return _config_manager
