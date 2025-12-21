"""
AI Brain - 多模型决策引擎

支持 DeepSeek, Qwen, Perplexity 等模型
特点：
1. 处理 DeepSeek 的 <think> 标签
2. 用户风格 Prompt 注入
3. 异步并发调用
"""

import os
import re
import json
import time
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# 抑制 httpx 的 INFO 日志（太冗余）
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@dataclass
class MarketContext:
    """市场上下文数据"""
    symbol: str
    timeframe: str
    current_price: float
    ohlcv: List[List]
    indicators: Dict[str, Any]
    formatted_indicators: str
    sentiment: Optional[Dict[str, Any]] = None  # 市场情绪数据


@dataclass
class AIDecisionResult:
    """AI 决策结果 - 僧侣型交易员输出格式"""
    agent_name: str
    signal: str  # open_long / open_short / close_long / close_short / hold / wait
    confidence: float  # 0-100
    reasoning: str
    thinking: str = ""  # DeepSeek <think> 内容
    entry_price: Optional[float] = None
    entry_type: str = "market"  # market / limit
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    rr_estimate: Optional[float] = None  # 风险回报比
    position_size_usd: float = 0.0  # 仓位金额 (USD)
    leverage: int = 1  # 杠杆倍数 1-20
    evidence: List[str] = None  # 证据列表
    arena_note: str = ""  # 竞技场调整说明
    cooldown_minutes: int = 15  # 冷却时间
    time_invalidation: str = ""  # 时间失效条件
    latency_ms: float = 0.0
    error: Optional[str] = None
    
    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []


# ============================================================================
# System Prompt 模板 - 僧侣型交易员 (Monk Trader)
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """你是"僧侣型加密合约交易员（Monk Trader）"，在合约市场进行自主决策。
唯一目标：最大化长期夏普比率（Sharpe）。你追求稳定与可解释，不追求交易次数。

【铁律（不可违背）】
1) 低频：多数周期必须选择 HOLD/WAIT；不为了"有动作"而交易。
2) 风险回报比：任何新开仓必须满足 RR >= 3.0（按止损/止盈估算）。
3) 资金与仓位：
   - 最多同时持仓 3 个币种（质量优先）。
   - 仓位金额和杠杆由你根据市场情况、置信度、风险回报比自主决定。
   - 杠杆范围 1-20x，高杠杆需要高置信度支撑。
   - 总保证金使用率 <= 90%
4) 冷却：任一币种平仓后 15 分钟内禁止再次开同方向新仓（除非"止损后反转"且证据>=3条）。
5) 数据不足则不交易：如果输入缺少关键字段（价格/指标/持仓/时间框架/足够K线），必须 WAIT，并说明缺什么。

【用户风格指令（仅在不违反铁律时生效）】
{user_style_prompt}

【决策步骤（必须执行）】
A. 市场状态：trend / range / breakout / reversal / unclear
B. 证据评分：至少列出3条"可验证证据"（来自输入数据）
C. 风险计划：给出明确 entry / stop_loss / take_profit / time_invalidation，并计算 rr_estimate
D. 动作选择：
   - 若证据 < 2条 或 rr_estimate < 3.0 或风险不可控 → HOLD/WAIT
   - 若已持仓 → 优先判断"持仓是否失效/是否需要止损/是否需要移动止盈"，避免频繁反向
E. 置信度：0-100；<75 禁止开仓（只能 HOLD/WAIT）

【输出（只允许 JSON；不要输出任何其他文本；必须包含单词 json）】
```json
{{
    "timestamp_ms": 0,
    "symbol": "BTCUSDT",
    "action": "open_long | open_short | close_long | close_short | hold | wait",
    "confidence": 0,
    "position_size_usd": 0,
    "leverage": 1,
    "entry": {{
        "type": "market|limit",
        "price": null,
        "note": ""
    }},
    "risk": {{
        "stop_loss": null,
        "take_profit": null,
        "rr_estimate": null,
        "time_invalidation": "",
        "cooldown_minutes": 15
    }},
    "evidence": ["", "", ""],
    "reasoning": "用不超过120字说明核心逻辑（不要长篇思维链）",
    "arena_note": "用一句话说明你如何根据排名/表现调整（更稳或更激进，但不破坏铁律）"
}}
```

【强制一致性】
- action 为 hold/wait 时：position_size_usd 必须为 0；entry/stop_loss/take_profit 为 null。
- action 为 open_* 时：必须给出 stop_loss、take_profit、rr_estimate、position_size_usd、leverage，且 rr_estimate >= 3.0。"""

USER_PROMPT_TEMPLATE = """【market_context】
- symbol: {symbol}
- timeframe: {timeframe}
- current_price: {current_price}

【技术指标】
{indicators}

【最近 K 线数据】
{recent_candles}

【持仓状态】
{position_status}
{sentiment_section}
{arena_context}
请根据以上数据进行决策。"""


# ============================================================================
# 批量分析 Prompt 模板（一次分析多个币种）
# ============================================================================

