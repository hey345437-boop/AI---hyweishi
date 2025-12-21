"""
Arena Scheduler - AI 竞技场精准调度器

核心特点：
1. 精准 00 秒触发（与 K 线收盘对齐）
2. 异步并发调用多个 AI
3. 线程安全，不阻塞 Streamlit UI
"""

import os
import asyncio
import time
import threading
import queue
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


@dataclass
class BattleResult:
    """单轮对战结果"""
    timestamp: int
    symbol: str
    timeframe: str
    current_price: float
    decisions: List[Dict]
    consensus: Optional[str]
    latency_ms: float


# ============================================================================
# 精准时间对齐工具
# ============================================================================

def timeframe_to_seconds(timeframe: str) -> int:
    """将 K 线周期转换为秒数"""
    tf_map = {
        '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
        '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600, '8h': 28800,
        '12h': 43200, '1D': 86400, '3D': 259200, '1W': 604800
    }
    return tf_map.get(timeframe, 300)


def wait_until_next_candle(timeframe: str = '1m', stop_event: threading.Event = None):
    """
    等待到下一根 K 线收盘时刻（可中断）
    
    例如：
    - 5m 周期：等待到 XX:00, XX:05, XX:10, XX:15...
    - 1h 周期：等待到整点
    - 4h 周期：等待到 00:00, 04:00, 08:00, 12:00...
    
    参数:
        timeframe: K 线周期
        stop_event: 停止事件，如果设置则提前退出等待
    
    返回实际等待的秒数（如果被中断返回 -1）
    """
    interval_sec = timeframe_to_seconds(timeframe)
    now = datetime.now()
    
    # 计算当前时间戳
    current_ts = now.timestamp()
    
    # 计算下一个对齐时刻
    next_ts = (int(current_ts / interval_sec) + 1) * interval_sec
    
    seconds_to_wait = next_ts - current_ts
    
    if seconds_to_wait > 0:
        if stop_event:
            # 可中断的等待：每秒检查一次停止信号
            waited = 0
            while waited < seconds_to_wait:
                if stop_event.is_set():
                    return -1  # 被中断
                time.sleep(min(1, seconds_to_wait - waited))
                waited += 1
        else:
            time.sleep(seconds_to_wait)
    
    return seconds_to_wait


def get_next_trigger_time(timeframe: str = '1m') -> datetime:
    """获取下一次触发时间"""
    interval_sec = timeframe_to_seconds(timeframe)
    now = datetime.now()
    current_ts = now.timestamp()
    next_ts = (int(current_ts / interval_sec) + 1) * interval_sec
    return datetime.fromtimestamp(next_ts)


# ============================================================================
# Arena Scheduler 核心类
# ============================================================================