BATCH_SYSTEM_PROMPT_TEMPLATE = """你是加密合约交易员，在合约市场进行自主决策。

【账户信息】
- 初始资金：$10,000 USD
- 这是虚拟竞技场账户，请根据可用余额合理分配仓位

【用户交易风格】
{user_style_prompt}

【批量分析任务】
你将收到多个币种的市场数据和当前持仓信息，请对每个币种分别给出决策。
输出必须是 JSON 数组格式，每个元素对应一个币种的决策。

【输出格式（必须是 JSON 数组）】
```json
[
  {{
    "symbol": "BTC",
    "action": "open_long",
    "confidence": 80,
    "position_size_usd": 1000,
    "leverage": 5,
    "stop_loss": 95000,
    "take_profit": 105000,
    "reasoning": "简短说明（不超过80字）"
  }}
]
```

【强制规则】
- symbol 必须只写基础币种名称（如 BTC、ETH、SOL），不要写 BTCUSDT 或 BTC/USDT
- action 必须从以下选择一个：
  - open_long（做多）：开多仓
  - open_short（做空）：开空仓
  - close_long（平多）：平掉多仓
  - close_short（平空）：平掉空仓
  - hold（持有）：维持当前持仓
  - wait（等待）：不操作
- 必须为每个输入的币种都给出决策
- 【重要】如果已有持仓，必须根据当前行情判断是否需要平仓：
  - 如果持有多仓但行情转空，应该 close_long 或 open_short
  - 如果持有空仓但行情转多，应该 close_short 或 open_long
- action 为 open_long/open_short 时：
  - position_size_usd 必须 > 0，根据可用余额和置信度决定仓位大小
  - 建议单笔仓位占可用余额的 10%-30%，高置信度可适当加大
  - stop_loss 必须设置具体价格
  - take_profit 必须设置具体价格
  - leverage 建议 3-10x
- action 为 close_long/close_short/hold/wait 时：position_size_usd 必须为 0
- 输出只能是 JSON 数组，不要有其他文字"""

BATCH_USER_PROMPT_TEMPLATE = """【批量市场数据】
以下是 {symbol_count} 个币种的市场数据，请对每个币种分别分析并给出决策。

{all_symbols_data}

【市场情绪】
{sentiment_section}
{balance_section}
{position_section}
{arena_context}

请输出 JSON 数组格式的决策结果。"""


# ============================================================================
# 基础 Agent 类
# ============================================================================

class BaseAgent(ABC):
    """AI Agent 基类"""
    
    def __init__(self, name: str, api_key: str = "", api_base: str = ""):
        self.name = name
        self.api_key = api_key
        self.api_base = api_base
        self.timeout = 30
    
    @abstractmethod
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用 API，返回 (content, thinking)"""
        pass
    
    def _build_messages(
        self, 
        context: MarketContext, 
        user_prompt: str = "",
        arena_context: Optional[Dict] = None,
        position_status: Optional[Dict] = None
    ) -> List[Dict]:
        """构建消息列表"""
        # 🔥 判断 user_prompt 是否是完整的交易员人设（包含铁律等关键词）
        # 如果是完整人设，直接使用；否则插入到默认模板
        if user_prompt and ("铁律" in user_prompt or "【决策步骤】" in user_prompt or "Trader）" in user_prompt):
            # 用户提供了完整的交易员人设，直接使用
            system_prompt = user_prompt + """

【输出（只允许 JSON；不要输出任何其他文本；必须包含单词 json）】
```json
{
    "timestamp_ms": 0,
    "symbol": "BTCUSDT",
    "action": "open_long | open_short | close_long | close_short | hold | wait",
    "confidence": 0,
    "position_size_usd": 0,
    "leverage": 1,
    "entry": {
        "type": "market|limit",
        "price": null,
        "note": ""
    },
    "risk": {
        "stop_loss": null,
        "take_profit": null,
        "rr_estimate": null,
        "time_invalidation": "",
        "cooldown_minutes": 15
    },
    "evidence": ["", "", ""],
    "reasoning": "用不超过120字说明核心逻辑",
    "arena_note": ""
}
```

【强制一致性】
- action 为 hold/wait 时：position_size_usd 必须为 0；entry/stop_loss/take_profit 为 null。
- action 为 open_* 时：必须给出 stop_loss、take_profit、rr_estimate、position_size_usd、leverage。"""
        else:
            # 使用默认模板，将 user_prompt 作为风格补充
            user_style = user_prompt if user_prompt else "均衡策略，追求稳定收益"
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(user_style_prompt=user_style)
        
        # 最近 K 线数据（最多 10 根）
        recent = context.ohlcv[-10:] if len(context.ohlcv) >= 10 else context.ohlcv
        candles_text = "\n".join([
            f"  [{i+1}] ts:{c[0]} O:{c[1]:.2f} H:{c[2]:.2f} L:{c[3]:.2f} C:{c[4]:.2f} V:{c[5]:.2f}"
            for i, c in enumerate(recent)
        ])
        
        # 构建情绪分析部分
        sentiment_section = ""
        if context.sentiment:
            value = context.sentiment.get('value', 'N/A')
            classification = context.sentiment.get('classification', '未知')
            sentiment_section = f"""
【市场情绪 (Fear & Greed Index)】
- 指数值: {value}
- 情绪等级: {classification}
"""
        
        # 构建持仓状态
        position_text = "无持仓"
        if position_status:
            positions = position_status.get('positions', [])
            if positions:
                pos_lines = []
                for pos in positions:
                    pos_lines.append(
                        f"  - {pos.get('symbol')}: {pos.get('side')} "
                        f"入场价:{pos.get('entry_price')} 数量:{pos.get('qty')} "
                        f"未实现盈亏:{pos.get('unrealized_pnl', 0):.2f}"
                    )
                position_text = "\n".join(pos_lines)
            account_info = position_status.get('account', {})
            if account_info:
                position_text += f"\n- 账户余额: {account_info.get('balance', 0):.2f} USDT"
                position_text += f"\n- 保证金使用率: {account_info.get('margin_ratio', 0):.1f}%"
        
        # 🔥 构建竞技场上下文（包含排名、对手信息、竞争态势）
        arena_text = ""
        if arena_context:
            my_rank = arena_context.get('my_rank', 0)
            my_stats = arena_context.get('my_stats') or {}
            leader = arena_context.get('leader') or {}
            gap = arena_context.get('gap_to_leader', 0)
            leaderboard = arena_context.get('leaderboard', [])
            intensity = arena_context.get('competition_intensity', 'low')
            
            # 基本信息
            arena_text = f"""