class ArenaScheduler:
    """AI 竞技场调度器"""
    
    def __init__(
        self,
        agents: List[str] = None,
        api_keys: Dict[str, str] = None,
        ai_takeover: bool = False
    ):
        self.agents = agents or ['deepseek', 'qwen', 'perplexity']
        self.api_keys = api_keys or {}
        self.ai_takeover_enabled = ai_takeover  # AI 托管开关
        
        self._db_manager = None
        self._indicator_calculator = None
        self._data_source = None
        self._agent_instances = {}
        
        # P1: 健康监控状态
        self._last_heartbeat = time.time()
        self._api_failure_counts: Dict[str, int] = {}  # agent_name -> 连续失败次数
        self._total_cycles = 0
        self._successful_cycles = 0
        self._last_error: Optional[str] = None
    
    def _get_db_manager(self):
        if self._db_manager is None:
            from ai_db_manager import get_ai_db_manager
            self._db_manager = get_ai_db_manager()
        return self._db_manager
    
    def _get_indicator_calculator(self):
        if self._indicator_calculator is None:
            from ai_indicators import IndicatorCalculator
            self._indicator_calculator = IndicatorCalculator()
        return self._indicator_calculator
    
    def _get_data_source(self):
        if self._data_source is None:
            from ai_indicators import get_data_source
            self._data_source = get_data_source()
        return self._data_source
    
    def _get_agent(self, agent_name: str):
        if agent_name not in self._agent_instances:
            from ai_brain import create_agent
            api_key = self.api_keys.get(agent_name, "")
            self._agent_instances[agent_name] = create_agent(agent_name, api_key)
        return self._agent_instances[agent_name]
    
    def _fetch_sentiment(self) -> Optional[Dict[str, Any]]:
        """
        获取市场情绪数据 (Fear & Greed Index)
        
        返回:
            {'value': 45, 'classification': 'Fear', 'timestamp': ...}
        """
        try:
            import requests
            response = requests.get(
                "https://api.alternative.me/fng/",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data and 'data' in data and len(data['data']) > 0:
                    fng = data['data'][0]
                    return {
                        'value': fng.get('value', 'N/A'),
                        'classification': fng.get('value_classification', '未知'),
                        'timestamp': fng.get('timestamp', '')
                    }
        except Exception as e:
            logger.debug(f"[Arena] 获取情绪数据失败: {e}")
        return None
    
    async def _fetch_market_data(
        self, symbol: str, timeframe: str, limit: int = 500
    ) -> Optional[Dict[str, Any]]:
        """获取单周期市场数据和指标（兼容旧接口）"""
        return await self._fetch_multi_timeframe_data(symbol, [timeframe], limit)
    
    async def _fetch_multi_timeframe_data(
        self, symbol: str, timeframes: List[str], limit: int = 500
    ) -> Optional[Dict[str, Any]]:
        """
        获取多周期市场数据和指标
        
        参数:
            symbol: 交易对
            timeframes: 周期列表，如 ['5m', '15m', '1h']
            limit: K 线数量
        
        返回:
            包含所有周期数据的字典
        """
        try:
            data_source = self._get_data_source()
            calculator = self._get_indicator_calculator()
            
            # 获取所有周期的数据
            all_timeframes_data = {}
            current_price = None
            formatted_parts = []
            
            for tf in timeframes:
                ohlcv = data_source.fetch_ohlcv(symbol, tf, limit)
                if not ohlcv:
                    logger.warning(f"[Arena] 获取 {symbol} {tf} 数据失败")
                    continue
                
                # 使用最短周期的价格作为当前价格
                if current_price is None:
                    current_price = ohlcv[-1][4]
                
                indicators = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR']
                latest_values = calculator.get_latest_values(indicators, ohlcv)
                formatted = calculator.format_for_ai(latest_values, symbol, tf)
                
                all_timeframes_data[tf] = {
                    'ohlcv': ohlcv,
                    'indicators': latest_values,
                    'formatted': formatted
                }
                formatted_parts.append(f"=== {tf} 周期 ===\n{formatted}")
            
            if not all_timeframes_data:
                return None
            
            # 合并所有周期的格式化文本
            combined_formatted = "\n\n".join(formatted_parts)
            
            # 主周期（第一个）的数据
            main_tf = timeframes[0]
            main_data = all_timeframes_data.get(main_tf, {})
            
            # 获取市场情绪数据
            sentiment = self._fetch_sentiment()
            
            return {
                'symbol': symbol,
                'timeframe': main_tf,  # 主周期
                'timeframes': timeframes,  # 所有周期
                'current_price': current_price,
                'ohlcv': main_data.get('ohlcv', []),  # 主周期 K 线
                'indicators': main_data.get('indicators', {}),  # 主周期指标
                'formatted_indicators': combined_formatted,  # 所有周期的格式化文本
                'multi_timeframe_data': all_timeframes_data,  # 所有周期的原始数据
                'sentiment': sentiment  # 市场情绪数据
            }
        except Exception as e:
            logger.error(f"[Arena] 获取市场数据失败: {e}")
            return None
    
    async def _call_single_agent(
        self, agent_name: str, context, user_prompt: str, arena_context: Dict = None
    ) -> Dict:
        """调用单个 AI（带竞技场上下文 + P1 失败计数）"""
        try:
            agent = self._get_agent(agent_name)
            result = await agent.get_decision(context, user_prompt, arena_context=arena_context)
            
            # P1: 成功时重置失败计数
            self._api_failure_counts[agent_name] = 0
            
            return {
                'agent_name': agent_name,
                'signal': result.signal,
                'confidence': result.confidence,
                'reasoning': result.reasoning,
                'thinking': result.thinking,
                'entry_price': result.entry_price,
                'stop_loss': result.stop_loss,
                'take_profit': result.take_profit,
                'position_size_usd': result.position_size_usd,
                'leverage': result.leverage,
                'latency_ms': result.latency_ms,
                'error': result.error
            }
        except Exception as e:
            logger.error(f"[{agent_name}] 调用失败: {e}")
            
            # P1: 累计失败计数
            self._api_failure_counts[agent_name] = self._api_failure_counts.get(agent_name, 0) + 1
            fail_count = self._api_failure_counts[agent_name]
            
            # P1: 连续失败告警（阈值 3 次）
            if fail_count >= 3:
                logger.warning(f"[告警] {agent_name} 连续 API 失败 {fail_count} 次!")
                self._last_error = f"{agent_name} 连续失败 {fail_count} 次: {str(e)}"
            
            return {
                'agent_name': agent_name,
                'signal': 'HOLD',
                'confidence': 0.0,
                'reasoning': '',
                'thinking': '',
                'latency_ms': 0,
                'error': str(e)
            }
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        P1: 获取调度器健康状态
        
        返回:
            {
                'is_healthy': True/False,
                'last_heartbeat': timestamp,
                'heartbeat_age_sec': 秒数,
                'total_cycles': 总周期数,
                'successful_cycles': 成功周期数,
                'success_rate': 成功率,
                'api_failures': {agent: count},
                'last_error': 最后错误信息,
                'alerts': [告警列表]
            }
        """
        now = time.time()
        heartbeat_age = now - self._last_heartbeat
        
        # 计算成功率
        success_rate = (self._successful_cycles / self._total_cycles * 100) if self._total_cycles > 0 else 100
        
        # 生成告警
        alerts = []
        
        # 心跳超时告警（5 分钟无心跳）
        if heartbeat_age > 300:
            alerts.append(f"[严重] 心跳超时 {heartbeat_age:.0f} 秒")
        
        # API 连续失败告警
        for agent, count in self._api_failure_counts.items():
            if count >= 3:
                alerts.append(f"[警告] {agent} 连续失败 {count} 次")
        
        # 成功率过低告警
        if self._total_cycles >= 10 and success_rate < 80:
            alerts.append(f"[警告] 成功率 {success_rate:.1f}% 低于 80%")
        
        return {
            'is_healthy': len(alerts) == 0,
            'last_heartbeat': self._last_heartbeat,
            'heartbeat_age_sec': heartbeat_age,
            'total_cycles': self._total_cycles,
            'successful_cycles': self._successful_cycles,
            'success_rate': success_rate,
            'api_failures': dict(self._api_failure_counts),
            'last_error': self._last_error,
            'alerts': alerts
        }
    
    async def run_battle_cycle(
        self,
        symbol: str,
        timeframe: str = "1m",
        timeframes: List[str] = None,
        user_prompt: str = "",
        kline_count: int = 500
    ) -> BattleResult:
        """
        运行一轮 AI 对战
        
        参数:
            symbol: 交易对
            timeframe: 主周期（用于触发和记录）
            timeframes: 所有要分析的周期列表，如 ['5m', '15m', '1h']
            user_prompt: 用户提示词
            kline_count: K 线数量
        """
        start_time = time.perf_counter()
        timestamp = int(time.time() * 1000)
        
        # P1: 更新心跳和周期计数
        self._last_heartbeat = time.time()
        self._total_cycles += 1
        
        # 如果没有指定多周期，使用单周期
        if timeframes is None:
            timeframes = [timeframe]
        
        tf_display = ', '.join(timeframes)
        logger.debug(f"[Arena] 对战 {symbol} @ [{tf_display}]")
        
        # 1. 获取多周期市场数据
        market_data = await self._fetch_multi_timeframe_data(symbol, timeframes, kline_count)
        if not market_data:
            return BattleResult(
                timestamp=timestamp, symbol=symbol, timeframe=timeframe,
                current_price=0, decisions=[], consensus=None, latency_ms=0
            )
        
        # 2. 构建上下文
        from ai_brain import MarketContext
        context = MarketContext(
            symbol=market_data['symbol'],
            timeframe=market_data['timeframe'],
            current_price=market_data['current_price'],
            ohlcv=market_data['ohlcv'],
            indicators=market_data['indicators'],
            formatted_indicators=market_data['formatted_indicators'],
            sentiment=market_data.get('sentiment')  # 市场情绪数据
        )
        
        # 3. 🔥 获取每个 AI 的竞技场上下文（排名、对手信息）
        db = self._get_db_manager()
        arena_contexts = {}
        for agent in self.agents:
            arena_contexts[agent] = db.get_arena_context(agent)
        
        # 4. 并发调用所有 AI（带竞技场上下文）
        tasks = [
            self._call_single_agent(agent, context, user_prompt, arena_contexts.get(agent))
            for agent in self.agents
        ]
        decisions = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理异常
        processed = []
        for i, result in enumerate(decisions):
            if isinstance(result, Exception):
                processed.append({
                    'agent_name': self.agents[i],
                    'signal': 'HOLD', 'confidence': 0.0,
                    'reasoning': '', 'thinking': '',
                    'error': str(result)
                })
            else:
                processed.append(result)
        
        # 4. 存储到数据库（P1: 保存后回填 decision_id 用于审计追踪）
        db = self._get_db_manager()
        from ai_db_manager import AIDecision
        import json
        
        for d in processed:
            if d.get('error'):
                continue
            
            decision = AIDecision(
                timestamp=timestamp,
                agent_name=d['agent_name'],
                symbol=symbol,
                signal=d['signal'],
                price=market_data['current_price'],
                confidence=d['confidence'],
                reasoning=d['reasoning'],
                thinking=d.get('thinking', ''),
                user_prompt_snapshot=user_prompt,
                indicators_snapshot=json.dumps(market_data['indicators']),
                timeframe=timeframe,
                latency_ms=d.get('latency_ms', 0)
            )
            decision_id = db.save_decision(decision)
            # P1: 回填 decision_id，形成"决策→执行→结果"闭环
            d['decision_id'] = decision_id
        
        # 5. 计算共识
        consensus = self._calculate_consensus(processed)
        
        # 6. 执行交易（每个 AI 独立执行自己的决策）
        # 🔥 修改：不再等待共识，每个 AI 的 open_long/open_short 信号都会尝试执行
        await self._simulate_execution(processed, market_data['current_price'], symbol)
        
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.debug(f"[Arena] 完成 | 共识: {consensus} | {total_latency:.0f}ms")
        
        # P1: 更新成功计数
        self._successful_cycles += 1
        
        return BattleResult(
            timestamp=timestamp, symbol=symbol, timeframe=timeframe,
            current_price=market_data['current_price'],
            decisions=processed, consensus=consensus, latency_ms=total_latency
        )
    
    async def run_batch_battle_cycle(
        self,
        symbols: List[str],
        timeframe: str = "1m",
        timeframes: List[str] = None,
        user_prompt: str = "",
        kline_count: int = 100
    ) -> List[BattleResult]:
        """
        批量运行 AI 对战（一次 API 调用分析所有币种）
        
        相比单个分析，大幅减少 API 请求次数：
        - 单个模式：N 个币种 × M 个 AI = N×M 次请求
        - 批量模式：M 个 AI = M 次请求
        
        参数:
            symbols: 交易对列表
            timeframe: 主周期
            timeframes: 所有要分析的周期列表
            user_prompt: 用户提示词
            kline_count: K 线数量（批量模式建议 50-100）
        """
        start_time = time.perf_counter()
        timestamp = int(time.time() * 1000)
        
        # P1: 更新心跳和周期计数
        self._last_heartbeat = time.time()
        self._total_cycles += 1
        
        if timeframes is None:
            timeframes = [timeframe]
        
        logger.info(f"[Arena] 批量分析 {len(symbols)} 个币种 | AI: {self.agents}")
        
        # 1. 获取所有币种的市场数据
        from ai_brain import MarketContext
        contexts = []
        symbol_data_map = {}
        
        for symbol in symbols:
            market_data = await self._fetch_multi_timeframe_data(symbol, timeframes, kline_count)
            if market_data:
                ctx = MarketContext(
                    symbol=market_data['symbol'],
                    timeframe=market_data['timeframe'],
                    current_price=market_data['current_price'],
                    ohlcv=market_data['ohlcv'],
                    indicators=market_data['indicators'],
                    formatted_indicators=market_data['formatted_indicators'],
                    sentiment=market_data.get('sentiment')
                )
                contexts.append(ctx)
                symbol_data_map[symbol] = market_data
        
        if not contexts:
            logger.warning("[Arena] 批量分析：无法获取任何币种数据")
            return []
        
        # 2. 获取情绪数据（只获取一次）
        sentiment = self._fetch_sentiment()
        
        # 3. 获取竞技场上下文
        db = self._get_db_manager()
        arena_contexts = {agent: db.get_arena_context(agent) for agent in self.agents}
        
        # 🔥 4. 获取每个 AI 的当前持仓和账户余额
        agent_positions = {}
        agent_balances = {}
        INITIAL_BALANCE = 10000.0  # 初始资金
        
        for agent_name in self.agents:
            positions = db.get_open_positions(agent_name)
            agent_positions[agent_name] = positions
            
            # 🔥 计算可用余额 = 初始资金 + 已实现盈亏 - 当前持仓占用
            stats = db.get_stats(agent_name)
            realized_pnl = stats.total_pnl if stats else 0
            
            # 计算持仓占用金额
            position_used = sum(pos.get('qty', 0) for pos in positions)
            
            # 可用余额
            available_balance = INITIAL_BALANCE + realized_pnl - position_used
            agent_balances[agent_name] = {
                'initial': INITIAL_BALANCE,
                'realized_pnl': realized_pnl,
                'position_used': position_used,
                'available': max(0, available_balance)
            }
        
        # 5. 批量调用每个 AI（每个 AI 一次调用分析所有币种）
        all_results = []  # List[BattleResult]
        
        for agent_name in self.agents:
            try:
                agent = self._get_agent(agent_name)
                arena_ctx = arena_contexts.get(agent_name)
                positions = agent_positions.get(agent_name, [])
                balance_info = agent_balances.get(agent_name, {})
                
                # 调用批量分析（传递持仓和余额信息）
                decisions = await agent.get_batch_decisions(
                    contexts=contexts,
                    user_prompt=user_prompt,
                    arena_context=arena_ctx,
                    sentiment=sentiment,
                    positions=positions,  # 🔥 传递当前持仓
                    balance_info=balance_info  # 🔥 新增：传递余额信息
                )
                
                # 重置失败计数
                self._api_failure_counts[agent_name] = 0
                
                # 保存每个币种的决策到数据库
                from ai_db_manager import AIDecision
                import json as json_module
                
                for i, decision in enumerate(decisions):
                    if i >= len(contexts):
                        break
                    
                    ctx = contexts[i]
                    symbol = ctx.symbol
                    market_data = symbol_data_map.get(symbol, {})
                    
                    # 保存到数据库
                    db_decision = AIDecision(
                        timestamp=timestamp,
                        agent_name=agent_name,
                        symbol=symbol,
                        signal=decision.signal,
                        price=ctx.current_price,
                        confidence=decision.confidence,
                        reasoning=decision.reasoning,
                        thinking=decision.thinking or '',
                        user_prompt_snapshot=user_prompt,
                        indicators_snapshot=json_module.dumps(market_data.get('indicators', {})),
                        timeframe=timeframe,
                        latency_ms=decision.latency_ms
                    )
                    decision_id = db.save_decision(db_decision)
                    
                    # 构建决策字典
                    d = {
                        'agent_name': agent_name,
                        'signal': decision.signal,
                        'confidence': decision.confidence,
                        'reasoning': decision.reasoning,
                        'thinking': decision.thinking or '',
                        'stop_loss': decision.stop_loss,
                        'take_profit': decision.take_profit,
                        'position_size_usd': decision.position_size_usd,
                        'leverage': decision.leverage,
                        'latency_ms': decision.latency_ms,
                        'decision_id': decision_id,
                        'error': decision.error
                    }
                    
                    # 查找或创建该币种的 BattleResult
                    existing = next((r for r in all_results if r.symbol == symbol), None)
                    if existing:
                        existing.decisions.append(d)
                    else:
                        all_results.append(BattleResult(
                            timestamp=timestamp,
                            symbol=symbol,
                            timeframe=timeframe,
                            current_price=ctx.current_price,
                            decisions=[d],
                            consensus=None,
                            latency_ms=0
                        ))
                
            except Exception as e:
                logger.error(f"[Arena] {agent_name} 批量分析失败: {e}")
                self._api_failure_counts[agent_name] = self._api_failure_counts.get(agent_name, 0) + 1
        
        # 5. 计算每个币种的共识
        for result in all_results:
            result.consensus = self._calculate_consensus(result.decisions)
            
            # 🔥 修改：每个 AI 独立执行自己的决策，不再等待共识
            # 风控检查会在 _execute_trades 中进行
            await self._simulate_execution(result.decisions, result.current_price, result.symbol)
        
        total_latency = (time.perf_counter() - start_time) * 1000
        logger.info(f"[Arena] 批量分析完成 | {len(symbols)} 币种 | {len(self.agents)} AI | {total_latency:.0f}ms")
        
        # 更新每个结果的延迟
        for result in all_results:
            result.latency_ms = total_latency / len(all_results) if all_results else 0
        
        self._successful_cycles += 1
        return all_results
    
    def _calculate_consensus(self, decisions: List[Dict]) -> Optional[str]:
        """计算共识信号"""
        buy_count, sell_count = 0, 0
        buy_conf, sell_conf = 0.0, 0.0
        
        for d in decisions:
            if d.get('error'):
                continue
            signal = d.get('signal', 'HOLD').lower()
            conf = d.get('confidence', 0)
            
            if signal in ['buy', 'open_long']:
                buy_count += 1
                buy_conf += conf
            elif signal in ['sell', 'open_short']:
                sell_count += 1
                sell_conf += conf
        
        total = len([d for d in decisions if not d.get('error')])
        if total == 0:
            return None
        
        # 多数决 + 置信度 > 60
        if buy_count > total / 2 and (buy_conf / buy_count if buy_count else 0) > 60:
            return 'BUY'
        if sell_count > total / 2 and (sell_conf / sell_count if sell_count else 0) > 60:
            return 'SELL'
        
        return 'HOLD'
    
    async def _execute_trades(self, decisions: List[Dict], price: float, symbol: str):
        """
        执行交易（实盘或模拟）
        
        根据主界面运行模式和 AI 托管状态决定：
        - 主界面 live + AI 托管启用 → 实盘交易
        - 其他情况 → 模拟交易（虚拟资金）
        
        支持的信号类型：
        - open_long / buy: 开多仓
        - open_short / sell: 开空仓
        - close_long: 平多仓
        - close_short: 平空仓
        """
        # 导入桥接模块
        try:
            from ai_trade_bridge import (
                get_ai_trade_bridge, AITradeSignal, AITradeMode
            )
            has_bridge = True
        except ImportError:
            has_bridge = False
            logger.warning("[Arena] ai_trade_bridge 模块不可用，使用纯模拟模式")
        
        # 获取 AI 托管状态
        ai_takeover = self.ai_takeover_enabled
        
        # 🔥 获取最大持仓数量限制（从提示词预设中提取）
        max_positions = self._get_max_positions_limit()
        
        # 🔥 支持的交易信号（包括平仓信号）
        valid_signals = ['buy', 'sell', 'open_long', 'open_short', 'close_long', 'close_short']
        
        for d in decisions:
            signal = d.get('signal', '').lower()
            agent = d.get('agent_name', 'unknown')
            
            # 🔥 详细日志：打印每个决策的完整信息
            logger.info(f"[Arena] 检查决策: {agent} | signal={signal} | confidence={d.get('confidence')} | size={d.get('position_size_usd')} | error={d.get('error')}")
            
            # 检查是否是有效的交易信号
            if d.get('error') or signal not in valid_signals:
                if d.get('error'):
                    logger.debug(f"[Arena] {agent} 跳过（有错误）: {d.get('error')}")
                elif signal:
                    logger.info(f"[Arena] {agent} 跳过（信号为 {signal}，不是交易信号）")
                continue
            
            # 统一信号格式
            if signal in ['buy', 'open_long']:
                signal_type = 'open_long'
            elif signal in ['sell', 'open_short']:
                signal_type = 'open_short'
            elif signal == 'close_long':
                signal_type = 'close_long'
            elif signal == 'close_short':
                signal_type = 'close_short'
            else:
                continue
            
            # 🔥 开仓前检查持仓数量限制
            if signal_type.startswith('open_'):
                db = self._get_db_manager()
                current_positions = db.get_open_positions(agent)
                # 统计不同币种的持仓数量
                unique_symbols = set(p['symbol'] for p in current_positions)
                
                # 如果要开的币种已经有持仓，不算新增
                if symbol not in unique_symbols and len(unique_symbols) >= max_positions:
                    logger.warning(
                        f"[Arena] {agent} 跳过开仓 {symbol}：已持有 {len(unique_symbols)} 个币种，"
                        f"达到最大限制 {max_positions}"
                    )
                    continue
            
            # 🔥 开仓信号需要仓位，平仓信号不需要
            if signal_type.startswith('open_'):
                size = d.get('position_size_usd') or 100
            else:
                size = 0  # 平仓不需要仓位金额
            confidence = d.get('confidence', 0.5)
            
            # 🔥 添加详细日志
            logger.info(f"[Arena] 准备执行 {agent} {signal_type} {symbol} | 置信度: {confidence:.0f}% | 仓位: {size} USD")
            
            # P1: 获取 decision_id 用于审计追踪
            decision_id = d.get('decision_id')
            
            if has_bridge:
                # 使用桥接模块执行（自动判断实盘/模拟）
                bridge = get_ai_trade_bridge()
                
                # 🔥 止损止盈完全由 AI 决定，不设默认值
                stop_loss = d.get('stop_loss')
                take_profit = d.get('take_profit')
                rr_estimate = d.get('rr_estimate')
                
                trade_signal = AITradeSignal(
                    agent_name=agent,
                    symbol=symbol,
                    signal=signal_type,
                    confidence=confidence,
                    entry_price=price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    rr_estimate=rr_estimate,
                    position_size_usd=size,
                    leverage=d.get('leverage', 5),
                    reasoning=d.get('reasoning', ''),
                    decision_id=decision_id
                )
                
                result = bridge.execute_signal(trade_signal, ai_takeover=ai_takeover)
                
                if result.success:
                    mode_str = "实盘" if result.mode == AITradeMode.LIVE else "模拟"
                    logger.info(f"[Arena] {agent} {signal_type} {symbol} ({mode_str}) 执行成功")
                else:
                    logger.warning(f"[Arena] {agent} {signal_type} {symbol} 执行失败: {result.message}")
            else:
                # 回退到纯模拟模式（P1: 传递 decision_id）
                self._fallback_simulation(agent, symbol, signal_type, price, size, decision_id)
    
    def _get_max_positions_limit(self) -> int:
        """
        从提示词预设中获取最大持仓数量限制
        
        解析提示词中的"最多同时持仓 X 个币种"
        默认返回 5（如果无法解析）
        """
        import re
        
        try:
            from ai_config_manager import get_ai_config_manager
            config_mgr = get_ai_config_manager()
            prompt = config_mgr.get_effective_prompt()
            
            # 尝试从提示词中提取数字
            # 匹配模式：最多同时持仓 X 个币种
            match = re.search(r'最多同时持仓\s*(\d+)\s*个', prompt)
            if match:
                limit = int(match.group(1))
                logger.debug(f"[Arena] 从提示词解析到最大持仓限制: {limit}")
                return limit
        except Exception as e:
            logger.warning(f"[Arena] 解析最大持仓限制失败: {e}")
        
        # 默认限制
        return 5
    
    def _fallback_simulation(
        self, agent: str, symbol: str, signal: str, price: float, size: float,
        decision_id: Optional[int] = None
    ):
        """回退的纯模拟交易逻辑（P1: 支持 decision_id 审计追踪）"""
        db = self._get_db_manager()
        
        open_pos = db.get_open_positions(agent)
        has_pos = any(p['symbol'] == symbol for p in open_pos)
        
        # 支持新旧信号格式
        signal_lower = signal.lower()
        is_long = signal_lower in ['buy', 'open_long']
        is_short = signal_lower in ['sell', 'open_short']
        
        if is_long and not has_pos:
            db.open_position(
                agent, symbol, 'long', price, qty=size,
                signal_type=f"AI:{agent}", decision_id=decision_id
            )
        elif is_short:
            for pos in open_pos:
                if pos['symbol'] == symbol and pos['side'] == 'long':
                    db.close_position(pos['id'], price)
            if not has_pos:
                db.open_position(
                    agent, symbol, 'short', price, qty=size,
                    signal_type=f"AI:{agent}", decision_id=decision_id
                )
    
    # 兼容旧方法名
    async def _simulate_execution(self, decisions: List[Dict], price: float, symbol: str):
        """兼容旧方法名，实际调用 _execute_trades"""
        await self._execute_trades(decisions, price, symbol)


# ============================================================================
# 后台精准调度器（00 秒触发）
# ============================================================================

# 全局状态
_scheduler_thread: Optional[threading.Thread] = None
_scheduler_stop_event: Optional[threading.Event] = None
_latest_result: Optional[BattleResult] = None
_result_lock = threading.Lock()
_result_queue: queue.Queue = queue.Queue(maxsize=100)


class PrecisionScheduler:
    """
    精准调度器 - 每分钟 00 秒触发
    
    特点：
    1. 与 K 线收盘时间对齐
    2. 独立线程运行，不阻塞 UI
    3. 线程安全的结果存储
    4. 支持 AI 托管实盘交易（需主界面为实盘模式）
    5. 支持多周期分析（方案 B：最短周期触发，获取所有周期数据）
    """
    
    def __init__(
        self,
        symbols: List[str] = None,
        timeframe: str = "1m",
        timeframes: List[str] = None,
        agents: List[str] = None,
        api_keys: Dict[str, str] = None,
        user_prompt: str = "",
        ai_takeover: bool = False,
        on_result: Callable[[BattleResult], None] = None
    ):
        self.symbols = symbols or ["BTC/USDT:USDT"]
        # 多周期支持：timeframes 是所有要分析的周期列表
        # timeframe 是触发周期（最短周期）
        self.timeframes = timeframes or [timeframe]
        self.timeframe = self._get_shortest_timeframe(self.timeframes)
        self.agents = agents or ["deepseek", "qwen", "perplexity"]
        self.api_keys = api_keys or {}
        self.user_prompt = user_prompt
        self.ai_takeover = ai_takeover  # AI 托管开关
        self.on_result = on_result
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._scheduler: Optional[ArenaScheduler] = None
        self._last_trigger_ts: int = 0  # 上次触发的时间戳
    
    def _get_shortest_timeframe(self, timeframes: List[str]) -> str:
        """获取最短周期作为触发周期"""
        if not timeframes:
            return "5m"
        # 按秒数排序，取最短
        sorted_tfs = sorted(timeframes, key=lambda tf: timeframe_to_seconds(tf))
        return sorted_tfs[0]
    
    def _run_loop(self):
        """后台线程主循环 - 跟随 K 线周期触发"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        self._scheduler = ArenaScheduler(
            agents=self.agents,
            api_keys=self.api_keys,
            ai_takeover=self.ai_takeover
        )
        
        interval_sec = timeframe_to_seconds(self.timeframe)
        tf_display = ', '.join(self.timeframes)
        logger.info(f"[Arena] 启动 | {self.symbols} | AI: {self.agents} | 周期: [{tf_display}]")
        
        # 首次启动立即执行一次
        first_run = True
        
        while not self._stop_event.is_set():
            try:
                if first_run:
                    # 首次启动立即执行，不等待
                    first_run = False
                    logger.debug("[Arena] 首次启动，立即执行")
                else:
                    # 等待到下一根 K 线收盘（可中断）
                    wait_sec = wait_until_next_candle(self.timeframe, self._stop_event)
                    if wait_sec < 0:
                        # 被中断，退出循环
                        logger.info("[Arena] 等待被中断，准备停止")
                        break
                    logger.debug(f"[Arena] 等待 {wait_sec:.0f}s")
                
                # 🔥 每次操作前都检查停止信号
                if self._stop_event.is_set():
                    logger.info("[Arena] 检测到停止信号，退出循环")
                    break
                
                # 防止重复触发（同一个 K 线周期内只触发一次）
                current_ts = int(datetime.now().timestamp())
                interval_ts = current_ts // interval_sec * interval_sec
                if interval_ts == self._last_trigger_ts:
                    time.sleep(1)
                    continue
                self._last_trigger_ts = interval_ts
                
                trigger_time = datetime.now().strftime("%H:%M:%S")
                logger.info(f"[Arena] 触发 @ {trigger_time}")
                
                # 🔥 再次检查停止信号
                if self._stop_event.is_set():
                    logger.info("[Arena] 触发前检测到停止信号")
                    break
                
                # 🔥 使用带超时的批量分析
                try:
                    results = self._loop.run_until_complete(
                        asyncio.wait_for(
                            self._scheduler.run_batch_battle_cycle(
                                symbols=self.symbols,
                                timeframe=self.timeframe,
                                timeframes=self.timeframes,
                                user_prompt=self.user_prompt,
                                kline_count=100
                            ),
                            timeout=120  # 2 分钟超时
                        )
                    )
                except asyncio.TimeoutError:
                    logger.warning("[Arena] 批量分析超时（120秒），跳过本轮")
                    continue
                
                # 🔥 执行完成后再次检查停止信号
                if self._stop_event.is_set():
                    logger.info("[Arena] 批量分析完成后检测到停止信号")
                    break
                
                # 存储结果
                global _latest_result
                for result in results:
                    # 🔥 每个结果处理前检查停止信号
                    if self._stop_event.is_set():
                        break
                    
                    with _result_lock:
                        _latest_result = result
                    
                    try:
                        _result_queue.put_nowait(result)
                    except queue.Full:
                        try:
                            _result_queue.get_nowait()
                            _result_queue.put_nowait(result)
                        except queue.Empty:
                            pass
                    
                    if self.on_result:
                        try:
                            self.on_result(result)
                        except Exception as e:
                            logger.error(f"[PrecisionScheduler] 回调失败: {e}")
                
            except Exception as e:
                logger.error(f"[PrecisionScheduler] 循环异常: {e}")
                time.sleep(5)
        
        if self._loop:
            self._loop.close()
        logger.info("[Arena] 已停止")
    
    def start(self):
        """启动调度器"""
        if self._thread and self._thread.is_alive():
            logger.debug("[Arena] 已在运行")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="PrecisionScheduler"
        )
        self._thread.start()
        
        next_trigger = get_next_trigger_time()
        logger.debug(f"[Arena] 下次触发: {next_trigger.strftime('%H:%M:%S')}")
    
    def stop(self):
        """停止调度器"""
        logger.info("[Arena] 正在停止...")
        self._stop_event.set()
        
        if self._thread and self._thread.is_alive():
            # 🔥 先等待 5 秒让线程自然退出
            self._thread.join(timeout=5)
            
            if self._thread.is_alive():
                logger.warning("[Arena] 线程未能在 5 秒内停止，继续等待...")
                # 再等待 5 秒
                self._thread.join(timeout=5)
                
                if self._thread.is_alive():
                    logger.warning("[Arena] 线程未能在 10 秒内停止，强制标记为已停止")
        
        self._thread = None
        logger.info("[Arena] 已停止")
    
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()
    
    def update_config(
        self,
        symbols: List[str] = None,
        timeframe: str = None,
        timeframes: List[str] = None,
        agents: List[str] = None,
        user_prompt: str = None,
        ai_takeover: bool = None
    ):
        """动态更新配置"""
        if symbols is not None:
            self.symbols = symbols
        if timeframes is not None:
            self.timeframes = timeframes
            self.timeframe = self._get_shortest_timeframe(timeframes)
        elif timeframe is not None:
            self.timeframe = timeframe
            self.timeframes = [timeframe]
        if agents is not None:
            self.agents = agents
            if self._scheduler:
                self._scheduler = ArenaScheduler(
                    agents=self.agents, 
                    api_keys=self.api_keys,
                    ai_takeover=self.ai_takeover
                )
        if user_prompt is not None:
            self.user_prompt = user_prompt
        if ai_takeover is not None:
            self.ai_takeover = ai_takeover
            if self._scheduler:
                self._scheduler.ai_takeover_enabled = ai_takeover
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        P1: 获取调度器健康状态
        
        返回调度器和内部 ArenaScheduler 的健康信息
        """
        base_status = {
            'scheduler_running': self.is_running(),
            'symbols': self.symbols,
            'timeframes': self.timeframes,
            'agents': self.agents,
            'ai_takeover': self.ai_takeover
        }
        
        if self._scheduler:
            arena_health = self._scheduler.get_health_status()
            base_status.update(arena_health)
        else:
            base_status['is_healthy'] = False
            base_status['alerts'] = ['ArenaScheduler 未初始化']
        
        return base_status


# 全局调度器
_precision_scheduler: Optional[PrecisionScheduler] = None


def start_scheduler(
    symbols: List[str] = None,
    timeframe: str = "1m",
    timeframes: List[str] = None,
    agents: List[str] = None,
    api_keys: Dict[str, str] = None,
    user_prompt: str = "",
    ai_takeover: bool = False
) -> PrecisionScheduler:
    """启动精准调度器（单例）"""
    global _precision_scheduler
    
    if _precision_scheduler and _precision_scheduler.is_running():
        _precision_scheduler.stop()
    
    # 如果没有指定 timeframes，使用单个 timeframe
    if timeframes is None:
        timeframes = [timeframe]
    
    _precision_scheduler = PrecisionScheduler(
        symbols=symbols or ["BTC/USDT:USDT"],
        timeframe=timeframe,
        timeframes=timeframes,
        agents=agents or ["deepseek", "qwen", "perplexity"],
        api_keys=api_keys or {},
        user_prompt=user_prompt,
        ai_takeover=ai_takeover
    )
    
    _precision_scheduler.start()
    return _precision_scheduler


def stop_scheduler():
    """停止调度器"""
    global _precision_scheduler
    if _precision_scheduler:
        _precision_scheduler.stop()
        _precision_scheduler = None


def is_scheduler_running() -> bool:
    """检查调度器状态"""
    return _precision_scheduler is not None and _precision_scheduler.is_running()


def get_latest_battle_result() -> Optional[BattleResult]:
    """获取最新对战结果"""
    with _result_lock:
        return _latest_result


def get_scheduler() -> Optional[PrecisionScheduler]:
    """获取调度器实例"""
    return _precision_scheduler


# ============================================================================
# 同步包装器
# ============================================================================

def run_battle_sync(
    symbol: str,
    timeframe: str = "1m",
    user_prompt: str = "",
    agents: List[str] = None,
    api_keys: Dict[str, str] = None
) -> BattleResult:
    """同步运行一轮对战"""
    scheduler = ArenaScheduler(agents=agents, api_keys=api_keys)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            scheduler.run_battle_cycle(symbol, timeframe, user_prompt)
        )
    finally:
        loop.close()


def get_leaderboard() -> List[Dict]:
    """获取 AI 排行榜"""
    from ai_db_manager import get_ai_db_manager
    db = get_ai_db_manager()
    stats = db.get_all_stats()
    
    return [
        {
            'rank': i + 1,
            'agent_name': s.agent_name,
            'win_rate': s.win_rate,
            'total_pnl': s.total_pnl,
            'total_trades': s.total_trades,
            'current_streak': s.current_streak,
            'last_signal': s.last_signal
        }
        for i, s in enumerate(stats)
        if s.total_trades > 0
    ]


def get_recent_decisions(limit: int = 20, since_timestamp: int = None) -> List[Dict]:
    """获取最近决策"""
    from ai_db_manager import get_ai_db_manager
    db = get_ai_db_manager()
    decisions = db.get_latest_decisions(limit=limit, since_timestamp=since_timestamp)
    return [d.to_dict() for d in decisions]


# ============================================================================
# 兼容性别名（供 ui_arena.py 调用）
# ============================================================================

def start_background_scheduler(
    interval_sec: int = 60,
    symbols: List[str] = None,
    timeframe: str = "1m",
    timeframes: List[str] = None,
    agents: List[str] = None,
    api_keys: Dict[str, str] = None,
    user_prompt: str = "",
    ai_takeover: bool = False
) -> PrecisionScheduler:
    """
    启动后台调度器（兼容性别名）
    
    参数:
        interval_sec: 对战间隔（秒），当前版本固定为 00 秒触发
        symbols: 交易对列表
        timeframe: 主时间周期（触发周期）
        timeframes: 所有要分析的周期列表（方案 B 多周期分析）
        agents: AI 列表
        api_keys: API Key 字典
        user_prompt: 用户提示词
        ai_takeover: AI 托管开关（需主界面为实盘模式才生效）
    """
    return start_scheduler(
        symbols=symbols,
        timeframe=timeframe,
        timeframes=timeframes,
        agents=agents,
        api_keys=api_keys,
        user_prompt=user_prompt,
        ai_takeover=ai_takeover
    )


def stop_background_scheduler():
    """停止后台调度器（兼容性别名）"""
    stop_scheduler()


def get_background_scheduler() -> Optional[PrecisionScheduler]:
    """获取后台调度器实例（兼容性别名）"""
    return get_scheduler()


def get_scheduler_health() -> Dict[str, Any]:
    """
    P1: 获取调度器健康状态
    
    返回:
        健康状态字典，包含心跳、成功率、告警等信息
    """
    scheduler = get_scheduler()
    if scheduler:
        return scheduler.get_health_status()
    return {
        'is_healthy': False,
        'scheduler_running': False,
        'alerts': ['调度器未启动']
    }