【arena_context - 竞技场态势】
你的排名: #{my_rank}/{arena_context.get('total_participants', 0)}
你的胜率: {my_stats.get('win_rate', 0)*100:.1f}%
你的 PnL: {my_stats.get('total_pnl', 0):.2f} USDT
连胜/连败: {my_stats.get('current_streak', 0)}
竞争激烈度: {intensity}
"""
            # 与领先者的差距
            if my_rank > 1 and leader:
                arena_text += f"""
【领先者】
- {leader.get('agent_name', 'Unknown')}: PnL {leader.get('total_pnl', 0):.2f}, 胜率 {leader.get('win_rate', 0)*100:.1f}%
- 你与领先者差距: {gap:.2f} USDT
"""
            
            # 排行榜
            if leaderboard:
                arena_text += "\n【排行榜 TOP5】\n"
                for item in leaderboard:
                    marker = " <-- 你" if item['name'] == my_stats.get('agent_name') else ""
                    streak_str = f"+{item['streak']}" if item['streak'] > 0 else str(item['streak'])
                    arena_text += f"#{item['rank']} {item['name']}: {item['pnl']:.2f} | {item['win_rate']*100:.0f}% | {streak_str}{marker}\n"
            
            # 竞争策略提示
            if intensity == 'high':
                arena_text += "\n[竞争激烈] 排名接近，每一笔交易都很关键。可适度激进追赶。"
            elif my_rank == 1:
                arena_text += "\n[领先中] 保持优势，避免不必要的风险。稳健为主。"
            elif gap > 20:
                arena_text += f"\n[落后较多] 差距 {gap:.1f}，需要更积极寻找机会追赶。"
        
        user_message = USER_PROMPT_TEMPLATE.format(
            symbol=context.symbol,
            timeframe=context.timeframe,
            current_price=context.current_price,
            indicators=context.formatted_indicators,
            recent_candles=candles_text,
            position_status=position_text,
            sentiment_section=sentiment_section,
            arena_context=arena_text
        )
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    
    def _parse_response(self, response: str) -> Dict:
        """解析 AI 响应 - 僧侣型交易员格式"""
        try:
            text = response.strip()
            
            # 提取 JSON
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                text = text[start:end].strip()
            
            # 🔥 处理 "json\n{...}" 格式
            if text.lower().startswith("json"):
                text = text[4:].strip()
            
            # 🔥 查找第一个 { 和最后一个 }
            if not text.startswith("{"):
                start_idx = text.find("{")
                end_idx = text.rfind("}")
                if start_idx != -1 and end_idx != -1:
                    text = text[start_idx:end_idx + 1]
            
            data = json.loads(text)
            
            # 🔥 处理嵌套的 {"json": {...}} 格式（Perplexity 有时会这样返回）
            if "json" in data and isinstance(data.get("json"), dict):
                data = data["json"]
            # 🔥 处理 {"response": {...}} 格式
            if "response" in data and isinstance(data.get("response"), dict):
                data = data["response"]
            
            # 解析 action -> signal 映射
            action = data.get("action", "wait").lower()
            valid_actions = ["open_long", "open_short", "close_long", "close_short", "hold", "wait"]
            
            # 🔥 处理模板值（如 "open_long | open_short | ..."）
            if "|" in action:
                # 模型返回了模板值，尝试从 reasoning 推断意图
                reasoning = str(data.get("reasoning", "")).lower()
                if "开多" in reasoning or "做多" in reasoning or "买入" in reasoning or "open_long" in reasoning:
                    action = "open_long"
                elif "开空" in reasoning or "做空" in reasoning or "卖出" in reasoning or "open_short" in reasoning:
                    action = "open_short"
                elif "平多" in reasoning or "close_long" in reasoning:
                    action = "close_long"
                elif "平空" in reasoning or "close_short" in reasoning:
                    action = "close_short"
                else:
                    action = "wait"
                logger.warning(f"[{self.name}] action 为模板值，从 reasoning 推断为: {action}")
            
            if action not in valid_actions:
                action = "wait"
            
            # 解析 entry 对象
            entry_obj = data.get("entry", {}) or {}
            entry_type = entry_obj.get("type", "market")
            entry_price = entry_obj.get("price")
            
            # 解析 risk 对象
            risk_obj = data.get("risk", {}) or {}
            stop_loss = risk_obj.get("stop_loss")
            take_profit = risk_obj.get("take_profit")
            rr_estimate = risk_obj.get("rr_estimate")
            time_invalidation = risk_obj.get("time_invalidation", "")
            cooldown_minutes = int(risk_obj.get("cooldown_minutes", 15))
            
            # 解析杠杆，限制在 1-20 之间
            leverage = int(data.get("leverage", 1))
            leverage = min(20, max(1, leverage))
            
            # 解析置信度 (0-100)
            confidence = float(data.get("confidence", 0))
            confidence = min(100, max(0, confidence))
            
            # 解析仓位金额
            position_size_usd = float(data.get("position_size_usd", 0))
            position_size_usd = max(0, position_size_usd)
            
            # 解析证据列表
            evidence = data.get("evidence", [])
            if not isinstance(evidence, list):
                evidence = []
            evidence = [str(e) for e in evidence if e]
            
            return {
                "signal": action,
                "confidence": confidence,
                "reasoning": str(data.get("reasoning", ""))[:200],
                "entry_price": entry_price,
                "entry_type": entry_type,
                "stop_loss": stop_loss,
                "take_profit": take_profit,
                "rr_estimate": rr_estimate,
                "position_size_usd": position_size_usd,
                "leverage": leverage,
                "evidence": evidence,
                "arena_note": str(data.get("arena_note", ""))[:100],
                "cooldown_minutes": cooldown_minutes,
                "time_invalidation": time_invalidation
            }
        except Exception as e:
            logger.warning(f"[{self.name}] 解析失败: {e}, response: {response[:200]}")
            return {
                "signal": "wait", 
                "confidence": 0,
                "reasoning": f"解析失败: {str(e)[:50]}",
                "entry_price": None,
                "entry_type": "market",
                "stop_loss": None,
                "take_profit": None,
                "rr_estimate": None,
                "position_size_usd": 0,
                "leverage": 1,
                "evidence": [],
                "arena_note": "",
                "cooldown_minutes": 15,
                "time_invalidation": ""
            }
    
    async def get_decision(
        self, 
        context: MarketContext, 
        user_prompt: str = "",
        arena_context: Optional[Dict] = None,
        position_status: Optional[Dict] = None
    ) -> AIDecisionResult:
        """获取 AI 决策"""
        start_time = time.perf_counter()
        
        try:
            messages = self._build_messages(context, user_prompt, arena_context, position_status)
            content, thinking = await self._call_api(messages)
            parsed = self._parse_response(content)
            latency = (time.perf_counter() - start_time) * 1000
            
            return AIDecisionResult(
                agent_name=self.name,
                signal=parsed["signal"],
                confidence=parsed["confidence"],
                reasoning=parsed["reasoning"],
                thinking=thinking,
                entry_price=parsed["entry_price"],
                entry_type=parsed["entry_type"],
                stop_loss=parsed["stop_loss"],
                take_profit=parsed["take_profit"],
                rr_estimate=parsed["rr_estimate"],
                position_size_usd=parsed["position_size_usd"],
                leverage=parsed["leverage"],
                evidence=parsed["evidence"],
                arena_note=parsed["arena_note"],
                cooldown_minutes=parsed["cooldown_minutes"],
                time_invalidation=parsed["time_invalidation"],
                latency_ms=latency
            )
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"[{self.name}] 决策失败: {e}")
            return AIDecisionResult(
                agent_name=self.name, 
                signal="wait", 
                confidence=0,
                reasoning=str(e)[:100], 
                latency_ms=latency, 
                error=str(e)
            )
    
    def _build_batch_messages(
        self,
        contexts: List[MarketContext],
        user_prompt: str = "",
        arena_context: Optional[Dict] = None,
        sentiment: Optional[Dict] = None,
        positions: List[Dict] = None,  # 当前持仓列表
        balance_info: Dict = None  # 🔥 新增：账户余额信息
    ) -> List[Dict]:
        """构建批量分析的消息列表"""
        # 🔥 判断 user_prompt 是否是完整的交易员人设
        # 如果是完整人设，提取核心风格；否则使用默认
        if user_prompt and ("铁律" in user_prompt or "【决策步骤】" in user_prompt or "Trader）" in user_prompt):
            # 用户提供了完整的交易员人设，提取关键信息作为风格
            user_style = user_prompt
        else:
            user_style = user_prompt if user_prompt else "均衡策略，追求稳定收益，风险回报比 >= 2.0"
        
        system_prompt = BATCH_SYSTEM_PROMPT_TEMPLATE.format(user_style_prompt=user_style)
        
        # 🔥 构建账户余额信息
        balance_text = ""
        if balance_info:
            initial = balance_info.get('initial', 10000)
            realized_pnl = balance_info.get('realized_pnl', 0)
            position_used = balance_info.get('position_used', 0)
            available = balance_info.get('available', initial)
            balance_text = f"""
【账户状态】
- 初始资金: ${initial:,.0f}
- 已实现盈亏: ${realized_pnl:+,.2f}
- 持仓占用: ${position_used:,.0f}
- 可用余额: ${available:,.2f}
注意：开仓金额不能超过可用余额！"""
        
        # 🔥 构建持仓信息
        position_text = ""
        if positions:
            pos_lines = []
            for pos in positions:
                symbol_short = pos.get('symbol', '').replace('/USDT:USDT', '').replace('/USDT', '')
                side = pos.get('side', 'unknown')
                entry_price = pos.get('entry_price', 0)
                qty = pos.get('qty', 0)
                side_cn = "多" if side == 'long' else "空"
                pos_lines.append(f"  - {symbol_short}: {side_cn}仓 | 入场价: {entry_price:.2f} | 仓位: ${qty:.0f}")
            position_text = "\n【当前持仓】\n" + "\n".join(pos_lines) + "\n注意：如果持仓方向与当前行情不符，请考虑平仓(close_long/close_short)或反向开仓。"
        else:
            position_text = "\n【当前持仓】无持仓"
        
        # 构建所有币种的数据
        all_data_parts = []
        for ctx in contexts:
            # 最近 5 根 K 线（批量模式减少数据量）
            recent = ctx.ohlcv[-5:] if len(ctx.ohlcv) >= 5 else ctx.ohlcv
            candles_text = " | ".join([
                f"C:{c[4]:.2f}"
                for c in recent
            ])
            
            symbol_data = f"""
=== {ctx.symbol} ({ctx.timeframe}) ===
价格: {ctx.current_price:.2f}
K线: {candles_text}
{ctx.formatted_indicators[:500]}"""
            all_data_parts.append(symbol_data)
        
        all_symbols_data = "\n".join(all_data_parts)
        
        # 情绪数据
        sentiment_text = ""
        if sentiment:
            sentiment_text = f"Fear & Greed: {sentiment.get('value', 'N/A')} ({sentiment.get('classification', '未知')})"
        
        # 竞技场上下文
        arena_text = ""
        if arena_context:
            my_rank = arena_context.get('my_rank', 0)
            arena_text = f"【竞技场】排名: #{my_rank}"
        
        user_message = BATCH_USER_PROMPT_TEMPLATE.format(
            symbol_count=len(contexts),
            all_symbols_data=all_symbols_data,
            sentiment_section=sentiment_text,
            balance_section=balance_text,  # 🔥 新增：余额信息
            position_section=position_text,
            arena_context=arena_text
        )
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    
    def _extract_json_objects(self, text: str) -> List[Dict]:
        """
        从文本中逐个提取 JSON 对象（用于处理不完整的 JSON 数组）
        
        增强版：支持嵌套对象、处理截断响应
        """
        results = []
        
        # 方法1：使用括号匹配逐个提取完整的 JSON 对象
        i = 0
        while i < len(text):
            if text[i] == '{':
                # 找到对象开始，使用括号计数找到结束
                depth = 0
                start = i
                in_string = False
                escape_next = False
                
                for j in range(i, len(text)):
                    char = text[j]
                    
                    if escape_next:
                        escape_next = False
                        continue
                    
                    if char == '\\':
                        escape_next = True
                        continue
                    
                    if char == '"' and not escape_next:
                        in_string = not in_string
                        continue
                    
                    if in_string:
                        continue
                    
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            # 找到完整对象
                            obj_str = text[start:j+1]
                            try:
                                # 尝试修复常见问题
                                obj_str = re.sub(r',\s*}', '}', obj_str)
                                obj_str = re.sub(r',\s*]', ']', obj_str)
                                obj = json.loads(obj_str)
                                if isinstance(obj, dict) and 'symbol' in obj:
                                    results.append(obj)
                            except json.JSONDecodeError:
                                pass
                            i = j
                            break
                else:
                    # 未找到闭合括号，尝试修复截断的 JSON
                    obj_str = text[start:]
                    # 尝试补全缺失的括号
                    missing_braces = depth
                    obj_str = obj_str.rstrip(',\n\r\t ')
                    # 如果在字符串中截断，先闭合字符串
                    if in_string:
                        obj_str += '"'
                    obj_str += '}' * missing_braces
                    try:
                        obj_str = re.sub(r',\s*}', '}', obj_str)
                        obj = json.loads(obj_str)
                        if isinstance(obj, dict) and 'symbol' in obj:
                            results.append(obj)
                    except json.JSONDecodeError:
                        pass
                    break
            i += 1
        
        # 方法2：如果方法1没有结果，尝试简单正则
        if not results:
            # 匹配包含 symbol 字段的简单对象
            pattern = r'\{\s*"symbol"\s*:\s*"([^"]+)"[^}]*\}'
            for match in re.finditer(pattern, text, re.DOTALL):
                try:
                    obj_str = match.group(0)
                    # 尝试修复
                    obj_str = re.sub(r',\s*}', '}', obj_str)
                    obj = json.loads(obj_str)
                    if isinstance(obj, dict) and 'symbol' in obj:
                        results.append(obj)
                except json.JSONDecodeError:
                    # 尝试手动构建最小对象
                    symbol = match.group(1)
                    results.append({
                        "symbol": symbol,
                        "action": "wait",
                        "confidence": 0,
                        "reasoning": "JSON 解析失败，使用默认值"
                    })
        
        logger.debug(f"[{self.name}] _extract_json_objects 提取到 {len(results)} 个对象")
        return results
    
    def _parse_batch_response(self, response: str) -> List[Dict]:
        """解析批量分析响应 - 增强版容错处理"""
        try:
            text = response.strip()
            original_text = text  # 保存原始文本用于调试
            
            # 记录原始响应（用于调试）
            logger.debug(f"[{self.name}] 原始响应长度: {len(text)}, 前200字符: {text[:200]}")
            
            # 提取 JSON
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end == -1:
                    # 没有找到结束标记，可能是截断的响应
                    text = text[start:].strip()
                    logger.warning(f"[{self.name}] JSON 代码块未闭合，可能是截断响应")
                else:
                    text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end == -1:
                    text = text[start:].strip()
                else:
                    text = text[start:end].strip()
            
            # 处理 "json\n[...]" 格式
            if text.lower().startswith("json"):
                text = text[4:].strip()
            
            # 查找 JSON 数组
            if not text.startswith("["):
                start_idx = text.find("[")
                end_idx = text.rfind("]")
                if start_idx != -1:
                    if end_idx != -1 and end_idx > start_idx:
                        text = text[start_idx:end_idx + 1]
                    else:
                        # 没有找到结束括号，截取到末尾并尝试修复
                        text = text[start_idx:]
                        logger.warning(f"[{self.name}] JSON 数组未闭合，尝试修复")
            
            # 🔥 增强的 JSON 修复
            # 1. 移除尾部逗号
            text = re.sub(r',\s*]', ']', text)
            text = re.sub(r',\s*}', '}', text)
            
            # 2. 修复截断的字符串（在引号内截断）
            # 检查引号是否配对
            quote_count = text.count('"') - text.count('\\"')
            if quote_count % 2 != 0:
                # 奇数个引号，添加一个闭合引号
                text = text.rstrip() + '"'
                logger.debug(f"[{self.name}] 修复未闭合的字符串")
            
            # 3. 修复未闭合的数组/对象
            open_brackets = text.count('[') - text.count(']')
            open_braces = text.count('{') - text.count('}')
            
            if open_brackets > 0 or open_braces > 0:
                # 移除可能的尾部逗号
                text = text.rstrip().rstrip(',')
                # 添加缺失的闭合括号
                text += '}' * open_braces + ']' * open_brackets
                logger.debug(f"[{self.name}] 修复未闭合的括号: +{open_braces}个}}, +{open_brackets}个]")
            
            # 4. 尝试解析
            data = None
            try:
                data = json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning(f"[{self.name}] JSON 解析失败: {e}")
                logger.debug(f"[{self.name}] 尝试解析的文本: {text[:500]}")
                
                # 🔥 尝试逐个提取 JSON 对象
                data = self._extract_json_objects(original_text)
                if data:
                    logger.info(f"[{self.name}] 通过逐个提取恢复了 {len(data)} 个决策")
            
            if data is None:
                data = []
            
            # 确保是数组
            if not isinstance(data, list):
                # 可能是单个对象，包装成数组
                data = [data]
            
            # 解析每个决策
            results = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                # 获取 symbol（支持多种字段名）
                symbol = item.get("symbol") or item.get("Symbol") or item.get("SYMBOL") or ""
                if not symbol:
                    continue
                
                action = str(item.get("action", item.get("Action", "wait"))).lower()
                valid_actions = ["open_long", "open_short", "close_long", "close_short", "hold", "wait"]
                if action not in valid_actions:
                    # 尝试映射常见的变体
                    action_map = {
                        "buy": "open_long",
                        "long": "open_long", 
                        "sell": "open_short",
                        "short": "open_short",
                        "close": "hold"
                    }
                    action = action_map.get(action, "wait")
                
                try:
                    confidence = float(item.get("confidence", item.get("Confidence", 0)))
                except (ValueError, TypeError):
                    confidence = 0
                confidence = min(100, max(0, confidence))
                
                try:
                    leverage = int(item.get("leverage", item.get("Leverage", 1)))
                except (ValueError, TypeError):
                    leverage = 1
                leverage = min(20, max(1, leverage))
                
                try:
                    position_size_usd = float(item.get("position_size_usd", item.get("position_size", 0)))
                except (ValueError, TypeError):
                    position_size_usd = 0
                position_size_usd = max(0, position_size_usd)
                
                results.append({
                    "symbol": symbol,
                    "signal": action,
                    "confidence": confidence,
                    "reasoning": str(item.get("reasoning", item.get("Reasoning", "")))[:150],
                    "stop_loss": item.get("stop_loss", item.get("stopLoss")),
                    "take_profit": item.get("take_profit", item.get("takeProfit")),
                    "position_size_usd": position_size_usd,
                    "leverage": leverage
                })
            
            logger.info(f"[{self.name}] 批量解析完成: {len(results)} 个决策, symbols: {[r['symbol'] for r in results]}")
            return results
            
        except Exception as e:
            logger.error(f"[{self.name}] 批量解析异常: {e}, response: {response[:300]}")
            # 最后的兜底：尝试从原始响应提取
            try:
                fallback = self._extract_json_objects(response)
                if fallback:
                    logger.info(f"[{self.name}] 兜底提取恢复了 {len(fallback)} 个决策")
                    return [{
                        "symbol": item.get("symbol", ""),
                        "signal": str(item.get("action", "wait")).lower(),
                        "confidence": float(item.get("confidence", 0)),
                        "reasoning": str(item.get("reasoning", ""))[:150],
                        "stop_loss": item.get("stop_loss"),
                        "take_profit": item.get("take_profit"),
                        "position_size_usd": float(item.get("position_size_usd", 0)),
                        "leverage": int(item.get("leverage", 1))
                    } for item in fallback if item.get("symbol")]
            except Exception:
                pass
            return []
    
    async def get_batch_decisions(
        self,
        contexts: List[MarketContext],
        user_prompt: str = "",
        arena_context: Optional[Dict] = None,
        sentiment: Optional[Dict] = None,
        positions: List[Dict] = None,  # 当前持仓列表
        balance_info: Dict = None  # 🔥 新增：账户余额信息
    ) -> List[AIDecisionResult]:
        """
        批量获取多个币种的决策（一次 API 调用）
        
        参数:
            contexts: 多个币种的市场上下文列表
            user_prompt: 用户提示词
            arena_context: 竞技场上下文
            sentiment: 市场情绪数据
            positions: 当前持仓列表（用于判断是否需要平仓）
            balance_info: 账户余额信息（初始资金、已实现盈亏、可用余额）
        
        返回:
            每个币种的决策结果列表
        """
        start_time = time.perf_counter()
        
        if not contexts:
            return []
        
        try:
            messages = self._build_batch_messages(
                contexts, user_prompt, arena_context, sentiment, positions, balance_info
            )
            content, thinking = await self._call_api(messages)
            parsed_list = self._parse_batch_response(content)
            latency = (time.perf_counter() - start_time) * 1000
            
            # 构建结果，按 symbol 匹配（增强匹配逻辑）
            symbol_to_parsed = {p["symbol"]: p for p in parsed_list}
            
            # 预处理：创建多种格式的映射
            normalized_map = {}
            for key, val in symbol_to_parsed.items():
                # 原始 key
                normalized_map[key.upper()] = val
                # 去掉所有分隔符
                clean_key = key.upper().replace("/", "").replace(":", "").replace("-", "")
                normalized_map[clean_key] = val
                # 只保留基础币种（如 BTC, ETH）
                base = clean_key.replace("USDT", "").replace("PERP", "")
                if base:
                    normalized_map[base] = val
            
            results = []
            for ctx in contexts:
                parsed = None
                
                # 尝试多种匹配方式
                symbol_variants = [
                    ctx.symbol.upper(),
                    ctx.symbol.upper().replace("/", "").replace(":", ""),
                    ctx.symbol.split("/")[0].upper(),  # 只取基础币种如 BTC
                ]
                
                for variant in symbol_variants:
                    if variant in normalized_map:
                        parsed = normalized_map[variant]
                        break
                
                if parsed:
                    results.append(AIDecisionResult(
                        agent_name=self.name,
                        signal=parsed["signal"],
                        confidence=parsed["confidence"],
                        reasoning=parsed["reasoning"],
                        thinking=thinking,
                        stop_loss=parsed["stop_loss"],
                        take_profit=parsed["take_profit"],
                        position_size_usd=parsed["position_size_usd"],
                        leverage=parsed["leverage"],
                        latency_ms=latency / len(contexts)  # 平均延迟
                    ))
                else:
                    # 没有匹配到，返回默认 wait
                    logger.warning(f"[{self.name}] 批量分析未匹配到 {ctx.symbol}，AI 返回的 symbols: {list(symbol_to_parsed.keys())}")
                    results.append(AIDecisionResult(
                        agent_name=self.name,
                        signal="wait",
                        confidence=0,
                        reasoning=f"批量分析未返回 {ctx.symbol} 的结果",
                        latency_ms=latency / len(contexts)
                    ))
            
            logger.debug(f"[{self.name}] 批量分析 {len(contexts)} 个币种完成 | {latency:.0f}ms")
            return results
            
        except Exception as e:
            latency = (time.perf_counter() - start_time) * 1000
            logger.error(f"[{self.name}] 批量决策失败: {e}")
            # 返回所有币种的错误结果
            return [
                AIDecisionResult(
                    agent_name=self.name,
                    signal="wait",
                    confidence=0,
                    reasoning=str(e)[:100],
                    latency_ms=latency / len(contexts),
                    error=str(e)
                )
                for _ in contexts
            ]


# ============================================================================
# DeepSeek Agent - 处理 <think> 标签
# ============================================================================

class DeepSeekAgent(BaseAgent):
    """DeepSeek AI Agent"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="deepseek",
            api_key=api_key or os.getenv("DEEPSEEK_API_KEY", ""),
            api_base="https://api.deepseek.com/v1"
        )
        self.model = "deepseek-chat"  # 通用模型，deepseek-reasoner 需要特殊权限
    
    def _extract_thinking(self, content: str) -> Tuple[str, str]:
        """提取 <think> 标签内容"""
        thinking = ""
        result = content
        
        # 匹配 <think>...</think>
        pattern = r'<think>(.*?)</think>'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            thinking = match.group(1).strip()
            result = re.sub(pattern, '', content, flags=re.DOTALL).strip()
        
        return result, thinking
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用 DeepSeek API"""
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            content = data["choices"][0]["message"]["content"]
            # 提取思考过程
            result, thinking = self._extract_thinking(content)
            return result, thinking


# ============================================================================
# Qwen Agent - DashScope
# ============================================================================

class QwenAgent(BaseAgent):
    """通义千问 AI Agent"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="qwen",
            api_key=api_key or os.getenv("DASHSCOPE_API_KEY", ""),
            api_base="https://dashscope.aliyuncs.com/api/v1"
        )
        self.model = "qwen-max"
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用 DashScope API"""
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 未配置")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": {"messages": messages},
            "parameters": {
                "temperature": 0.3,
                "max_tokens": 800,
                "result_format": "message"
            }
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/services/aigc/text-generation/generation",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            if "output" in data:
                content = data["output"]["choices"][0]["message"]["content"]
                return content, ""
            raise ValueError(f"Unexpected response: {data}")


# ============================================================================
# Perplexity Agent - 带搜索能力
# ============================================================================

class PerplexityAgent(BaseAgent):
    """Perplexity AI Agent（带实时搜索）"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="perplexity",
            api_key=api_key or os.getenv("PERPLEXITY_API_KEY", ""),
            api_base="https://api.perplexity.ai"
        )
        # Perplexity 支持的模型: sonar, sonar-pro, sonar-reasoning
        self.model = "sonar"
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用 Perplexity API"""
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY 未配置")
        
        # 增强 system prompt，要求搜索最新新闻
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            enhanced_messages[0]["content"] += "\n\n请搜索最新的加密货币市场新闻和情绪，结合技术分析给出建议。"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": enhanced_messages,
            "temperature": 0.3,
            "max_tokens": 800
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text[:200] if response.text else "Unknown error"
                raise ValueError(f"Perplexity API 错误 {response.status_code}: {error_text}")
            
            # 解析 JSON
            try:
                data = response.json()
            except Exception as e:
                raise ValueError(f"Perplexity 返回非 JSON: {response.text[:100]}")
            
            return data["choices"][0]["message"]["content"], ""


# ============================================================================
# GPT Agent
# ============================================================================

class GPTAgent(BaseAgent):
    """OpenAI GPT Agent"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="gpt",
            api_key=api_key or os.getenv("OPENAI_API_KEY", ""),
            api_base="https://api.openai.com/v1"
        )
        self.model = "gpt-4o-mini"
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY 未配置")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 800
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"], ""


# ============================================================================
# Claude Agent
# ============================================================================

class ClaudeAgent(BaseAgent):
    """Anthropic Claude Agent"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="claude",
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY", ""),
            api_base="https://api.anthropic.com/v1"
        )
        self.model = "claude-3-haiku-20240307"
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY 未配置")
        
        system_msg = ""
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_msg = msg["content"]
            else:
                user_messages.append(msg)
        
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": self.model,
            "max_tokens": 800,
            "system": system_msg,
            "messages": user_messages
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"], ""


# ============================================================================
# SparkLite Agent - 讯飞星火 (OpenAI 兼容接口)
# ============================================================================

class SparkLiteAgent(BaseAgent):
    """讯飞星火 Spark Lite Agent（OpenAI 兼容接口）"""
    
    def __init__(self, api_key: str = ""):
        super().__init__(
            name="spark_lite",
            api_key=api_key or os.getenv("SPARK_API_PASSWORD", ""),
            api_base="https://spark-api-open.xf-yun.com/v1"
        )
        # Spark Lite 模型标识
        self.model = "lite"
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用讯飞星火 OpenAI 兼容接口"""
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("SPARK_API_PASSWORD 未配置")
        
        # 🔥 为 SparkLite 增强 prompt，因为它的模型能力较弱
        enhanced_messages = messages.copy()
        if enhanced_messages and enhanced_messages[0]["role"] == "system":
            # 简化并明确指令
            enhanced_messages[0]["content"] = enhanced_messages[0]["content"].replace(
                '"action": "open_long | open_short | close_long | close_short | hold | wait"',
                '"action": "wait"  // 必须选择: open_long, open_short, hold, wait 之一'
            ).replace(
                '"type": "market|limit"',
                '"type": "market"'
            )
            enhanced_messages[0]["content"] += """

【重要】action 必须是以下之一：open_long（做多）, open_short（做空）, hold（持有）, wait（等待）。不要返回模板值！"""
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": enhanced_messages,
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text[:200] if response.text else "Unknown error"
                raise ValueError(f"SparkLite API 错误 {response.status_code}: {error_text}")
            
            # 解析 JSON
            try:
                data = response.json()
            except Exception as e:
                raise ValueError(f"SparkLite 返回非 JSON: {response.text[:100]}")
            
            content = data["choices"][0]["message"]["content"]
            return content, ""


# ============================================================================
# Hunyuan Agent - 腾讯混元 (OpenAI 兼容接口)
# ============================================================================

# 混元模型白名单（只允许免费模型）
HUNYUAN_ALLOWED_MODELS = {"hunyuan-lite"}


class HunyuanAgent(BaseAgent):
    """
    腾讯混元 Hunyuan Agent（OpenAI 兼容接口）
    
    注意事项：
    - 默认使用 hunyuan-lite（免费模型），强制白名单限制
    - 免费资源包耗尽后默认不会自动转后付费
    - 如需彻底避免扣费，建议在混元控制台关闭后付费
    """
    
    def __init__(self, api_key: str = ""):
        # 从环境变量读取配置
        base_url = os.getenv("HUNYUAN_BASE_URL", "https://api.hunyuan.cloud.tencent.com/v1")
        model = os.getenv("HUNYUAN_MODEL", "hunyuan-lite")
        
        # 🔥 强制模型白名单检查
        if model not in HUNYUAN_ALLOWED_MODELS:
            raise ValueError(
                f"Hunyuan 模型 '{model}' 不在白名单中！"
                f"只允许免费模型: {HUNYUAN_ALLOWED_MODELS}。"
                f"请修改 HUNYUAN_MODEL 环境变量或使用默认值 hunyuan-lite。"
            )
        
        super().__init__(
            name="hunyuan",
            api_key=api_key or os.getenv("HUNYUAN_API_KEY", ""),
            api_base=base_url
        )
        self.model = model
        
        # 后付费风险提示
        afterpay_enabled = os.getenv("HUNYUAN_AFTERPAY_ENABLED", "false").lower() == "true"
        if afterpay_enabled:
            logger.warning(
                "⚠️ [Hunyuan] HUNYUAN_AFTERPAY_ENABLED=true，已开启后付费！"
                "免费资源包耗尽后将产生费用。建议在混元控制台关闭后付费以避免扣费风险。"
            )
        else:
            logger.info(
                "✅ [Hunyuan] 使用免费模型 hunyuan-lite，后付费已关闭。"
                "免费资源包耗尽后请求将失败而非扣费。"
            )
    
    async def _call_api(self, messages: List[Dict]) -> Tuple[str, str]:
        """调用腾讯混元 OpenAI 兼容接口"""
        try:
            import httpx
        except ImportError:
            raise ImportError("请安装 httpx: pip install httpx")
        
        if not self.api_key:
            raise ValueError("HUNYUAN_API_KEY 未配置")
        
        # 再次检查模型（防止运行时被修改）
        if self.model not in HUNYUAN_ALLOWED_MODELS:
            raise ValueError(f"Hunyuan 模型 '{self.model}' 不允许使用，只能用: {HUNYUAN_ALLOWED_MODELS}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            )
            
            # 检查响应状态
            if response.status_code != 200:
                error_text = response.text[:200] if response.text else "Unknown error"
                # 检查是否是资源包耗尽
                if "quota" in error_text.lower() or "limit" in error_text.lower():
                    raise ValueError(
                        f"Hunyuan 免费资源包可能已耗尽: {error_text}。"
                        "请检查混元控制台的资源包状态。"
                    )
                raise ValueError(f"Hunyuan API 错误 {response.status_code}: {error_text}")
            
            # 解析 JSON
            try:
                data = response.json()
            except Exception as e:
                raise ValueError(f"Hunyuan 返回非 JSON: {response.text[:100]}")
            
            content = data["choices"][0]["message"]["content"]
            return content, ""


# ============================================================================
# Agent 工厂
# ============================================================================

AGENT_CLASSES = {
    "deepseek": DeepSeekAgent,
    "qwen": QwenAgent,
    "perplexity": PerplexityAgent,
    "gpt": GPTAgent,
    "claude": ClaudeAgent,
    "spark_lite": SparkLiteAgent,
    "hunyuan": HunyuanAgent,
}


def create_agent(agent_name: str, api_key: str = "") -> BaseAgent:
    """创建 Agent 实例"""
    agent_class = AGENT_CLASSES.get(agent_name.lower())
    if not agent_class:
        raise ValueError(f"未知的 Agent: {agent_name}")
    return agent_class(api_key)


def get_available_agents() -> List[str]:
    """获取可用的 Agent 列表"""
    return list(AGENT_CLASSES.keys())
