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
NOFX Arena UI - AI 竞技场界面模块

驾驶舱双栏布局 + Battle Royale 风格 AI 对抗展示
"""

import streamlit as st
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable


# ============================================================================
# 数据接口层 - 预留给后端/数据库对接
# ============================================================================

# AI 模型定义（支持的 AI 交易员列表）
# 从 ai_providers.py 统一获取，保持一致性
def _get_ai_models_from_providers() -> Dict[str, Dict[str, Any]]:
    """从 ai_providers.py 获取 AI 模型定义"""
    try:
        from ai.ai_providers import AI_PROVIDERS, PROVIDER_ALIASES
        models = {}
        for provider_id, provider in AI_PROVIDERS.items():
            models[provider_id] = {
                "id": provider_id,
                "name": provider.name,
                "icon": "",
                "description": provider.description,
                "api_base_url": provider.api_base,
                "requires_api_key": True,
            }
        # 添加别名映射
        for alias, real_id in PROVIDER_ALIASES.items():
            if real_id in models and alias not in models:
                models[alias] = models[real_id].copy()
                models[alias]["id"] = alias  # 保持原始 ID
        return models
    except ImportError as e:
        # 回退到最小硬编码列表
        import logging
        logging.getLogger(__name__).warning(f"[Arena] ai_providers.py 导入失败: {e}，使用最小回退列表")
        return _AI_MODELS_MINIMAL_FALLBACK

# 最小回退列表（仅在 ai_providers.py 不可用时使用）
# 注意：新增 AI 服务商应在 ai_providers.py 中添加，此处仅作为紧急回退
_AI_MODELS_MINIMAL_FALLBACK = {
    "deepseek": {
        "id": "deepseek",
        "name": "DeepSeek",
        "icon": "",
        "description": "深度推理，擅长技术分析",
        "api_base_url": "https://api.deepseek.com/v1",
        "requires_api_key": True,
    },
    "qwen": {
        "id": "qwen",
        "name": "通义千问",
        "icon": "",
        "description": "阿里云通义千问系列",
        "api_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "requires_api_key": True,
    },
    "openai": {
        "id": "openai",
        "name": "OpenAI",
        "icon": "",
        "description": "OpenAI GPT系列",
        "api_base_url": "https://api.openai.com/v1",
        "requires_api_key": True,
    },
}

# 动态获取 AI 模型列表
AI_MODELS = _get_ai_models_from_providers()


class ArenaDataInterface:
    """
    Arena 数据接口类
    
    所有数据操作通过此接口进行，使用 AIConfigManager 进行数据库持久化
    """
    
    # ========== AI API 配置 ==========
    
    @staticmethod
    def _get_config_manager():
        """获取配置管理器"""
        try:
            from ai.ai_config_manager import get_ai_config_manager
            return get_ai_config_manager()
        except ImportError:
            return None
    
    @staticmethod
    def get_ai_api_configs() -> Dict[str, Dict[str, Any]]:
        """
        获取所有 AI 的 API 配置（从数据库读取）
        
        返回格式:
        {
            "deepseek": {"api_key": "sk-xxx", "enabled": True, "verified": True},
            "qwen": {"api_key": "", "enabled": False, "verified": False},
            ...
        }
        """
        config_mgr = ArenaDataInterface._get_config_manager()
        if config_mgr:
            db_configs = config_mgr.get_all_ai_api_configs()
            # 同步到 session_state
            st.session_state.ai_api_configs = db_configs
            return db_configs
        
        # 回退到 session_state
        if 'ai_api_configs' not in st.session_state:
            st.session_state.ai_api_configs = {}
        return st.session_state.ai_api_configs
    
    @staticmethod
    def save_ai_api_config(ai_id: str, api_key: str, enabled: bool = True, model: str = "") -> Dict[str, Any]:
        """
        保存单个 AI 的 API 配置（持久化到数据库）
        
        参数:
            ai_id: AI 标识符 (deepseek, qwen, openai, claude, perplexity)
            api_key: API Key
            enabled: 是否启用
            model: 选择的模型 ID
        
        返回:
            {"ok": True/False, "message": "...", "verified": True/False}
        """
        # 真实 API Key 验证
        try:
            from ai.ai_api_validator import quick_validate_key_format, verify_api_key_sync
            
            # 1. 快速格式检查
            format_ok, format_msg = quick_validate_key_format(ai_id, api_key)
            if not format_ok:
                return {"ok": False, "message": format_msg, "verified": False}
            
            # 2. 真实 API 调用验证
            verified, verify_msg = verify_api_key_sync(ai_id, api_key)
            
        except ImportError:
            # 回退到简单验证
            verified = api_key and len(api_key) > 10
            verify_msg = "配置已保存（未验证）" if verified else "API Key 格式无效"
        except Exception as e:
            return {"ok": False, "message": f"验证异常: {str(e)[:50]}", "verified": False}
        
        # 保存到数据库
        config_mgr = ArenaDataInterface._get_config_manager()
        if config_mgr:
            success = config_mgr.save_ai_api_config(
                ai_id, api_key, 
                enabled=enabled and verified, 
                verified=verified,
                model=model
            )
            if success:
                # 同步到 session_state
                if 'ai_api_configs' not in st.session_state:
                    st.session_state.ai_api_configs = {}
                st.session_state.ai_api_configs[ai_id] = {
                    "api_key": api_key,
                    "enabled": enabled and verified,
                    "verified": verified,
                    "model": model
                }
                return {
                    "ok": True,
                    "message": verify_msg,
                    "verified": verified
                }
            return {"ok": False, "message": "保存失败", "verified": False}
        
        # 回退到 session_state
        if 'ai_api_configs' not in st.session_state:
            st.session_state.ai_api_configs = {}
        
        st.session_state.ai_api_configs[ai_id] = {
            "api_key": api_key,
            "enabled": enabled and verified,
            "verified": verified,
            "model": model,
            "updated_at": datetime.now().isoformat()
        }
        
        return {
            "ok": True,
            "message": "配置已保存" if verified else "API Key 格式无效",
            "verified": verified
        }
    
    @staticmethod
    def delete_ai_api_config(ai_id: str) -> Dict[str, Any]:
        """删除 AI 的 API 配置（从数据库删除）"""
        config_mgr = ArenaDataInterface._get_config_manager()
        if config_mgr:
            success = config_mgr.delete_ai_api_config(ai_id)
            if success:
                # 同步到 session_state
                if 'ai_api_configs' in st.session_state and ai_id in st.session_state.ai_api_configs:
                    del st.session_state.ai_api_configs[ai_id]
                return {"ok": True, "message": "配置已删除"}
            return {"ok": False, "message": "删除失败"}
        
        # 回退到 session_state
        if 'ai_api_configs' in st.session_state:
            if ai_id in st.session_state.ai_api_configs:
                del st.session_state.ai_api_configs[ai_id]
                return {"ok": True, "message": "配置已删除"}
        return {"ok": False, "message": "配置不存在"}
    
    # 调试模式开关 - 设为 False 使用真实配置
    DEBUG_MODE = False
    
    @staticmethod
    def get_enabled_ai_list() -> List[str]:
        """
        获取已启用的 AI 列表（已配置且验证通过的）
        
        返回: ["deepseek", "qwen", ...]
        """
        # 调试模式：返回所有 AI 用于展示
        if ArenaDataInterface.DEBUG_MODE:
            return ["deepseek", "qwen", "perplexity"]
        
        configs = ArenaDataInterface.get_ai_api_configs()
        return [
            ai_id for ai_id, config in configs.items()
            if config.get('enabled') and config.get('verified')
        ]
    
    # ========== AI 接管交易状态 ==========
    
    @staticmethod
    def get_takeover_status() -> Dict[str, Any]:
        """
        获取 AI 接管交易状态
        
        返回:
        {
            "enabled": True/False,      # 是否启用接管
            "active_ai": "deepseek",    # 当前接管的 AI
            "started_at": "...",        # 接管开始时间
            "trades_count": 5,          # 接管期间交易次数
        }
        
         后续对接: 从数据库 ai_takeover_status 表读取
        """
        return {
            "enabled": st.session_state.get('ai_takeover', False),
            "active_ai": st.session_state.get('ai_takeover_model', None),
            "started_at": st.session_state.get('ai_takeover_started_at', None),
            "trades_count": st.session_state.get('ai_takeover_trades', 0),
        }
    
    @staticmethod
    def start_takeover(ai_id: str) -> Dict[str, Any]:
        """
        启动 AI 接管交易
        
        参数:
            ai_id: 要接管的 AI 标识符
        
        返回:
            {"ok": True/False, "message": "..."}
        
         后续对接: 
            1. 写入数据库 ai_takeover_status 表
            2. 通知后端 trade_engine 切换到 AI 模式
        """
        # 检查 AI 是否已配置
        configs = ArenaDataInterface.get_ai_api_configs()
        if ai_id not in configs or not configs[ai_id].get('verified'):
            return {"ok": False, "message": f"{ai_id} 未配置或 API Key 无效"}
        
        st.session_state.ai_takeover = True
        st.session_state.ai_takeover_model = ai_id
        st.session_state.ai_takeover_started_at = datetime.now().isoformat()
        st.session_state.ai_takeover_trades = 0
        
        return {"ok": True, "message": f"已启动 {AI_MODELS.get(ai_id, {}).get('name', ai_id)} 接管交易"}
    
    @staticmethod
    def stop_takeover() -> Dict[str, Any]:
        """
        停止 AI 接管交易
        
         后续对接:
            1. 更新数据库 ai_takeover_status 表
            2. 通知后端 trade_engine 切换回手动模式
        """
        st.session_state.ai_takeover = False
        st.session_state.ai_takeover_model = None
        st.session_state.ai_takeover_started_at = None
        
        return {"ok": True, "message": "已停止 AI 接管"}
    
    # ========== AI 交易员状态 ==========
    
    @staticmethod
    def get_ai_trader_stats(ai_id: str) -> Dict[str, Any]:
        """
        获取单个 AI 交易员的统计数据
        
        返回:
        {
            "rank": 1,
            "roi": 14.2,
            "win_rate": 65,
            "signal": "BUY",
            "confidence": 85,
            "streak": 3,
            "last_trade": "BTC/USDT LONG @ $98,200",
            "reason": "...",
        }
        
         后续对接: 从数据库 ai_trader_stats 表读取
        """
        # 当前返回模拟数据
        mock_data = get_arena_mock_data()
        return mock_data.get(ai_id, {})
    
    @staticmethod
    def get_all_ai_trader_stats() -> Dict[str, Dict[str, Any]]:
        """
        获取所有已启用 AI 的统计数据
        
         后续对接: 从数据库批量查询
        """
        enabled_ais = ArenaDataInterface.get_enabled_ai_list()
        if not enabled_ais:
            # 没有启用的 AI，返回空
            return {}
        
        # 当前返回模拟数据（只返回已启用的）
        mock_data = get_arena_mock_data()
        return {ai_id: mock_data.get(ai_id, {}) for ai_id in enabled_ais if ai_id in mock_data}
    
    # ========== AI 提示词配置 ==========
    
    @staticmethod
    def get_ai_prompt() -> str:
        """获取 AI 自定义提示词（从数据库读取）"""
        config_mgr = ArenaDataInterface._get_config_manager()
        if config_mgr:
            prompt = config_mgr.get_custom_prompt()
            st.session_state.ai_custom_prompt = prompt
            return prompt
        return st.session_state.get('ai_custom_prompt', '')
    
    @staticmethod
    def save_ai_prompt(prompt: str) -> Dict[str, Any]:
        """保存 AI 自定义提示词（持久化到数据库）"""
        config_mgr = ArenaDataInterface._get_config_manager()
        if config_mgr:
            success = config_mgr.set_custom_prompt(prompt)
            if success:
                st.session_state.ai_custom_prompt = prompt
                return {"ok": True, "message": "提示词已保存"}
            return {"ok": False, "message": "保存失败"}
        
        st.session_state.ai_custom_prompt = prompt
        return {"ok": True, "message": "提示词已保存"}


# ============ 真实数据获取 ============

@st.cache_data(ttl=5, show_spinner=False)
def get_arena_real_data() -> Dict[str, Dict[str, Any]]:
    """
    获取 AI 竞技场真实数据（从数据库读取）
    
    只返回已配置 API 的 AI 数据
    """
    # 获取已配置的 AI 列表
    enabled_ais = ArenaDataInterface.get_enabled_ai_list()
    if not enabled_ais:
        return {}
    
    # 尝试从数据库获取统计数据
    try:
        from ai.ai_db_manager import get_ai_db_manager
        from ai.ai_indicators import get_data_source
        
        db = get_ai_db_manager()
        all_stats = db.get_all_stats()
        
        # 获取当前价格用于计算未实现盈亏
        data_source = None
        price_cache = {}
        try:
            data_source = get_data_source()
        except:
            pass
        
        # 转换为字典格式
        # 初始资金 10000 USD，用于计算 ROI 百分比
        INITIAL_BALANCE = 10000.0
        
        stats_dict = {}
        for stat in all_stats:
            # total_pnl 是绝对盈亏金额（USD），需要转换为百分比
            total_pnl_usd = stat.total_pnl or 0
            
            stats_dict[stat.agent_name] = {
                "rank": 0,  # 稍后计算
                "roi": total_pnl_usd,  # 先存储绝对盈亏，后面会转换为百分比
                "total_pnl_usd": total_pnl_usd,  # 保留绝对盈亏金额
                "unrealized_pnl": 0,  # 未实现盈亏（稍后计算）
                "win_rate": int(stat.win_rate * 100) if stat.win_rate else 0,
                "total_trades": stat.total_trades or 0,  # 添加交易次数
                "signal": stat.last_signal or "WAIT",
                "confidence": 0,  # 从最新决策获取
                "reason": "",
                "is_active": False,
                "last_trade": "",
                "streak": stat.current_streak or 0
            }
        
        # 计算每个 AI 的未实现盈亏
        for ai_id in enabled_ais:
            positions = db.get_open_positions(ai_id)
            unrealized_pnl = 0
            
            for pos in positions:
                symbol = pos.get('symbol', '')
                entry_price = pos.get('entry_price', 0)
                qty = pos.get('qty', 0)  # qty 是 USD 仓位金额
                side = pos.get('side', 'long')
                leverage = pos.get('leverage', 1)
                
                # 获取当前价格
                if symbol not in price_cache and data_source:
                    try:
                        ohlcv = data_source.fetch_ohlcv(symbol, '1m', 1)
                        price_cache[symbol] = ohlcv[-1][4] if ohlcv else entry_price
                    except:
                        price_cache[symbol] = entry_price
                
                current_price = price_cache.get(symbol, entry_price)
                
                # 修复盈亏计算公式
                # qty 是 USD 仓位金额，盈亏 = 价格变化百分比 * 仓位 * 杠杆
                if entry_price > 0:
                    price_change_pct = (current_price - entry_price) / entry_price
                    if side == 'long':
                        pnl = price_change_pct * qty * leverage
                    else:  # short
                        pnl = -price_change_pct * qty * leverage
                else:
                    pnl = 0
                
                unrealized_pnl += pnl
            
            if ai_id in stats_dict:
                stats_dict[ai_id]["unrealized_pnl"] = unrealized_pnl
                # 总盈亏 = 已实现 + 未实现（USD）
                total_pnl = stats_dict[ai_id]["total_pnl_usd"] + unrealized_pnl
                # ROI 百分比 = 总盈亏 / 初始资金 * 100
                stats_dict[ai_id]["roi"] = (total_pnl / INITIAL_BALANCE) * 100
            else:
                # 新 AI 没有统计记录，但有持仓，需要创建条目
                if unrealized_pnl != 0:
                    stats_dict[ai_id] = {
                        "rank": 0,
                        "roi": (unrealized_pnl / INITIAL_BALANCE) * 100,
                        "total_pnl_usd": 0,
                        "unrealized_pnl": unrealized_pnl,
                        "win_rate": 0,
                        "total_trades": 0,
                        "signal": "WAIT",
                        "confidence": 0,
                        "reason": "",
                        "is_active": False,
                        "last_trade": "",
                        "streak": 0
                    }
        
        # 获取最新决策（每个 AI 获取多条，用于显示多币种分析）
        latest_decisions = db.get_latest_decisions(limit=len(enabled_ais) * 10)
        
        # 按 AI 分组收集决策
        ai_decisions_map = {}
        for decision in latest_decisions:
            if decision.agent_name not in ai_decisions_map:
                ai_decisions_map[decision.agent_name] = []
            ai_decisions_map[decision.agent_name].append(decision)
        
        for ai_name, decisions in ai_decisions_map.items():
            if ai_name in stats_dict:
                # 取最新一条的置信度和信号
                latest = decisions[0]
                stats_dict[ai_name]["confidence"] = int(latest.confidence) if latest.confidence else 0
                stats_dict[ai_name]["signal"] = latest.signal or "WAIT"
                
                # 构建包含币种的推理内容（显示最近分析的所有币种）
                reason_parts = []
                seen_symbols = set()
                for d in decisions[:5]:  # 最多显示 5 个币种
                    symbol_short = d.symbol.replace('/USDT:USDT', '').replace('/USDT', '') if d.symbol else '未知'
                    if symbol_short in seen_symbols:
                        continue
                    seen_symbols.add(symbol_short)
                    
                    signal_emoji = "(↑)" if d.signal in ['open_long', 'BUY'] else "(↓)" if d.signal in ['open_short', 'SELL'] else "(-)"
                    reason_text = d.reasoning[:80] + "..." if d.reasoning and len(d.reasoning) > 80 else (d.reasoning or "无")
                    reason_parts.append(f"**{symbol_short}** {signal_emoji}: {reason_text}")
                
                stats_dict[ai_name]["reason"] = "\n\n".join(reason_parts) if reason_parts else "等待分析..."
            else:
                # 新 AI 有决策但没有统计数据，创建条目
                latest = decisions[0]
                reason_parts = []
                seen_symbols = set()
                for d in decisions[:5]:
                    symbol_short = d.symbol.replace('/USDT:USDT', '').replace('/USDT', '') if d.symbol else '未知'
                    if symbol_short in seen_symbols:
                        continue
                    seen_symbols.add(symbol_short)
                    signal_emoji = "(↑)" if d.signal in ['open_long', 'BUY'] else "(↓)" if d.signal in ['open_short', 'SELL'] else "(-)"
                    reason_text = d.reasoning[:80] + "..." if d.reasoning and len(d.reasoning) > 80 else (d.reasoning or "无")
                    reason_parts.append(f"**{symbol_short}** {signal_emoji}: {reason_text}")
                
                stats_dict[ai_name] = {
                    "rank": 0,
                    "roi": 0,
                    "unrealized_pnl": 0,
                    "win_rate": 0,
                    "signal": latest.signal or "WAIT",
                    "confidence": int(latest.confidence) if latest.confidence else 0,
                    "reason": "\n\n".join(reason_parts) if reason_parts else "等待分析...",
                    "is_active": False,
                    "last_trade": "",
                    "streak": 0
                }
        
        # 只返回已配置的 AI，然后再计算排名
        result = {}
        for ai_id in enabled_ais:
            if ai_id in stats_dict:
                result[ai_id] = stats_dict[ai_id]
            else:
                # 新配置的 AI，使用默认数据
                result[ai_id] = {
                    "rank": 0,  # 稍后计算
                    "roi": 0,
                    "total_pnl_usd": 0,  # 添加绝对盈亏
                    "unrealized_pnl": 0,
                    "win_rate": 0,
                    "total_trades": 0,  # 添加交易次数
                    "signal": "WAIT",
                    "confidence": 0,
                    "reason": "等待首次分析...",
                    "is_active": False,
                    "last_trade": "",
                    "streak": 0
                }
        
        # 只在已启用的 AI 中计算排名（按 ROI 排序）
        sorted_ais = sorted(result.items(), key=lambda x: x[1].get('roi', 0), reverse=True)
        for i, (ai_id, data) in enumerate(sorted_ais):
            result[ai_id]["rank"] = i + 1
        
        return result
        
    except Exception as e:
        # 数据库不可用，返回已配置 AI 的默认数据
        result = {}
        for i, ai_id in enumerate(enabled_ais):
            result[ai_id] = {
                "rank": i + 1,
                "roi": 0,
                "total_pnl_usd": 0,  # 添加绝对盈亏
                "win_rate": 0,
                "total_trades": 0,  # 添加交易次数
                "signal": "WAIT",
                "confidence": 0,
                "reason": "等待首次分析...",
                "is_active": False,
                "last_trade": "",
                "streak": 0
            }
        return result


# 兼容旧代码的别名
def get_arena_mock_data() -> Dict[str, Dict[str, Any]]:
    """兼容旧代码，实际调用真实数据获取"""
    return get_arena_real_data()


# ============ 样式定义 ============

ARENA_STYLES = """
<style>
/* ========== Arena 界面使用 Streamlit 默认深色主题 ========== */
/* 不覆盖全局背景，保持默认深色风格 */

/* ========== 简洁入场过渡动画 ========== */
/* 页面内容淡入效果 */
.arena-fade-in {
    animation: arenaFadeIn 0.6s ease-out;
}

@keyframes arenaFadeIn {
    0% { 
        opacity: 0; 
        transform: translateY(10px);
    }
    100% { 
        opacity: 1; 
        transform: translateY(0);
    }
}

/* 卡片依次入场动画 */
.arena-card-enter {
    animation: cardSlideIn 0.5s ease-out backwards;
}

.arena-card-enter:nth-child(1) { animation-delay: 0.1s; }
.arena-card-enter:nth-child(2) { animation-delay: 0.2s; }
.arena-card-enter:nth-child(3) { animation-delay: 0.3s; }

@keyframes cardSlideIn {
    0% { 
        opacity: 0; 
        transform: translateY(20px) scale(0.95);
    }
    100% { 
        opacity: 1; 
        transform: translateY(0) scale(1);
    }
}

/* 侧边栏滑入效果 */
section[data-testid="stSidebar"] {
    animation: sidebarSlideIn 0.4s ease-out;
}

@keyframes sidebarSlideIn {
    0% { 
        opacity: 0;
        transform: translateX(-20px);
    }
    100% { 
        opacity: 1;
        transform: translateX(0);
    }
}

/* ========== AI 竞技场卡片 ========== */
.arena-card {
    background: linear-gradient(145deg, rgba(26, 26, 46, 0.9), rgba(15, 15, 26, 0.95));
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 20px;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease;
}

.arena-card:hover {
    border-color: rgba(255, 255, 255, 0.2);
    transform: translateY(-2px);
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

/* 冠军卡片特殊样式 */
.arena-card.champion {
    border: 2px solid #ffd700;
    box-shadow: 0 0 30px rgba(255, 215, 0, 0.2);
}

.arena-card.champion::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, #ffd700, #ffed4a, #ffd700);
}

/* ========== 排名徽章 ========== */
.rank-badge {
    display: inline-flex;
    align-items: center;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 14px;
    font-weight: 600;
}

.rank-badge.gold {
    background: linear-gradient(135deg, #ffd700, #ffed4a);
    color: #1a1a2e;
}

.rank-badge.silver {
    background: linear-gradient(135deg, #c0c0c0, #e8e8e8);
    color: #1a1a2e;
}

.rank-badge.bronze {
    background: linear-gradient(135deg, #cd7f32, #daa06d);
    color: #1a1a2e;
}

/* ========== 信号标签 + 呼吸灯动画 ========== */
.signal-tag {
    display: inline-block;
    padding: 8px 24px;
    border-radius: 8px;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* BUY 信号 - 绿色呼吸灯 */
.signal-tag.buy {
    background: linear-gradient(135deg, #00d4aa, #00f5c4);
    color: #0a0a0f;
    animation: pulse-buy 2s ease-in-out infinite;
}

@keyframes pulse-buy {
    0% {
        box-shadow: 0 0 0 0 rgba(0, 212, 170, 0.7);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 20px 10px rgba(0, 212, 170, 0.3);
        transform: scale(1.02);
    }
    100% {
        box-shadow: 0 0 0 0 rgba(0, 212, 170, 0);
        transform: scale(1);
    }
}

/* SELL 信号 - 红色呼吸灯 */
.signal-tag.sell {
    background: linear-gradient(135deg, #ff6b6b, #ff8e8e);
    color: #0a0a0f;
    animation: pulse-sell 2s ease-in-out infinite;
}

@keyframes pulse-sell {
    0% {
        box-shadow: 0 0 0 0 rgba(255, 107, 107, 0.7);
        transform: scale(1);
    }
    50% {
        box-shadow: 0 0 20px 10px rgba(255, 107, 107, 0.3);
        transform: scale(1.02);
    }
    100% {
        box-shadow: 0 0 0 0 rgba(255, 107, 107, 0);
        transform: scale(1);
    }
}

/* WAIT 信号 - 黄色柔和闪烁 */
.signal-tag.wait {
    background: linear-gradient(135deg, #feca57, #ffed4a);
    color: #0a0a0f;
    animation: pulse-wait 3s ease-in-out infinite;
}

@keyframes pulse-wait {
    0%, 100% {
        box-shadow: 0 4px 20px rgba(254, 202, 87, 0.4);
        opacity: 1;
    }
    50% {
        box-shadow: 0 4px 30px rgba(254, 202, 87, 0.6);
        opacity: 0.9;
    }
}

/* ========== 指标数值 ========== */
.metric-value {
    font-size: 24px;
    font-weight: 700;
}

.metric-value.positive {
    color: #00d4aa;
}

.metric-value.negative {
    color: #ff6b6b;
}

.metric-value.neutral {
    color: #feca57;
}

.metric-label {
    font-size: 12px;
    color: #718096;
    text-transform: uppercase;
    letter-spacing: 1px;
}

/* ========== 状态指示器 ========== */
.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 12px;
}

.status-indicator.active {
    background: rgba(0, 212, 170, 0.15);
    color: #00d4aa;
    border: 1px solid rgba(0, 212, 170, 0.3);
}

.status-indicator.inactive {
    background: rgba(255, 255, 255, 0.05);
    color: #718096;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

/* ========== "还活着"闪烁动画 ========== */
.alive-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #00d4aa;
    animation: alive-pulse 1.5s ease-in-out infinite;
    margin-right: 4px;
}

@keyframes alive-pulse {
    0%, 100% { 
        opacity: 1; 
        transform: scale(1);
        box-shadow: 0 0 0 0 rgba(0, 212, 170, 0.7);
    }
    50% { 
        opacity: 0.6; 
        transform: scale(0.8);
        box-shadow: 0 0 8px 4px rgba(0, 212, 170, 0.3);
    }
}

/* "还活着"文字闪烁 - 二次元风格 */
.alive-text {
    display: inline-block;
    font-size: 10px;
    color: #00d4aa;
    margin-left: 6px;
    padding: 2px 6px;
    background: rgba(0, 212, 170, 0.15);
    border-radius: 8px;
    animation: alive-text-blink 2s ease-in-out infinite;
    font-weight: 500;
}

@keyframes alive-text-blink {
    0%, 100% { 
        opacity: 1;
        color: #00d4aa;
        text-shadow: 0 0 8px rgba(0, 212, 170, 0.6);
    }
    50% { 
        opacity: 0.5;
        color: #00b894;
        text-shadow: 0 0 4px rgba(0, 212, 170, 0.3);
    }
}

/* AI 发言卡片 - 交易账本风格 */
.ai-speech-card {
    background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.08));
    border-left: 3px solid #667eea;
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
    margin: 8px 0;
    position: relative;
}

.ai-speech-card.long {
    border-left-color: #00d4aa;
    background: linear-gradient(135deg, rgba(0, 212, 170, 0.1), rgba(0, 184, 148, 0.08));
}

.ai-speech-card.short {
    border-left-color: #ff6b6b;
    background: linear-gradient(135deg, rgba(255, 107, 107, 0.1), rgba(238, 82, 83, 0.08));
}

.ai-speech-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.ai-speech-name {
    font-weight: 600;
    font-size: 14px;
    color: #e2e8f0;
}

.ai-speech-tag {
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 10px;
    background: rgba(102, 126, 234, 0.3);
    color: #a0aec0;
}

.ai-speech-time {
    font-size: 11px;
    color: #718096;
}

.ai-speech-content {
    font-size: 13px;
    color: #cbd5e0;
    line-height: 1.6;
    margin-top: 4px;
}

.ai-speech-footer {
    display: flex;
    justify-content: flex-end;
    margin-top: 8px;
}

.ai-speech-expand {
    font-size: 11px;
    color: #667eea;
    cursor: pointer;
}

/* ========== 控制面板 ========== */
.control-panel {
    background: rgba(26, 26, 46, 0.6);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
}

.control-panel-title {
    font-size: 14px;
    font-weight: 600;
    color: #a0aec0;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ========== 命令中心 ========== */
.command-center {
    background: linear-gradient(145deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
    border: 1px solid rgba(102, 126, 234, 0.3);
    border-radius: 12px;
    padding: 16px;
}

/* ========== 冠军视野 Tab ========== */
.champion-view {
    background: linear-gradient(145deg, rgba(255, 215, 0, 0.05), rgba(255, 237, 74, 0.02));
    border: 1px solid rgba(255, 215, 0, 0.2);
    border-radius: 12px;
    padding: 20px;
}

/* ========== 动画效果 ========== */
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 20px rgba(0, 212, 170, 0.3); }
    50% { box-shadow: 0 0 40px rgba(0, 212, 170, 0.5); }
}

.arena-card.champion.active {
    animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes slide-in {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.arena-card {
    animation: slide-in 0.5s ease-out;
}

/* ========== 连胜/连败徽章 - 火焰/冰霜风格 ========== */
.streak-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* 连胜徽章 - 火焰风格 */
.streak-badge.winning {
    background: linear-gradient(135deg, rgba(255, 107, 0, 0.3), rgba(255, 193, 7, 0.2));
    color: #ff9500;
    border: 1px solid rgba(255, 152, 0, 0.5);
    text-shadow: 0 0 10px rgba(255, 152, 0, 0.5);
}

/* 大连胜 (>3) - 燃烧动画 */
.streak-badge.winning.hot {
    background: linear-gradient(135deg, rgba(255, 69, 0, 0.4), rgba(255, 140, 0, 0.3));
    color: #ff6b00;
    border: 1px solid rgba(255, 69, 0, 0.6);
    animation: flame-glow 1.5s ease-in-out infinite;
}

@keyframes flame-glow {
    0%, 100% {
        box-shadow: 0 0 5px rgba(255, 107, 0, 0.5), 0 0 10px rgba(255, 69, 0, 0.3);
    }
    50% {
        box-shadow: 0 0 15px rgba(255, 107, 0, 0.8), 0 0 25px rgba(255, 69, 0, 0.5);
    }
}

/* 连败徽章 - 冰霜风格 */
.streak-badge.losing {
    background: linear-gradient(135deg, rgba(100, 181, 246, 0.2), rgba(144, 202, 249, 0.15));
    color: #64b5f6;
    border: 1px solid rgba(100, 181, 246, 0.4);
}

/* 大连败 (>2) - 冰冻效果 */
.streak-badge.losing.frozen {
    background: linear-gradient(135deg, rgba(33, 150, 243, 0.3), rgba(100, 181, 246, 0.2));
    color: #42a5f5;
    border: 1px solid rgba(33, 150, 243, 0.5);
    animation: frost-shimmer 2s ease-in-out infinite;
}

@keyframes frost-shimmer {
    0%, 100% {
        box-shadow: 0 0 5px rgba(100, 181, 246, 0.4);
    }
    50% {
        box-shadow: 0 0 15px rgba(100, 181, 246, 0.6), 0 0 20px rgba(33, 150, 243, 0.3);
    }
}

/* 打字机光标动画 */
.typewriter-cursor {
    display: inline-block;
    width: 2px;
    height: 1em;
    background: #00d4aa;
    margin-left: 2px;
    animation: blink-cursor 0.8s step-end infinite;
}

@keyframes blink-cursor {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* ========== 粉色渐变按钮样式 ========== */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3) !important;
    transition: all 0.3s ease !important;
}

.stButton > button[kind="primary"]:hover {
    box-shadow: 0 6px 20px rgba(240, 147, 251, 0.5) !important;
    transform: translateY(-1px) !important;
}

/* 所有 primary 按钮统一粉色渐变 */
div[data-testid="stButton"] > button[kind="primary"],
div[data-testid="stButton"] > button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%) !important;
    border: none !important;
    color: white !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(240, 147, 251, 0.3) !important;
}
</style>
"""


# ============ UI 组件函数 ============

def render_arena_styles():
    """注入 Arena 样式"""
    st.markdown(ARENA_STYLES, unsafe_allow_html=True)


def render_intro_animation():
    """
    渲染简洁的入场过渡效果
    
    通过 CSS 动画实现无缝衔接，无需额外 HTML 元素
    动画已在 ARENA_STYLES 中定义，页面元素会自动应用
    """
    # 动画效果已通过 CSS 自动应用到页面元素
    # 侧边栏滑入 + 内容淡入 + 卡片依次入场
    pass


def render_rank_badge(rank: int) -> str:
    """渲染排名徽章 HTML"""
    badges = {
        1: ('🥇 1', 'gold'),
        2: ('🥈 2', 'silver'),
        3: ('🥉 3', 'bronze')
    }
    text, cls = badges.get(rank, (f'{rank}', 'bronze'))
    return f'<span class="rank-badge {cls}">{text}</span>'


def render_signal_tag(signal: str) -> str:
    """渲染信号标签 HTML"""
    signal_upper = signal.upper()
    cls = signal_upper.lower()
    if cls not in ['buy', 'sell', 'wait']:
        cls = 'wait'
    return f'<span class="signal-tag {cls}">{signal_upper}</span>'


def render_streak_badge(streak: int) -> str:
    """
    渲染连胜/连败徽章 - 火焰/冰霜风格
    
    - 连胜 > 3: 火焰徽章 + 燃烧动画
    - 连败 > 2: 冰霜徽章 + 冰冻效果
    """
    if streak > 0:
        # 连胜
        if streak > 3:
            # 大连胜 - 火焰燃烧效果
            fire_icons = "(*^▽^*)" 
            return f'<span class="streak-badge winning hot">{fire_icons} {streak}连胜</span>'
        else:
            return f'<span class="streak-badge winning">(≧∇≦)/ {streak}连胜</span>'
    elif streak < 0:
        # 连败
        abs_streak = abs(streak)
        if abs_streak > 2:
            # 大连败 - 冰冻效果
            ice_icons = "❄️" * min(abs_streak - 1, 3)  # 最多3个冰晶
            return f'<span class="streak-badge losing frozen">{ice_icons} {abs_streak}连败</span>'
        else:
            return f'<span class="streak-badge losing">❄️ {abs_streak}连败</span>'
    return ''


def stream_text(placeholder, full_text: str, delay: float = 0.02):
    """
    打字机效果 - 逐字输出文本
    
    Args:
        placeholder: st.empty() 占位符
        full_text: 完整文本
        delay: 每个字符的延迟（秒）
    """
    displayed_text = ""
    for char in full_text:
        displayed_text += char
        # 添加闪烁光标
        placeholder.markdown(
            displayed_text + '<span class="typewriter-cursor"></span>',
            unsafe_allow_html=True
        )
        time.sleep(delay)
    # 最终显示完整文本（无光标）
    placeholder.markdown(displayed_text)


def stream_text_fast(placeholder, full_text: str, chunk_size: int = 5, delay: float = 0.03):
    """
    快速打字机效果 - 按块输出（适合长文本）
    
    Args:
        placeholder: st.empty() 占位符
        full_text: 完整文本
        chunk_size: 每次输出的字符数
        delay: 每块的延迟（秒）
    """
    displayed_text = ""
    for i in range(0, len(full_text), chunk_size):
        displayed_text += full_text[i:i+chunk_size]
        placeholder.markdown(
            displayed_text + '<span class="typewriter-cursor"></span>',
            unsafe_allow_html=True
        )
        time.sleep(delay)
    placeholder.markdown(displayed_text)


def _render_trade_history_popup(agent_name: str):
    """
    渲染 AI 交易历史弹窗内容
    
    显示该 AI 的历史开仓/平仓记录，包含时间
    """
    try:
        from ai.ai_db_manager import get_ai_db_manager
        db = get_ai_db_manager()
        trades = db.get_trade_history(agent_name, limit=20)
        
        if not trades:
            st.info("暂无交易记录")
            return
        
        # 统计信息
        closed_trades = [t for t in trades if t['status'] == 'closed']
        open_trades = [t for t in trades if t['status'] == 'open']
        total_pnl = sum(t['pnl'] for t in closed_trades)
        win_count = sum(1 for t in closed_trades if t['pnl'] > 0)
        
        st.markdown(f"""
        **交易统计** | 已平仓: {len(closed_trades)} 笔 | 持仓中: {len(open_trades)} 笔 | 总盈亏: ${total_pnl:+.2f}
        """)
        
        st.markdown("---")
        
        # 当前持仓
        if open_trades:
            st.markdown("**📌 当前持仓**")
            for t in open_trades:
                side_emoji = "🟢" if t['side'] == 'long' else "🔴"
                st.markdown(f"""
                {side_emoji} **{t['symbol_short']}** {t['side_cn']}仓 | 
                入场: ${t['entry_price']:.2f} | 
                仓位: ${t['qty']:.0f} × {t['leverage']}x | 
                开仓: {t['open_time']}
                """)
            st.markdown("---")
        
        # 历史交易
        st.markdown("**📜 历史交易**")
        for t in closed_trades[:15]:  # 最多显示 15 条
            pnl = t['pnl']
            pnl_color = "green" if pnl > 0 else ("red" if pnl < 0 else "gray")
            pnl_sign = "+" if pnl > 0 else ""
            side_emoji = "🟢" if t['side'] == 'long' else "🔴"
            
            st.markdown(f"""
            {side_emoji} **{t['symbol_short']}** {t['side_cn']}仓 | 
            :{pnl_color}[{pnl_sign}${pnl:.2f}] | 
            {t['entry_price']:.2f} → {t['exit_price']:.2f} | 
            {t['open_time']} → {t['close_time']} ({t['duration']})
            """)
        
        if len(closed_trades) > 15:
            st.caption(f"... 还有 {len(closed_trades) - 15} 条记录")
            
    except Exception as e:
        st.error(f"加载交易记录失败: {e}")


def render_arena_card(name: str, data: Dict[str, Any]):
    """
    渲染单个 AI 交易员卡片
    
    Battle Royale 风格，强调竞争关系
    """
    rank = data.get('rank', 0)
    roi = data.get('roi', 0)
    win_rate = data.get('win_rate', 0)
    signal = data.get('signal', 'WAIT')
    confidence = data.get('confidence', 0)
    is_active = data.get('is_active', False)
    last_trade = data.get('last_trade', '')
    streak = data.get('streak', 0)
    reason = data.get('reason', '')
    
    # 卡片样式类
    card_class = 'arena-card'
    if rank == 1:
        card_class += ' champion'
        if is_active:
            card_class += ' active'
    
    # ROI 颜色和格式化（保留 2 位小数）
    roi_class = 'positive' if roi > 0 else ('negative' if roi < 0 else 'neutral')
    roi_sign = '+' if roi > 0 else ''
    roi_display = f"{roi:.2f}"  # 保留 2 位小数
    
    # 模型显示名称（从 AI_MODELS 获取）
    ai_info = AI_MODELS.get(name, {})
    display_name = ai_info.get('name', name.title())
    
    # 状态文本 - 根据实际调度器状态显示
    ai_takeover_live = st.session_state.get('ai_takeover_live', False)
    # 优先使用实际调度器状态，而不是 session_state（页面刷新后 session_state 会丢失）
    try:
        from ai.arena_scheduler import is_scheduler_running
        scheduler_running = is_scheduler_running()
    except ImportError:
        scheduler_running = st.session_state.get('arena_scheduler_running', False)
    
    if ai_takeover_live and rank == 1:
        # 实盘托管模式
        status_html = '<div class="status-indicator active">(๑•̀ㅂ•́)و 实盘资金主控中</div>'
    elif scheduler_running:
        # 模拟跑分中 + 闪烁动画表示"还活着"
        status_html = '<div class="status-indicator inactive"><span class="alive-dot"></span> 模拟跑分中</div>'
    else:
        status_html = '<div class="status-indicator inactive">⚠️ 待机中</div>'
    
    # 使用 Streamlit container
    with st.container(border=True):
        # Header: 名称 + 排名 + "还活着"闪烁
        col_name, col_rank = st.columns([2, 1])
        with col_name:
            # 如果调度器运行中，显示"还活着"闪烁文字
            alive_html = '<span class="alive-text">(๑•̀ㅂ•́)و✧ 还活着</span>' if scheduler_running else ''
            st.markdown(f"### {display_name}{alive_html}", unsafe_allow_html=True)
        with col_rank:
            st.markdown(render_rank_badge(rank), unsafe_allow_html=True)
        
        # 连胜/连败
        if streak != 0:
            st.markdown(render_streak_badge(streak), unsafe_allow_html=True)
        
        st.divider()
        
        # Metrics: ROI + WinRate
        col_roi, col_wr = st.columns(2)
        with col_roi:
            st.markdown(f"""
            <div class="metric-label">ROI (本月)</div>
            <div class="metric-value {roi_class}">{roi_sign}{roi_display}%</div>
            """, unsafe_allow_html=True)
        with col_wr:
            st.markdown(f"""
            <div class="metric-label">胜率</div>
            <div class="metric-value neutral">{win_rate}%</div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Signal: 大号信号标签
        st.markdown(f"""
        <div style="text-align: center; margin: 16px 0;">
            {render_signal_tag(signal)}
            <div style="margin-top: 8px; color: #718096; font-size: 12px;">
                置信度: {confidence}%
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Status
        st.markdown(status_html, unsafe_allow_html=True)
        
        # 最近交易
        if last_trade:
            st.caption(f"📝 {last_trade}")
        
        # 查看推理按钮 - 显示各币种分析
        col_reason, col_history = st.columns(2)
        with col_reason:
            with st.popover("(・ω・) 查看推理"):
                st.markdown("**各币种分析:**")
                st.markdown("---")
                st.markdown(reason)
        
        with col_history:
            with st.popover("📊 交易记录"):
                _render_trade_history_popup(name)


def render_arena_section(arena_data: Dict[str, Dict], ai_enabled: bool):
    """
    渲染 AI 竞技场区域
    
    根据已配置的 AI 动态显示卡片
    """
    # 获取已启用的 AI 列表
    enabled_ais = ArenaDataInterface.get_enabled_ai_list()
    
    if not enabled_ais:
        # 没有配置任何 AI
        st.markdown("""
        <div style="
            text-align: center;
            padding: 60px 20px;
            background: rgba(255, 255, 255, 0.02);
            border: 2px dashed rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            color: #718096;
        ">
            <div style="font-size: 48px; margin-bottom: 16px;">🤖</div>
            <div style="font-size: 18px; font-weight: 600; margin-bottom: 8px;">等待 AI 接入...</div>
            <div style="font-size: 14px;">请在左侧控制面板配置 AI API</div>
        </div>
        """, unsafe_allow_html=True)
        return
    
    # 获取接管状态
    takeover_status = ArenaDataInterface.get_takeover_status()
    active_ai = takeover_status.get('active_ai')
    
    # 过滤出已启用的 AI 数据
    filtered_data = {}
    for ai_id in enabled_ais:
        if ai_id in arena_data:
            data = arena_data[ai_id].copy()
            # 标记当前接管的 AI
            data['is_active'] = (ai_id == active_ai and takeover_status.get('enabled'))
            filtered_data[ai_id] = data
        else:
            # 新配置的 AI，使用默认数据
            ai_info = AI_MODELS.get(ai_id, {})
            filtered_data[ai_id] = {
                "rank": len(filtered_data) + 1,
                "roi": 0,
                "win_rate": 0,
                "signal": "WAIT",
                "confidence": 0,
                "reason": f"## {ai_info.get('name', ai_id)} 待初始化\n\n等待首次分析...",
                "is_active": (ai_id == active_ai and takeover_status.get('enabled')),
                "last_trade": "",
                "streak": 0
            }
    
    # 按排名排序
    sorted_ais = sorted(filtered_data.items(), key=lambda x: x[1].get('rank', 99))
    
    # 动态列数：有多少 AI 就显示多少列（自动适应）
    num_ais = len(sorted_ais)
    
    if num_ais == 0:
        return
    
    # 所有 AI 在同一行显示
    cols = st.columns(num_ais)
    for i, (name, data) in enumerate(sorted_ais):
        with cols[i]:
            render_arena_card(name, data)


def render_ai_takeover_section():
    """
    渲染 AI 接管交易区域
    
    包含：
    1. AI 选择器（多选，选择参与对战的 AI）
    2. 后台调度器状态显示
    3. 启动/停止调度器按钮
    4. 对战间隔配置
    """
    # 导入调度器模块
    try:
        from ai.arena_scheduler import (
            start_background_scheduler,
            stop_background_scheduler,
            is_scheduler_running,
            get_latest_battle_result,
            get_background_scheduler
        )
        has_scheduler = True
    except ImportError:
        has_scheduler = False
    
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    ">
        <span style="color: white; font-size: 14px; font-weight: 600;">◈ AI 竞技场调度</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 获取接管状态
    takeover_status = ArenaDataInterface.get_takeover_status()
    ai_takeover = takeover_status.get('enabled', False)
    
    # 获取已启用的 AI 列表
    enabled_ais = ArenaDataInterface.get_enabled_ai_list()
    
    if not enabled_ais:
        st.warning("(・_・) 请先配置 AI API")
        st.caption("在下方 API 配置区域添加至少一个 AI")
        return
    
    # 检查调度器状态
    scheduler_running = has_scheduler and is_scheduler_running()
    
    # AI 多选器（选择参与对战的 AI）
    st.markdown("""
    <div style="color: #a0aec0; font-size: 11px; margin-bottom: 6px;">
        选择参与对战的 AI（可多选）
    </div>
    """, unsafe_allow_html=True)
    
    ai_options = {ai_id: AI_MODELS[ai_id]['name'] for ai_id in enabled_ais}
    
    # 从 session_state 或数据库获取已选择的 AI
    default_selected = st.session_state.get('arena_selected_ais')
    if default_selected is None:
        # 尝试从数据库恢复
        try:
            from ai.ai_config_manager import get_ai_config_manager
            config_mgr = get_ai_config_manager()
            state = config_mgr.get_scheduler_state()
            saved_agents = state.get('agents', [])
            if saved_agents:
                default_selected = [ai for ai in saved_agents if ai in enabled_ais]
        except Exception:
            pass
        
        # 如果数据库也没有，使用默认值（所有已启用的 AI）
        if not default_selected:
            default_selected = list(enabled_ais)
    
    default_selected = [ai for ai in default_selected if ai in enabled_ais]
    
    selected_ais = st.multiselect(
        "参战 AI",
        options=list(ai_options.keys()),
        default=default_selected,
        format_func=lambda x: ai_options.get(x, x),
        key="arena_ai_multiselect",
        disabled=scheduler_running,
        label_visibility="collapsed"
    )
    st.session_state.arena_selected_ais = selected_ais
    
    if len(selected_ais) < 1:
        st.warning("至少选择 1 个 AI")
        return
    
    st.markdown("<div style='height: 6px'></div>", unsafe_allow_html=True)
    
    # 运行状态显示（删除了间隔选择器，AI 跟随 K 线周期触发）
    all_tfs = st.session_state.get('ai_timeframes', ['5m'])
    if not all_tfs:
        all_tfs = ['5m']
    # 显示触发周期（最短周期）和分析周期数量
    trigger_tf = min(all_tfs, key=lambda tf: {'1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720, '1D': 1440, '3D': 4320, '1W': 10080}.get(tf, 999))
    tf_display = f"{trigger_tf} 触发, {len(all_tfs)} 周期分析" if len(all_tfs) > 1 else trigger_tf
    
    st.markdown(f"""
    <div style="
        background: {'rgba(0, 212, 170, 0.2)' if scheduler_running else 'rgba(128, 128, 128, 0.2)'};
        border-radius: 6px;
        padding: 8px 12px;
        text-align: center;
    ">
        <span style="color: {'#00d4aa' if scheduler_running else '#888'}; font-size: 12px;">
            {'● 运行中' if scheduler_running else '○ 已停止'} | {tf_display}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    
    # AI 托管实盘开关（需要主界面为实盘模式才生效）
    ai_takeover_enabled = st.checkbox(
        "(⚠️) 启用 AI 托管实盘",
        value=st.session_state.get('ai_takeover_live', False),
        key="ai_takeover_checkbox",
        disabled=scheduler_running,
        help="启用后，AI 将执行真实交易（需主界面为实盘模式）"
    )
    st.session_state.ai_takeover_live = ai_takeover_enabled
    
    if ai_takeover_enabled:
        st.markdown("""
        <div style="
            background: rgba(255, 107, 107, 0.15);
            border: 1px solid rgba(255, 107, 107, 0.4);
            border-radius: 6px;
            padding: 8px;
            margin: 4px 0;
            font-size: 11px;
            color: #ff6b6b;
        ">
            ⚠️ 托管已启用！AI 决策将执行真实交易（需主界面为实盘模式）
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    
    if scheduler_running:
        # 调度器运行中
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(0, 212, 170, 0.2), rgba(0, 184, 148, 0.15));
            border: 1px solid rgba(0, 212, 170, 0.4);
            border-radius: 8px;
            padding: 10px 12px;
            margin-bottom: 8px;
            text-align: center;
        ">
            <span style="color: #00d4aa; font-size: 13px; font-weight: 600;">
                (๑•̀ㅂ•́)و AI 竞技场运行中
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        # 简单状态日志（每10秒刷新）
        _render_arena_status_log()
        
        # 显示最新对战结果
        if has_scheduler:
            latest_result = get_latest_battle_result()
            if latest_result:
                st.caption(f"最新对战: {latest_result.symbol} | 共识: {latest_result.consensus or 'N/A'}")
        
        # 最近决策记录（可展开）
        with st.expander("(・ω・) 最近决策记录", expanded=False):
            _render_recent_decisions_fragment()
        
        # 停止按钮
        if st.button("(・_・) 停止竞技场", key="stop_arena_scheduler", width="stretch"):
            if has_scheduler:
                # 先清除持久化状态（确保不会自动恢复）
                try:
                    from ai.ai_config_manager import get_ai_config_manager
                    config_mgr = get_ai_config_manager()
                    config_mgr.clear_scheduler_state()
                except Exception as e:
                    logger.warning(f"清除调度器状态失败: {e}")
                
                # 停止调度器
                stop_background_scheduler()
                ArenaDataInterface.stop_takeover()
                
                # 清除 session 状态
                st.session_state.arena_scheduler_running = False
                st.session_state.ai_takeover_live = False
                st.session_state._scheduler_restored = False  # 允许下次恢复检查
                
                st.success("竞技场已停止")
                st.rerun()
    else:
        # 调度器未运行
        if st.button("(ノ°▽°)ノ 启动 AI 竞技场", key="start_arena_scheduler", width="stretch", type="primary"):
            if not has_scheduler:
                st.error("调度器模块未加载")
                return
            
            # 获取配置（使用 auto_symbols，与交易池配置同步）
            trading_pool = st.session_state.get('auto_symbols', ['BTC/USDT:USDT'])
            # 获取所有选中的周期（方案 B：多周期分析）
            timeframes = st.session_state.get('ai_timeframes', ['5m'])
            if not timeframes:
                timeframes = ['5m']
            
            # 获取用户风格 Prompt（优先使用自定义，否则使用预设）
            user_prompt = st.session_state.get('ai_custom_prompt', '')
            if not user_prompt:
                # 如果没有自定义 Prompt，使用当前预设
                try:
                    from ai.ai_config_manager import PROMPT_PRESETS
                    preset_id = st.session_state.get('ai_preset_id', 'balanced')
                    if preset_id in PROMPT_PRESETS:
                        user_prompt = PROMPT_PRESETS[preset_id].prompt
                except Exception:
                    pass
            
            # 获取 API Keys
            api_configs = ArenaDataInterface.get_ai_api_configs()
            api_keys = {
                ai_id: config.get('api_key', '')
                for ai_id, config in api_configs.items()
                if config.get('enabled') and config.get('api_key')
            }
            
            # 获取 AI 托管状态
            ai_takeover = st.session_state.get('ai_takeover_live', False)
            
            # 启动调度器（传递完整的 timeframes 列表）
            # 调度器会自动选择最短周期作为触发周期
            try:
                start_background_scheduler(
                    symbols=trading_pool,
                    timeframes=timeframes,  # 传递所有周期
                    agents=selected_ais,
                    api_keys=api_keys,
                    user_prompt=user_prompt,
                    ai_takeover=ai_takeover
                )
                ArenaDataInterface.start_takeover(selected_ais[0])
                
                # 设置调度器运行状态
                st.session_state.arena_scheduler_running = True
                
                # 持久化：保存调度器状态（UI 重启后可恢复）
                try:
                    from ai.ai_config_manager import get_ai_config_manager
                    config_mgr = get_ai_config_manager()
                    config_mgr.save_scheduler_state(
                        enabled=True,
                        symbols=trading_pool,
                        timeframes=timeframes,
                        agents=selected_ais,
                        ai_takeover=ai_takeover,
                        user_prompt=user_prompt
                    )
                except Exception:
                    pass
                
                mode_str = "实盘托管" if ai_takeover else "模拟交易"
                tf_display = ', '.join(timeframes) if len(timeframes) <= 3 else f"{timeframes[0]}等{len(timeframes)}个周期"
                st.success(f"竞技场已启动 | {len(selected_ais)} 个 AI | [{tf_display}] | {mode_str}")
                st.rerun()
            except Exception as e:
                st.error(f"启动失败: {e}")
        
        # 显示触发说明
        all_tfs = st.session_state.get('ai_timeframes', ['5m'])
        if all_tfs:
            # 找出最短周期作为触发周期
            tf_order = {'1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720, '1D': 1440, '3D': 4320, '1W': 10080}
            trigger_tf = min(all_tfs, key=lambda tf: tf_order.get(tf, 999))
            if len(all_tfs) == 1:
                st.caption(f"AI 将跟随 {trigger_tf} K线周期自动分析")
            else:
                st.caption(f"AI 将跟随 {trigger_tf} 触发，同时分析 {len(all_tfs)} 个周期数据")


def render_ai_api_config_section():
    """
    渲染 AI API 配置区域
    
    包含：
    1. 已配置的 AI 列表（显示选择的模型）
    2. 添加新 AI 的表单（支持模型选择）
    3. 删除 AI 配置
    """
    # 获取模型版本信息
    try:
        from ai.ai_providers import MODEL_VERSION_UPDATED
        version_info = f"模型版本: {MODEL_VERSION_UPDATED}"
    except ImportError:
        version_info = ""
    
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    ">
        <span style="color: white; font-size: 14px; font-weight: 600;">◈ AI API 配置</span>
        <span style="color: rgba(255,255,255,0.7); font-size: 11px; float: right; margin-top: 2px;">{version_info}</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 获取模型列表的辅助函数
    def get_models_for_provider(provider_id: str) -> list:
        """获取指定服务商的模型列表"""
        try:
            from ai.ai_providers import AI_PROVIDERS, PROVIDER_ALIASES
            # 处理别名映射（如 spark_lite -> spark）
            real_id = PROVIDER_ALIASES.get(provider_id, provider_id)
            provider = AI_PROVIDERS.get(real_id)
            if provider:
                return [(m.id, f"{m.name}{'  [免费]' if m.is_free else ''}") for m in provider.models]
        except ImportError:
            pass
        # 回退到默认模型
        spark_models = [("lite", "Spark Lite  [免费]"), ("generalv3", "Spark Pro"), ("generalv3.5", "Spark Max")]
        default_models = {
            "deepseek": [("deepseek-chat", "DeepSeek Chat"), ("deepseek-reasoner", "DeepSeek Reasoner")],
            "qwen": [("qwen-turbo", "Qwen Turbo"), ("qwen-plus", "Qwen Plus"), ("qwen-max", "Qwen Max")],
            "spark": spark_models,
            "spark_lite": spark_models,  # 别名也需要支持
            "hunyuan": [("hunyuan-lite", "混元 Lite  [免费]"), ("hunyuan-standard", "混元 Standard"), ("hunyuan-pro", "混元 Pro")],
            "glm": [("glm-4-flash", "GLM-4 Flash  [免费]"), ("glm-4-air", "GLM-4 Air"), ("glm-4", "GLM-4")],
            "doubao": [("doubao-lite-4k", "豆包 Lite 4K"), ("doubao-pro-4k", "豆包 Pro 4K"), ("doubao-pro-32k", "豆包 Pro 32K")],
            "perplexity": [("llama-3.1-sonar-small-128k-online", "Sonar Small"), ("llama-3.1-sonar-large-128k-online", "Sonar Large")],
            "openai": [("gpt-4o-mini", "GPT-4o Mini"), ("gpt-4o", "GPT-4o"), ("gpt-4-turbo", "GPT-4 Turbo")],
            "claude": [("claude-3-haiku-20240307", "Claude 3 Haiku"), ("claude-3-sonnet-20240229", "Claude 3 Sonnet")],
        }
        return default_models.get(provider_id, [])
    
    def get_default_model(provider_id: str) -> str:
        """获取默认模型"""
        try:
            from ai.ai_providers import AI_PROVIDERS, PROVIDER_ALIASES
            # 处理别名映射（如 spark_lite -> spark）
            real_id = PROVIDER_ALIASES.get(provider_id, provider_id)
            provider = AI_PROVIDERS.get(real_id)
            if provider:
                return provider.default_model
        except ImportError:
            pass
        defaults = {
            "deepseek": "deepseek-chat",
            "qwen": "qwen-max",
            "spark": "lite",
            "spark_lite": "lite",  # 别名也需要支持
            "hunyuan": "hunyuan-lite",
            "glm": "glm-4-flash",
            "doubao": "doubao-pro-4k",
            "perplexity": "llama-3.1-sonar-small-128k-online",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-haiku-20240307",
        }
        return defaults.get(provider_id, "")
    
    # 获取当前配置
    configs = ArenaDataInterface.get_ai_api_configs()
    
    # 显示已配置的 AI
    if configs:
        for ai_id, config in configs.items():
            ai_info = AI_MODELS.get(ai_id, {})
            verified = config.get('verified', False)
            current_model = config.get('model', '') or get_default_model(ai_id)
            status_icon = "(^_^)" if verified else "(x_x)"
            status_color = "#00d4aa" if verified else "#ff6b6b"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"""
                <div style="
                    display: flex;
                    flex-direction: column;
                    gap: 2px;
                    padding: 6px 0;
                ">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="color: white; font-size: 13px;">{ai_info.get('name', ai_id)}</span>
                        <span style="color: {status_color}; font-size: 12px;">{status_icon}</span>
                    </div>
                    <span style="color: #718096; font-size: 11px;">模型: {current_model}</span>
                </div>
                """, unsafe_allow_html=True)
            with col2:
                if st.button("X", key=f"del_ai_{ai_id}", help=f"删除 {ai_info.get('name', ai_id)}"):
                    ArenaDataInterface.delete_ai_api_config(ai_id)
                    st.rerun()
            
            # 模型切换（折叠）
            with st.expander(f"切换模型", expanded=False):
                models = get_models_for_provider(ai_id)
                if models:
                    model_ids = [m[0] for m in models]
                    model_names = [m[1] for m in models]
                    current_idx = model_ids.index(current_model) if current_model in model_ids else 0
                    
                    new_model_name = st.selectbox(
                        "选择模型",
                        model_names,
                        index=current_idx,
                        key=f"model_select_{ai_id}",
                        label_visibility="collapsed"
                    )
                    new_model_id = model_ids[model_names.index(new_model_name)]
                    
                    if new_model_id != current_model:
                        if st.button("保存", key=f"save_model_{ai_id}", type="primary"):
                            # 更新模型配置
                            result = ArenaDataInterface.save_ai_api_config(
                                ai_id, 
                                config.get('api_key', ''),
                                model=new_model_id
                            )
                            if result.get('ok'):
                                st.success("模型已更新")
                                st.rerun()
    else:
        st.caption("暂无配置，请添加 AI")
    
    # 添加新 AI 配置
    with st.expander("+ 添加 AI", expanded=not configs):
        # 获取未配置的 AI 列表
        unconfigured_ais = [
            ai_id for ai_id in AI_MODELS.keys()
            if ai_id not in configs
        ]
        
        if not unconfigured_ais:
            st.info("所有 AI 已配置")
        else:
            # AI 选择
            ai_options = [(AI_MODELS[ai_id]['name'], ai_id) for ai_id in unconfigured_ais]
            ai_display_names = [opt[0] for opt in ai_options]
            ai_ids = [opt[1] for opt in ai_options]
            
            selected_display = st.selectbox(
                "选择 AI",
                ai_display_names,
                key="add_ai_selector",
                label_visibility="collapsed"
            )
            selected_ai_id = ai_ids[ai_display_names.index(selected_display)]
            
            # 模型选择
            models = get_models_for_provider(selected_ai_id)
            if models:
                model_ids = [m[0] for m in models]
                model_names = [m[1] for m in models]
                default_model = get_default_model(selected_ai_id)
                default_idx = model_ids.index(default_model) if default_model in model_ids else 0
                
                selected_model_name = st.selectbox(
                    "选择模型",
                    model_names,
                    index=default_idx,
                    key="add_ai_model_selector",
                    label_visibility="collapsed"
                )
                selected_model_id = model_ids[model_names.index(selected_model_name)]
            else:
                selected_model_id = ""
            
            # API Key 输入
            api_key = st.text_input(
                "API Key",
                type="password",
                placeholder=f"输入 {AI_MODELS[selected_ai_id]['name']} 的 API Key",
                key="add_ai_api_key",
                label_visibility="collapsed"
            )
            
            # 显示 API Key 格式提示
            from ai.ai_api_validator import API_KEY_PATTERNS
            pattern_info = API_KEY_PATTERNS.get(selected_ai_id)
            if pattern_info and pattern_info[0]:
                st.caption(f"格式: {pattern_info[0]}xxx...")
            
            # 保存按钮
            if st.button("保存并验证", key="save_ai_config", use_container_width=True, type="primary"):
                if api_key.strip():
                    # 显示验证中提示
                    with st.spinner(f"(・ω・) 正在验证 {AI_MODELS[selected_ai_id]['name']} API Key..."):
                        result = ArenaDataInterface.save_ai_api_config(
                            selected_ai_id, 
                            api_key.strip(),
                            model=selected_model_id
                        )
                    
                    if result.get('ok') and result.get('verified'):
                        st.success(f"(^_^) {result.get('message', '验证成功')}")
                        st.rerun()
                    elif result.get('ok'):
                        # 保存成功但未验证
                        st.warning(f"(・_・) {result.get('message', '未验证')}")
                    else:
                        st.error(f"(x_x) {result.get('message', '验证失败')}")
                else:
                    st.warning("请输入 API Key")


def render_trading_pool_section(actions: Dict):
    """
    渲染交易池配置区域（与主界面同步）
    
    在 AI 决策界面和主界面都可以修改交易池，
    修改后通过 session_state 和数据库同步
    """
    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        padding: 8px 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 15px rgba(79, 172, 254, 0.3);
    ">
        <span style="color: white; font-size: 14px; font-weight: 600;">⬢ 交易池</span>
    </div>
    """, unsafe_allow_html=True)
    
    # 导入符号处理工具
    try:
        from utils.symbol_utils import normalize_symbol, parse_symbol_input
    except ImportError:
        st.error("无法加载 symbol_utils")
        return
    
    # 设置默认交易池
    default_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
    if "auto_symbols" not in st.session_state:
        st.session_state.auto_symbols = default_symbols
    
    # 动态交易池设置
    st.caption("输入币种：btc, eth, sol...")
    symbol_input = st.text_area(
        "交易对列表(每行一个)",
        value="\n".join(st.session_state.auto_symbols),
        height=80,
        key="arena_symbol_input",
        label_visibility="collapsed"
    )
    
    if st.button("保存交易池", key="arena_save_pool", width="stretch", type="primary"):
        # 使用 parse_symbol_input 进行规范化
        new_symbols = parse_symbol_input(symbol_input)
        if new_symbols:
            # 先写DB
            db_write_success = False
            try:
                symbols_str = ",".join(new_symbols)
                actions.get("update_bot_config", lambda **kwargs: None)(symbols=symbols_str)
                actions.get("set_control_flags", lambda **kwargs: None)(reload_config=1)
                db_write_success = True
            except Exception as e:
                st.error(f"保存失败: {str(e)[:50]}")
            
            # DB 写入成功后更新 session_state
            if db_write_success:
                st.session_state.auto_symbols = new_symbols
                st.success(f"交易池已更新: {', '.join(new_symbols)}")
        else:
            st.warning("交易池不能为空")


def render_command_center():
    """
    渲染 AI 信息获取配置区域
    
    包含：
    1. 时间周期选择（多选）
    2. K线数量配置
    3. 技术指标选择
    4. 自定义提示词（带预设和数据库持久化）
    """
    # 导入配置管理器
    try:
        from ai.ai_config_manager import get_ai_config_manager, PROMPT_PRESETS
        config_mgr = get_ai_config_manager()
        has_config_mgr = True
    except ImportError:
        has_config_mgr = False
        config_mgr = None
    
    # 从数据库加载配置（首次）
    if has_config_mgr and 'ai_config_loaded' not in st.session_state:
        settings = config_mgr.get_ai_settings()
        st.session_state.ai_timeframes = settings.get('timeframes', ['5m', '15m', '1h', '4h'])
        st.session_state.ai_kline_count = settings.get('kline_count', 100)
        st.session_state.ai_indicators = settings.get('indicators', ['MA', 'RSI', 'MACD'])
        st.session_state.ai_custom_prompt = settings.get('custom_prompt', '')
        st.session_state.ai_preset_id = settings.get('preset_id', 'balanced')
        # 加载 AI API 配置
        st.session_state.ai_api_configs = config_mgr.get_all_ai_api_configs()
        st.session_state.ai_config_loaded = True
    
    # 初始化 session_state（回退默认值）
    if 'ai_timeframes' not in st.session_state:
        st.session_state.ai_timeframes = ['5m', '15m', '1h', '4h']
    if 'ai_kline_count' not in st.session_state:
        st.session_state.ai_kline_count = 100
    if 'ai_indicators' not in st.session_state:
        st.session_state.ai_indicators = ['MA', 'RSI', 'MACD']
    if 'ai_preset_id' not in st.session_state:
        st.session_state.ai_preset_id = 'balanced'
    
    # ============ 时间周期选择 ============
    with st.expander("(・ω・) 技术指标", expanded=True):
        st.markdown("""
        <div style="color: #a0aec0; font-size: 11px; margin-bottom: 8px;">
            ◎ 时间周期
        </div>
        <div style="color: #718096; font-size: 10px; margin-bottom: 10px;">
            选择要分析的K线周期（可多选）
        </div>
        """, unsafe_allow_html=True)
        
        # 时间周期分组
        st.markdown('<span style="color: #ff6b6b; font-size: 11px;">超短线</span>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        tf_1m = col1.checkbox("1m", value='1m' in st.session_state.ai_timeframes, key="tf_1m")
        tf_3m = col2.checkbox("3m", value='3m' in st.session_state.ai_timeframes, key="tf_3m")
        tf_5m = col3.checkbox("5m", value='5m' in st.session_state.ai_timeframes, key="tf_5m")
        
        st.markdown('<span style="color: #feca57; font-size: 11px;">日内</span>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        tf_15m = col1.checkbox("15m", value='15m' in st.session_state.ai_timeframes, key="tf_15m")
        tf_30m = col2.checkbox("30m", value='30m' in st.session_state.ai_timeframes, key="tf_30m")
        tf_1h = col3.checkbox("1h", value='1h' in st.session_state.ai_timeframes, key="tf_1h")
        
        st.markdown('<span style="color: #00d4aa; font-size: 11px;">波段</span>', unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns(5)
        tf_2h = col1.checkbox("2h", value='2h' in st.session_state.ai_timeframes, key="tf_2h")
        tf_4h = col2.checkbox("4h", value='4h' in st.session_state.ai_timeframes, key="tf_4h")
        tf_6h = col3.checkbox("6h", value='6h' in st.session_state.ai_timeframes, key="tf_6h")
        tf_8h = col4.checkbox("8h", value='8h' in st.session_state.ai_timeframes, key="tf_8h")
        tf_12h = col5.checkbox("12h", value='12h' in st.session_state.ai_timeframes, key="tf_12h")
        
        st.markdown('<span style="color: #a0aec0; font-size: 11px;">趋势</span>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        tf_1d = col1.checkbox("1D", value='1D' in st.session_state.ai_timeframes, key="tf_1d")
        tf_3d = col2.checkbox("3D", value='3D' in st.session_state.ai_timeframes, key="tf_3d")
        tf_1w = col3.checkbox("1W", value='1W' in st.session_state.ai_timeframes, key="tf_1w")
        
        # 收集选中的时间周期
        selected_tfs = []
        if tf_1m: selected_tfs.append('1m')
        if tf_3m: selected_tfs.append('3m')
        if tf_5m: selected_tfs.append('5m')
        if tf_15m: selected_tfs.append('15m')
        if tf_30m: selected_tfs.append('30m')
        if tf_1h: selected_tfs.append('1h')
        if tf_2h: selected_tfs.append('2h')
        if tf_4h: selected_tfs.append('4h')
        if tf_6h: selected_tfs.append('6h')
        if tf_8h: selected_tfs.append('8h')
        if tf_12h: selected_tfs.append('12h')
        if tf_1d: selected_tfs.append('1D')
        if tf_3d: selected_tfs.append('3D')
        if tf_1w: selected_tfs.append('1W')
        
        if selected_tfs:
            # 找出最短周期作为触发周期
            tf_order = {'1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720, '1D': 1440, '3D': 4320, '1W': 10080}
            trigger_tf = min(selected_tfs, key=lambda tf: tf_order.get(tf, 999))
            if len(selected_tfs) == 1:
                st.caption(f"分析周期: {trigger_tf}")
            else:
                st.caption(f"触发: {trigger_tf} | 分析: {len(selected_tfs)} 个周期")
        
        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
        
        # K线数量（用于计算技术指标，建议 50-200）
        kline_count = st.number_input(
            "K线数量（用于指标计算）:",
            min_value=50,
            max_value=500,
            value=st.session_state.ai_kline_count,
            step=50,
            key="ai_kline_input",
            help="获取的历史 K 线数量，用于计算技术指标。建议 100-200，太少会导致指标不准确。"
        )
        
        st.markdown("<div style='height: 12px'></div>", unsafe_allow_html=True)
        
        # 技术指标选择
        st.markdown("""
        <div style="color: #a0aec0; font-size: 11px; margin-bottom: 8px;">
            (・∀・) 技术指标
        </div>
        """, unsafe_allow_html=True)
        
        available_indicators = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR', 'OBV', 'VWAP']
        selected_indicators = st.multiselect(
            "选择指标",
            available_indicators,
            default=st.session_state.ai_indicators,
            key="ai_indicator_select",
            label_visibility="collapsed"
        )
        
        # 更新 session_state
        st.session_state.ai_timeframes = selected_tfs
        st.session_state.ai_kline_count = kline_count
        st.session_state.ai_indicators = selected_indicators
    
    # ============ AI 风格提示词（带预设） ============
    with st.expander("(・ω・)ノ AI 风格提示词", expanded=False):
        # 预设选择器
        if has_config_mgr:
            preset_options = {
                'aggressive': '(>_<) 激进 - 高风险高收益',
                'balanced': '(・_・) 均衡 - 风险收益平衡',
                'conservative': '(￣▽￣) 保守 - 低风险稳健',
                'scalping': '(*^▽^*) 超短线 - 快进快出',
                'trend_following': '(・∀・) 趋势跟踪 - 顺势而为'
            }
            
            current_preset = st.session_state.get('ai_preset_id', 'balanced')
            selected_preset = st.selectbox(
                "选择预设风格",
                options=list(preset_options.keys()),
                format_func=lambda x: preset_options[x],
                index=list(preset_options.keys()).index(current_preset) if current_preset in preset_options else 1,
                key="ai_preset_selector",
                label_visibility="collapsed"
            )
            
            # 显示预设详情
            if selected_preset in PROMPT_PRESETS:
                preset = PROMPT_PRESETS[selected_preset]
                # 根据预设 ID 显示对应的风控参数
                preset_info = {
                    "conservative": {"rr": ">=3.0", "conf": ">=75", "max_pos": "3"},
                    "balanced": {"rr": ">=2.0", "conf": ">=70", "max_pos": "5"},
                    "aggressive": {"rr": ">=1.5", "conf": ">=65", "max_pos": "6"},
                    "scalping": {"rr": ">=1.0", "conf": ">=80", "max_pos": "4"},
                    "trend_following": {"rr": ">=2.5", "conf": ">=80", "max_pos": "3"},
                }
                info = preset_info.get(selected_preset, {"rr": "-", "conf": "-", "max_pos": "-"})
                risk_color = {"low": "#48bb78", "medium": "#ecc94b", "high": "#f56565"}.get(preset.risk_level, "#a0aec0")
                st.markdown(f"""
                <div style="
                    background: rgba(255,255,255,0.05);
                    border-radius: 8px;
                    padding: 10px;
                    margin: 8px 0;
                    font-size: 11px;
                    color: #a0aec0;
                ">
                    <div style="margin-bottom: 6px;">{preset.description}</div>
                    <div>RR{info['rr']} | 置信度{info['conf']} | 最多{info['max_pos']}仓 | <span style="color:{risk_color}">风险:{preset.risk_level}</span></div>
                </div>
                """, unsafe_allow_html=True)
            
            # 应用预设按钮
            if st.button("应用预设", key="apply_preset", width="stretch"):
                if selected_preset in PROMPT_PRESETS:
                    preset = PROMPT_PRESETS[selected_preset]
                    st.session_state.ai_preset_id = selected_preset
                    st.session_state.ai_custom_prompt = preset.prompt
                    # 保存到数据库
                    if config_mgr:
                        config_mgr.set_preset(selected_preset)
                        config_mgr.set_custom_prompt(preset.prompt)
                    # 设置成功提示标记
                    st.session_state.preset_applied = preset.name
                    st.rerun()
            
            # 显示成功提示（在 rerun 后显示）
            if st.session_state.get('preset_applied'):
                st.success(f"(^_^) 已应用 {st.session_state.preset_applied} 预设")
                del st.session_state.preset_applied
        
        st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
        
        # 自定义提示词输入
        st.markdown("""
        <div style="color: #a0aec0; font-size: 11px; margin-bottom: 8px;">
            自定义提示词（会作为 AI 的交易风格指令）
        </div>
        """, unsafe_allow_html=True)
        
        # 提示词说明（可折叠）
        with st.expander("(?) 提示词填写说明", expanded=False):
            st.markdown("""
            <div style="font-size: 11px; color: #a0aec0; line-height: 1.6;">
            
            **提示词定义 AI 的交易风格和铁律，AI 会严格遵守。**
            
            **核心要素：**
            - 风险回报比 (RR)：如 "RR >= 2.0 才能开仓"
            - 置信度门槛：如 "置信度 < 70 禁止开仓"
            - 最大持仓数：如 "最多同时持仓 5 个币种"
            - 冷却时间：如 "平仓后 10 分钟内禁止同方向开仓"
            - 仓位/杠杆：由 AI 根据市场情况自主决定
            
            **内置预设风格：**
            - 僧侣型：RR>=3.0, 置信度>=75, 低频高质量
            - 均衡型：RR>=2.0, 置信度>=70, 风险收益平衡
            - 猎人型：RR>=1.5, 置信度>=65, 高频捕捉机会
            - 闪电型：RR>=1.0, 置信度>=80, 超短线快进快出
            - 冲浪型：RR>=2.5, 置信度>=80, 只做趋势行情
            
            **建议直接选择预设，或基于预设微调。**
            </div>
            """, unsafe_allow_html=True)
        
        custom_prompt = st.text_area(
            "自定义提示词",
            value=st.session_state.get('ai_custom_prompt', ''),
            placeholder="输入你的交易风格指令，如：保守策略，仓位3%，止损1.5%...",
            height=120,
            key='ai_prompt_input',
            label_visibility="collapsed"
        )
        
        # 保存提示词到 session_state
        if custom_prompt != st.session_state.get('ai_custom_prompt', ''):
            st.session_state.ai_custom_prompt = custom_prompt
        
        # 保存配置按钮
        if st.button("(^_^)b 保存配置", type="primary", width="stretch"):
            # 保存到数据库
            if has_config_mgr and config_mgr:
                settings = {
                    'timeframes': selected_tfs,
                    'kline_count': kline_count,
                    'indicators': selected_indicators,
                    'preset_id': st.session_state.get('ai_preset_id', 'balanced'),
                    'custom_prompt': custom_prompt,
                }
                config_mgr.save_ai_settings(settings)
                st.success(f"配置已保存: {len(selected_tfs)}个周期, {kline_count}根K线, {len(selected_indicators)}个指标")
            else:
                st.info(f"已应用: {len(selected_tfs)}个周期, {kline_count}根K线, {len(selected_indicators)}个指标")
    
    return True


def plot_nofx_equity(df):
    """
    NOFX 风格金色渐变资金曲线图表
    
    特点：
    1. 金色渐变填充 (#F7D154)
    2. 极简坐标轴（Y轴在右侧，虚线网格）
    3. 透明背景
    4. 当前价格指示线
    5. 悬浮提示深灰色背景
    
    参数:
        df: DataFrame，包含 'timestamp' 和 'equity' 两列
    """
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.warning("请安装 plotly: pip install plotly")
        return
    
    if df is None or df.empty:
        st.info("暂无资金曲线数据")
        return
    
    # 获取数据
    x_data = df['timestamp']
    y_data = df['equity']
    
    # 最新净值
    latest_equity = y_data.iloc[-1]
    
    # 创建图表
    fig = go.Figure()
    
    # 主曲线 - 金色渐变填充
    fig.add_trace(go.Scatter(
        x=x_data,
        y=y_data,
        mode='lines',
        name='净值',
        line=dict(
            color='#F7D154',  # 金色
            width=2,
            shape='spline',  # 平滑曲线
            smoothing=0.8
        ),
        fill='tozeroy',
        fillcolor='rgba(247, 209, 84, 0.15)',  # 金色半透明填充
        hovertemplate='$%{y:,.2f}<extra></extra>'
    ))
    
    # 当前价格水平线
    fig.add_hline(
        y=latest_equity,
        line=dict(
            color='#F7D154',
            width=1,
            dash='dot'
        ),
        annotation=dict(
            text=f"${latest_equity:,.2f}",
            font=dict(color='#F7D154', size=12),
            bgcolor='rgba(30, 30, 30, 0.8)',
            bordercolor='#F7D154',
            borderwidth=1,
            borderpad=4,
            xanchor='left',
            yanchor='middle'
        ),
        annotation_position='right'
    )
    
    # 布局配置 - NOFX 极简风格
    fig.update_layout(
        # 透明背景
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        
        # 零边距
        margin=dict(l=0, r=60, t=10, b=30),
        
        # 高度
        height=280,
        
        # 字体
        font=dict(
            family='Inter, Roboto, sans-serif',
            color='#888888',
            size=11
        ),
        
        # 隐藏图例
        showlegend=False,
        
        # 悬浮提示样式
        hoverlabel=dict(
            bgcolor='#1E1E1E',
            font=dict(color='white', size=12),
            bordercolor='#333333'
        ),
        
        # X轴配置
        xaxis=dict(
            showgrid=False,
            showline=False,
            zeroline=False,
            tickfont=dict(color='#666666', size=10),
            tickformat='%m/%d',
        ),
        
        # Y轴配置 - 右侧，虚线网格
        yaxis=dict(
            side='right',
            showgrid=True,
            gridcolor='rgba(51, 51, 51, 0.5)',
            gridwidth=0.5,
            griddash='dot',
            showline=False,
            zeroline=False,
            tickfont=dict(color='#666666', size=10),
            tickformat='$,.0f',
        ),
        
        # 拖拽模式
        dragmode=False,
    )
    
    # 渲染图表
    st.plotly_chart(fig, width="stretch", config={
        'displayModeBar': False,  # 隐藏工具栏
        'staticPlot': False,
    })


def render_champion_view(arena_data: Dict[str, Dict]):
    """
    渲染冠军视野 Tab
    
    展示当前排名第一的 AI 的详细分析
     使用真实数据，没有交易时显示空状态
    """
    import pandas as pd
    import numpy as np
    
    # 找到排名第一的 AI
    champion = None
    champion_name = None
    for name, data in arena_data.items():
        if data.get('rank') == 1:
            champion = data
            champion_name = name
            break
    
    if not champion:
        st.info("(・ω・) 暂无冠军数据，请先配置 AI 并启动竞技场")
        return
    
    # 获取 AI 信息
    ai_info = AI_MODELS.get(champion_name, {})
    display_name = ai_info.get('name', champion_name.title())
    
    # 检查调度器是否运行中
    try:
        from ai.arena_scheduler import is_scheduler_running
        scheduler_running = is_scheduler_running()
    except ImportError:
        scheduler_running = False
    
    # 冠军信息头
    status_text = "竞技场运行中" if scheduler_running else "等待启动"
    status_color = "#00d4aa" if scheduler_running else "#718096"
    
    st.markdown(f"""
    <div class="champion-view">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 16px;">
            <span style="font-size: 18px; color: #ffd700;">(☆▽☆)</span>
            <div>
                <div style="font-size: 20px; font-weight: 700; color: #ffd700;">
                    {display_name}
                </div>
                <div style="font-size: 12px; color: {status_color};">{status_text}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 从数据库获取真实统计数据
    real_stats = _get_real_ai_stats(champion_name)
    
    # 关键指标（使用真实数据）
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        roi = real_stats.get('total_pnl', 0)
        st.metric("累计盈亏", f"${roi:+.2f}" if roi != 0 else "$0.00")
    with col2:
        win_rate = real_stats.get('win_rate', 0)
        st.metric("胜率", f"{win_rate:.0f}%" if real_stats.get('total_trades', 0) > 0 else "--")
    with col3:
        total_trades = real_stats.get('total_trades', 0)
        st.metric("交易次数", str(total_trades))
    with col4:
        streak = real_stats.get('streak', 0)
        if streak > 0:
            streak_text = f"{streak}连胜"
        elif streak < 0:
            streak_text = f"{abs(streak)}连败"
        else:
            streak_text = "--"
        st.metric("连胜/败", streak_text)
    
    st.divider()
    
    # 资金曲线图表
    st.markdown("### 资金曲线")
    
    # 从数据库获取真实资金曲线
    df_equity = _get_real_equity_curve(champion_name)
    
    if df_equity is not None and not df_equity.empty:
        # 渲染 NOFX 风格资金曲线
        plot_nofx_equity(df_equity)
        
        # 资金曲线统计
        balance = df_equity['equity'].values
        col1, col2, col3 = st.columns(3)
        with col1:
            max_val = balance.max()
            st.metric("最高净值", f"${max_val:,.2f}")
        with col2:
            min_val = balance.min()
            st.metric("最低净值", f"${min_val:,.2f}")
        with col3:
            # 计算最大回撤
            peak = np.maximum.accumulate(balance)
            drawdown = (peak - balance) / peak * 100
            max_drawdown = drawdown.max()
            st.metric("最大回撤", f"{max_drawdown:.1f}%")
    else:
        # 没有交易数据时显示空状态
        st.markdown("""
        <div style="
            text-align: center;
            padding: 60px 20px;
            background: rgba(255, 255, 255, 0.02);
            border: 2px dashed rgba(255, 255, 255, 0.1);
            border-radius: 16px;
            color: #718096;
        ">
            <div style="font-size: 48px; margin-bottom: 16px;">(・ω・)</div>
            <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">暂无交易数据</div>
            <div style="font-size: 13px;">启动 AI 竞技场后，交易数据将在这里显示</div>
        </div>
        """, unsafe_allow_html=True)
        
        # 显示空的统计
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("最高净值", "--")
        with col2:
            st.metric("最低净值", "--")
        with col3:
            st.metric("最大回撤", "--")


def _get_real_ai_stats(agent_name: str) -> Dict[str, Any]:
    """
    从数据库获取 AI 的真实统计数据
    
     使用 get_arena_real_data 统一数据源
    """
    # 使用统一的数据获取函数
    arena_data = get_arena_real_data()
    
    if agent_name in arena_data:
        data = arena_data[agent_name]
        return {
            'total_pnl': data.get('total_pnl_usd', 0),
            'win_rate': data.get('win_rate', 0),
            'total_trades': data.get('total_trades', 0),
            'streak': data.get('streak', 0)
        }
    
    # 回退到直接查询数据库
    try:
        from ai.ai_db_manager import get_ai_db_manager
        db = get_ai_db_manager()
        stats = db.get_agent_stats(agent_name)
        if stats:
            return {
                'total_pnl': stats.total_pnl or 0,
                'win_rate': (stats.win_rate or 0) * 100,
                'total_trades': stats.total_trades or 0,
                'streak': stats.current_streak or 0
            }
    except Exception:
        pass
    
    return {
        'total_pnl': 0,
        'win_rate': 0,
        'total_trades': 0,
        'streak': 0
    }


def _get_real_equity_curve(agent_name: str):
    """
    从数据库获取 AI 的真实资金曲线
    
    返回 DataFrame，即使没有交易也返回初始资金点
    """
    import pandas as pd
    from datetime import datetime, timedelta
    
    initial_balance = 10000  # 虚拟初始资金
    
    try:
        from ai.ai_db_manager import get_ai_db_manager
        db = get_ai_db_manager()
        
        # 获取已平仓的交易记录
        closed_positions = db.get_closed_positions(agent_name, limit=100)
        
        # 构建资金曲线
        equity_data = []
        current_balance = initial_balance
        
        if closed_positions:
            for pos in closed_positions:
                pnl = pos.get('pnl', 0) or 0
                current_balance += pnl
                
                # 解析时间（数据库存储的是毫秒时间戳）
                close_time = pos.get('close_time') or pos.get('exit_time')
                if close_time:
                    try:
                        if isinstance(close_time, (int, float)):
                            # 毫秒时间戳转换
                            ts = pd.to_datetime(close_time, unit='ms')
                        elif isinstance(close_time, str):
                            ts = pd.to_datetime(close_time)
                        else:
                            ts = close_time
                        equity_data.append({
                            'timestamp': ts,
                            'equity': current_balance
                        })
                    except Exception:
                        pass
        
        # 即使没有交易，也返回初始资金点
        if not equity_data:
            # 创建一个简单的初始资金曲线（过去 24 小时到现在）
            now = pd.Timestamp.now()
            equity_data = [
                {'timestamp': now - pd.Timedelta(hours=24), 'equity': initial_balance},
                {'timestamp': now, 'equity': initial_balance}
            ]
        
        df = pd.DataFrame(equity_data)
        df = df.sort_values('timestamp')
        
        # 添加初始点（如果有交易记录）
        if len(df) > 0 and len(closed_positions) > 0:
            first_ts = df['timestamp'].iloc[0] - pd.Timedelta(hours=1)
            df = pd.concat([
                pd.DataFrame([{'timestamp': first_ts, 'equity': initial_balance}]),
                df
            ], ignore_index=True)
        
        return df
        
    except Exception as e:
        # 出错时返回初始资金曲线
        now = pd.Timestamp.now()
        return pd.DataFrame([
            {'timestamp': now - pd.Timedelta(hours=24), 'equity': initial_balance},
            {'timestamp': now, 'equity': initial_balance}
        ])


def render_live_chart_tab(view_model: Dict, actions: Dict):
    """
    渲染 AI 决策 K 线 Tab
    
    显示 AI 入场信号（与主界面策略信号区分）
    使用 @st.fragment 实现局部刷新，避免全局刷新导致图表重置
    """
    # 获取冠军信号信息
    arena_data = get_arena_real_data()
    champion = next((d for d in arena_data.values() if d.get('rank') == 1), None)
    champion_name = next((name for name, d in arena_data.items() if d.get('rank') == 1), 'DeepSeek')
    ai_info = AI_MODELS.get(champion_name, {})
    display_name = ai_info.get('name', champion_name)
    
    # 顶部信息栏 + 询问 AI 按钮
    col_info, col_ask = st.columns([4, 1])
    
    with col_info:
        if champion:
            signal = champion.get('signal', 'WAIT')
            signal_color = '#00d4aa' if signal == 'BUY' else ('#ff6b6b' if signal == 'SELL' else '#feca57')
            st.markdown(f"""
            <div style="
                display: flex;
                align-items: center;
                gap: 12px;
                padding: 12px 16px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 8px;
            ">
                <span style="color: #718096;">AI 信号源:</span>
                <span style="color: {signal_color}; font-weight: 600;">
                    {display_name} ({signal})
                </span>
            </div>
            """, unsafe_allow_html=True)
    
    with col_ask:
        # 询问 AI 按钮
        st.button(
            "(・ω・) 询问 AI", 
            key="ask_ai_btn", 
            width="stretch",
            on_click=_show_ai_advisor_dialog
        )
    
    # 使用实时更新的 K 线图（与主界面一致）
    _render_ai_kline_chart_realtime(view_model, actions, arena_data)


def _render_ai_kline_chart_realtime(view_model: Dict, actions: Dict, arena_data: Dict):
    """
    AI 决策专用 K 线图 - 实时更新版本
    
    使用自定义 HTML 组件 + JavaScript 实现 TradingView 风格的实时更新
    与主界面 K 线图实现方式一致，特点：
    1. 使用 JavaScript 直接操作 Lightweight Charts API
    2. 增量更新数据，不重建图表
    3. 保持用户的缩放/拖动位置
    """
    import streamlit.components.v1 as components
    import json
    import os
    
    # 导入必要的模块
    try:
        from ui.ui_legacy import (
            _fetch_ohlcv_for_chart, 
            check_market_api_status,
            MARKET_API_URL
        )
    except ImportError as e:
        st.warning(f"无法加载图表组件: {e}")
        return
    
    BEIJING_OFFSET_SEC = 8 * 3600
    
    # 获取交易池
    symbols = st.session_state.get('auto_symbols', ['BTC/USDT:USDT'])
    if not symbols:
        st.info("请先在侧边栏配置交易池")
        return
    
    timeframes = ['1m', '3m', '5m', '15m', '30m', '1h', '4h', '1D']
    
    # 控制栏
    col_sym, col_tf, col_status = st.columns([3, 2, 1])
    with col_sym:
        selected_symbol = st.selectbox("币种", symbols, key="ai_kline_symbol")
    with col_tf:
        selected_tf = st.selectbox("周期", timeframes, index=2, key="ai_kline_tf")
    with col_status:
        api_status = check_market_api_status()
        if api_status:
            st.caption("(^_^) API 在线")
        else:
            st.caption("(・ω・) 直连模式")
    
    # 获取 K 线数据（1000 根）
    ohlcv_data = _fetch_ohlcv_for_chart(selected_symbol, selected_tf, limit=1000)
    
    if not ohlcv_data:
        st.warning("暂无 K 线数据")
        return
    
    # 转换数据格式
    candle_data = []
    volume_data = []
    
    for candle in ohlcv_data:
        ts_ms = candle[0]
        ts_sec = int(ts_ms / 1000) + BEIJING_OFFSET_SEC
        
        candle_data.append({
            "time": ts_sec,
            "open": float(candle[1]),
            "high": float(candle[2]),
            "low": float(candle[3]),
            "close": float(candle[4])
        })
        
        volume_data.append({
            "time": ts_sec,
            "value": float(candle[5]),
            "color": "#26a69a80" if float(candle[4]) >= float(candle[1]) else "#ef535080"
        })
    
    # 生成 AI 入场信号标记（只显示当前选择的币种）
    ai_markers = _generate_ai_signal_markers(candle_data, arena_data, selected_symbol)
    
    # 构建 API URL（用于实时更新）
    api_url = f"{MARKET_API_URL}/kline?symbol={selected_symbol}&tf={selected_tf}&limit=5"
    
    # 刷新间隔（秒）
    refresh_interval = 1
    
    # 生成自定义 HTML 组件
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <script src="https://unpkg.com/lightweight-charts@4.1.0/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 0; background: #131722; }}
            #chart {{ width: 100%; height: 480px; }}
            #status {{ 
                color: #d1d4dc; 
                font-size: 12px; 
                padding: 8px 12px; 
                background: #1e222d;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-top: 1px solid #363a45;
            }}
            .price-up {{ color: #26a69a; }}
            .price-down {{ color: #ef5350; }}
            .ai-signal {{ 
                display: inline-block;
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 11px;
                margin-left: 8px;
            }}
            .ai-signal.buy {{ background: rgba(0, 212, 170, 0.2); color: #00d4aa; }}
            .ai-signal.sell {{ background: rgba(255, 107, 107, 0.2); color: #ff6b6b; }}
        </style>
    </head>
    <body>
        <div id="chart"></div>
        <div id="status">
            <span id="price-info">(・ω・) 加载中...</span>
            <span id="update-time">--</span>
        </div>
        <script>
            // 初始化图表
            const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
                width: document.getElementById('chart').clientWidth,
                height: 480,
                layout: {{
                    background: {{ type: 'solid', color: '#131722' }},
                    textColor: '#d1d4dc'
                }},
                grid: {{
                    vertLines: {{ color: '#363a45' }},
                    horzLines: {{ color: '#363a45' }}
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal
                }},
                rightPriceScale: {{
                    borderColor: '#363a45',
                    scaleMargins: {{ top: 0.1, bottom: 0.2 }}
                }},
                timeScale: {{
                    borderColor: '#363a45',
                    timeVisible: true,
                    secondsVisible: false
                }}
            }});
            
            // 创建蜡烛图系列
            const candleSeries = chart.addCandlestickSeries({{
                upColor: '#26a69a',
                downColor: '#ef5350',
                borderUpColor: '#26a69a',
                borderDownColor: '#ef5350',
                wickUpColor: '#26a69a',
                wickDownColor: '#ef5350'
            }});
            
            // 创建成交量系列
            const volumeSeries = chart.addHistogramSeries({{
                priceFormat: {{ type: 'volume' }},
                priceScaleId: 'volume'
            }});
            volumeSeries.priceScale().applyOptions({{
                scaleMargins: {{ top: 0.8, bottom: 0 }}
            }});
            
            // 加载初始数据
            const initialCandles = {json.dumps(candle_data)};
            const initialVolumes = {json.dumps(volume_data)};
            const aiMarkers = {json.dumps(ai_markers)};
            
            candleSeries.setData(initialCandles);
            volumeSeries.setData(initialVolumes);
            
            // 设置 AI 信号标记
            if (aiMarkers && aiMarkers.length > 0) {{
                candleSeries.setMarkers(aiMarkers);
            }}
            
            // 自适应大小
            window.addEventListener('resize', () => {{
                chart.applyOptions({{ width: document.getElementById('chart').clientWidth }});
            }});
            
            // 统计 AI 信号
            const buyCount = aiMarkers.filter(m => m.text && m.text.includes('BUY')).length;
            const sellCount = aiMarkers.filter(m => m.text && m.text.includes('SELL')).length;
            
            // 更新状态栏
            function updateStatus(candle) {{
                const priceInfo = document.getElementById('price-info');
                const updateTime = document.getElementById('update-time');
                
                const price = candle.close.toLocaleString('en-US', {{style: 'currency', currency: 'USD'}});
                const firstPrice = initialCandles[0] ? initialCandles[0].open : candle.open;
                const change = ((candle.close / firstPrice - 1) * 100).toFixed(2);
                const changeClass = change >= 0 ? 'price-up' : 'price-down';
                const changeIcon = change >= 0 ? '(^_^)' : '(T_T)';
                
                let signalHtml = '';
                if (buyCount > 0) {{
                    signalHtml += `<span class="ai-signal buy">BUY x${{buyCount}}</span>`;
                }}
                if (sellCount > 0) {{
                    signalHtml += `<span class="ai-signal sell">SELL x${{sellCount}}</span>`;
                }}
                
                priceInfo.innerHTML = `${{price}} | <span class="${{changeClass}}">${{changeIcon}} ${{change}}%</span>${{signalHtml}}`;
                
                const now = new Date();
                updateTime.textContent = `(・ω・) ${{now.toLocaleTimeString()}}`;
            }}
            
            // 初始状态
            if (initialCandles.length > 0) {{
                updateStatus(initialCandles[initialCandles.length - 1]);
            }}
            
            //  实时更新函数
            async function fetchAndUpdate() {{
                try {{
                    const response = await fetch('{api_url}');
                    const result = await response.json();
                    
                    if (result.data && result.data.length > 0) {{
                        // 获取最新的几根K线
                        const newCandles = result.data.map(row => ({{
                            time: Math.floor(row[0] / 1000) + {BEIJING_OFFSET_SEC},
                            open: parseFloat(row[1]),
                            high: parseFloat(row[2]),
                            low: parseFloat(row[3]),
                            close: parseFloat(row[4])
                        }}));
                        
                        const newVolumes = result.data.map(row => ({{
                            time: Math.floor(row[0] / 1000) + {BEIJING_OFFSET_SEC},
                            value: parseFloat(row[5]),
                            color: parseFloat(row[4]) >= parseFloat(row[1]) ? '#26a69a80' : '#ef535080'
                        }}));
                        
                        //  增量更新：只更新最后一根K线
                        const latestCandle = newCandles[newCandles.length - 1];
                        const latestVolume = newVolumes[newVolumes.length - 1];
                        
                        candleSeries.update(latestCandle);
                        volumeSeries.update(latestVolume);
                        
                        updateStatus(latestCandle);
                    }}
                }} catch (e) {{
                    console.error('更新失败:', e);
                }}
            }}
            
            //  定时刷新（每5秒）
            setInterval(fetchAndUpdate, {refresh_interval * 1000});
        </script>
    </body>
    </html>
    '''
    
    # 渲染组件
    components.html(html_content, height=540)


def _generate_ai_signal_markers(candle_data: List[Dict], arena_data: Dict, selected_symbol: str = None) -> List[Dict]:
    """
    生成 AI 入场信号标记 - 从数据库读取真实交易记录
    
    从 ai_positions 表读取 AI 的历史开仓记录，在 K 线图上标记入场点
    
    参数:
        candle_data: K 线数据
        arena_data: 竞技场数据
        selected_symbol: 当前选择的币种（用于过滤，只显示该币种的信号）
    """
    markers = []
    
    if not candle_data or len(candle_data) < 10:
        return markers
    
    # 获取 K 线时间范围（用于过滤交易记录）
    first_candle_time = candle_data[0]['time']
    last_candle_time = candle_data[-1]['time']
    
    # 北京时间偏移（K 线数据已经加了偏移，需要还原）
    BEIJING_OFFSET_SEC = 8 * 3600
    
    try:
        from ai.ai_db_manager import get_ai_db_manager, get_db_connection
        import threading
        
        db = get_ai_db_manager()
        
        # 获取已启用的 AI 列表
        enabled_ais = list(arena_data.keys())
        
        for ai_id in enabled_ais:
            ai_info = AI_MODELS.get(ai_id, {})
            ai_name = ai_info.get('name', ai_id.title())
            
            # 获取该 AI 的所有持仓（包括已平仓）
            # 从 ai_positions 表读取
            with get_db_connection(db.db_path) as conn:
                cursor = conn.cursor()
                
                # 查询该 AI 在时间范围内的开仓记录
                # created_at 是毫秒时间戳
                start_ts_ms = (first_candle_time - BEIJING_OFFSET_SEC) * 1000
                end_ts_ms = (last_candle_time - BEIJING_OFFSET_SEC + 3600) * 1000  # 多加 1 小时容错
                
                # 如果指定了币种，只查询该币种的记录
                if selected_symbol:
                    cursor.execute("""
                        SELECT symbol, side, entry_price, created_at, qty, leverage
                        FROM ai_positions
                        WHERE agent_name = ? 
                          AND symbol = ?
                          AND created_at >= ?
                          AND created_at <= ?
                        ORDER BY created_at DESC
                        LIMIT 20
                    """, (ai_id, selected_symbol, start_ts_ms, end_ts_ms))
                else:
                    cursor.execute("""
                        SELECT symbol, side, entry_price, created_at, qty, leverage
                        FROM ai_positions
                        WHERE agent_name = ? 
                          AND created_at >= ?
                          AND created_at <= ?
                        ORDER BY created_at DESC
                        LIMIT 50
                    """, (ai_id, start_ts_ms, end_ts_ms))
                
                positions = cursor.fetchall()
            
            # 为每个开仓记录生成标记
            for pos in positions:
                symbol, side, entry_price, created_at_ms, qty, leverage = pos
                
                # 转换时间戳为 K 线时间格式（秒 + 北京时间偏移）
                trade_time_sec = int(created_at_ms / 1000) + BEIJING_OFFSET_SEC
                
                # 找到最接近的 K 线时间
                closest_candle_time = None
                min_diff = float('inf')
                for candle in candle_data:
                    diff = abs(candle['time'] - trade_time_sec)
                    if diff < min_diff:
                        min_diff = diff
                        closest_candle_time = candle['time']
                
                if closest_candle_time is None:
                    continue
                
                # 生成标记
                symbol_short = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                qty_display = f"${qty:.0f}" if qty else ""
                
                if side == 'long':
                    markers.append({
                        "time": closest_candle_time,
                        "position": "belowBar",
                        "shape": "arrowUp",
                        "color": "#00d4aa",
                        "text": f"LONG\n{ai_name}\n{qty_display}"
                    })
                elif side == 'short':
                    markers.append({
                        "time": closest_candle_time,
                        "position": "aboveBar",
                        "shape": "arrowDown",
                        "color": "#ff6b6b",
                        "text": f"SHORT\n{ai_name}\n{qty_display}"
                    })
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"[Arena] 获取 AI 交易记录失败: {e}")
        # 出错时返回空标记，不影响图表显示
    
    return markers


def render_ledger_tab(view_model: Dict, actions: Dict):
    """
    渲染交易账本 Tab
    
    显示 AI 发言记录 + 持仓和交易历史
    """
    import pandas as pd
    
    # ========== AI 发言记录（使用 fragment 实现静默刷新） ==========
    st.markdown("### (・ω・) AI 交易员发言")
    _render_ai_speech_fragment()
    
    st.divider()
    
    # ========== AI 虚拟账户概览 ==========
    # 使用 fragment 实现局部刷新
    _render_ai_accounts_fragment()
    
    st.divider()
    
    # ========== AI 虚拟持仓（竞技场模拟交易）==========
    # 使用 fragment 实现局部刷新，不触发整个页面刷新
    _render_ai_positions_fragment()
    
    st.divider()
    
    # ========== 真实账户持仓 ==========
    st.markdown("### ($.$) 真实账户持仓")
    
    open_positions = view_model.get('open_positions', {})
    if open_positions:
        pos_data = []
        for symbol, pos in open_positions.items():
            pos_data.append({
                "交易对": symbol,
                "方向": pos.get('side', '-'),
                "数量": f"${pos.get('size', 0):,.2f}",
                "入场价": f"${pos.get('entry_price', 0):,.2f}",
                "浮动盈亏": f"${pos.get('pnl', 0):,.2f}"
            })
        df_pos = pd.DataFrame(pos_data)
        st.dataframe(df_pos, width="stretch", hide_index=True)
    else:
        st.info("当前无持仓")


@st.fragment(run_every=30)
def _render_recent_decisions_fragment():
    """
    最近决策记录 Fragment - 每30秒静默刷新
    
    显示最近的 AI 决策记录列表
    """
    try:
        from ai.ai_db_manager import get_ai_db_manager
        from datetime import datetime, timezone, timedelta
        
        # 北京时区 (UTC+8)
        BEIJING_TZ = timezone(timedelta(hours=8))
        
        db = get_ai_db_manager()
        recent_decisions = db.get_latest_decisions(limit=10)
        
        if recent_decisions:
            for d in recent_decisions:
                # 信号颜色
                signal_color = "#00d4aa" if d.signal in ['open_long', 'BUY'] else (
                    "#ff6b6b" if d.signal in ['open_short', 'SELL'] else "#718096"
                )
                # 时间格式化（转换为北京时间）
                time_str = ""
                if d.created_at:
                    try:
                        if isinstance(d.created_at, str):
                            # 解析字符串时间
                            dt = datetime.fromisoformat(d.created_at.replace('Z', '+00:00'))
                            if dt.tzinfo is None:
                                # 假设是 UTC 时间，转换为北京时间
                                dt = dt.replace(tzinfo=timezone.utc)
                            dt_bj = dt.astimezone(BEIJING_TZ)
                            time_str = dt_bj.strftime('%H:%M')
                        else:
                            time_str = d.created_at.strftime('%H:%M')
                    except:
                        time_str = str(d.created_at).split(' ')[1][:5] if ' ' in str(d.created_at) else ""
                # 推理预览
                reason_preview = d.reasoning[:40] + "..." if d.reasoning and len(d.reasoning) > 40 else (d.reasoning or "-")
                
                st.markdown(f"""
                <div style="
                    padding: 6px 10px;
                    margin-bottom: 4px;
                    background: rgba(255,255,255,0.03);
                    border-radius: 6px;
                    font-size: 12px;
                ">
                    <span style="color: #888;">{time_str}</span>
                    <span style="color: #aaa; margin: 0 4px;">|</span>
                    <span style="font-weight: 600;">{d.agent_name}</span>
                    <span style="color: {signal_color}; margin-left: 6px;">{d.signal.upper()}</span>
                    <span style="color: #888; margin-left: 4px;">({d.confidence:.0f}%)</span>
                    <div style="color: #666; margin-top: 2px; font-size: 11px;">{reason_preview}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.caption("暂无决策记录")
    except Exception as e:
        st.caption(f"加载失败: {e}")


@st.fragment(run_every=30)
def _render_ai_speech_fragment():
    """
    AI 发言记录 Fragment - 每30秒静默刷新
    
    按轮次整合显示所有 AI 的分析，每轮用 expander 折叠
    """
    try:
        from ai.ai_db_manager import get_ai_db_manager
        from datetime import datetime, timezone, timedelta
        
        # 北京时区 (UTC+8)
        BEIJING_TZ = timezone(timedelta(hours=8))
        
        db = get_ai_db_manager()
        
        # 获取最近的决策记录
        decisions = db.get_latest_decisions(limit=100)
        
        if not decisions:
            st.info("暂无 AI 发言记录，等待 AI 分析...")
            return
        
        # 解析所有决策的时间
        parsed_decisions = []
        for d in decisions:
            created_at = d.created_at
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if created_at.tzinfo is None:
                        created_at = created_at.replace(tzinfo=timezone.utc)
                    created_at = created_at.astimezone(BEIJING_TZ)
                except:
                    created_at = datetime.now(BEIJING_TZ)
            elif created_at is not None:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                created_at = created_at.astimezone(BEIJING_TZ)
            else:
                created_at = datetime.now(BEIJING_TZ)
            parsed_decisions.append((d, created_at))
        
        # 按时间排序（最新的在前）
        parsed_decisions.sort(key=lambda x: x[1], reverse=True)
        
        # 按轮次分组（同一轮次内的决策时间差不超过 3 分钟）
        rounds = []  # [(round_time, {agent_name: [decisions]})]
        current_round = None
        current_round_time = None
        
        for d, dt in parsed_decisions:
            agent = d.agent_name
            
            # 判断是否属于当前轮次（时间差不超过 3 分钟）
            if current_round_time is None or (current_round_time - dt).total_seconds() > 180:
                # 开始新的一轮
                if current_round is not None:
                    rounds.append((current_round_time.strftime('%Y-%m-%d %H:%M'), current_round))
                current_round = {}
                current_round_time = dt
            
            if agent not in current_round:
                current_round[agent] = []
            current_round[agent].append(d)
        
        # 添加最后一轮
        if current_round is not None:
            rounds.append((current_round_time.strftime('%Y-%m-%d %H:%M'), current_round))
        
        # 只显示最近 5 轮
        for round_idx, (round_time, agents_data) in enumerate(rounds[:5]):
            # 统计这一轮的整体情况
            total_long = 0
            total_short = 0
            total_close = 0
            ai_count = len(agents_data)
            
            for agent, agent_decisions in agents_data.items():
                for d in agent_decisions:
                    if d.signal in ['open_long', 'BUY']:
                        total_long += 1
                    elif d.signal in ['open_short', 'SELL']:
                        total_short += 1
                    elif d.signal in ['close_long', 'close_short']:
                        total_close += 1
            
            # 构建轮次标题
            summary_parts = []
            if total_long > 0:
                summary_parts.append(f"🟢开多x{total_long}")
            if total_short > 0:
                summary_parts.append(f"🔴开空x{total_short}")
            if total_close > 0:
                summary_parts.append(f"📤平仓x{total_close}")
            if not summary_parts:
                summary_parts.append("⏳观望")
            
            summary = " | ".join(summary_parts)
            expander_title = f" 第{round_idx + 1}轮 [{round_time}] - {ai_count}个AI | {summary}"
            
            # 使用 expander 折叠显示
            with st.expander(expander_title, expanded=False):
                # 显示每个 AI 的分析
                for agent, agent_decisions in sorted(agents_data.items()):
                    ai_info = AI_MODELS.get(agent, {})
                    display_name = ai_info.get('name', agent.title())
                    
                    # 统计该 AI 的信号
                    signals = [d.signal for d in agent_decisions]
                    long_count = sum(1 for s in signals if s in ['open_long', 'BUY'])
                    short_count = sum(1 for s in signals if s in ['open_short', 'SELL'])
                    close_count = sum(1 for s in signals if s in ['close_long', 'close_short'])
                    hold_count = sum(1 for s in signals if s == 'hold')
                    
                    # 确定信号标签
                    if long_count > 0:
                        card_class = "long"
                        signal_tag = f"🟢 开多 x{long_count}"
                    elif short_count > 0:
                        card_class = "short"
                        signal_tag = f"🔴 开空 x{short_count}"
                    elif close_count > 0:
                        card_class = ""
                        signal_tag = f"📤 平仓 x{close_count}"
                    elif hold_count > 0:
                        card_class = ""
                        signal_tag = f"⏸️ 持有 x{hold_count}"
                    else:
                        card_class = ""
                        signal_tag = "⏳ 观望"
                    
                    # 构建发言内容
                    speech_parts = []
                    seen_symbols = set()
                    for d in agent_decisions[:5]:
                        symbol = d.symbol or '未知'
                        symbol_short = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
                        
                        if symbol_short in seen_symbols:
                            continue
                        seen_symbols.add(symbol_short)
                        
                        signal_emoji = "↑" if d.signal in ['open_long', 'BUY'] else "↓" if d.signal in ['open_short', 'SELL'] else "→"
                        reasoning = d.reasoning[:80] + "..." if d.reasoning and len(d.reasoning) > 80 else (d.reasoning or "无分析")
                        speech_parts.append(f"<b>{symbol_short}</b> ({signal_emoji}): {reasoning}")
                    
                    speech_content = "<br>".join(speech_parts) if speech_parts else "等待分析..."
                    
                    # 渲染 AI 发言卡片
                    st.markdown(f"""
                    <div class="ai-speech-card {card_class}">
                        <div class="ai-speech-header">
                            <span class="ai-speech-name">{display_name}</span>
                            <span class="ai-speech-tag">{signal_tag}</span>
                        </div>
                        <div class="ai-speech-content">{speech_content}</div>
                    </div>
                    """, unsafe_allow_html=True)
        
    except Exception as e:
        st.warning(f"获取 AI 发言失败: {e}")


@st.fragment(run_every=10)
def _render_arena_status_log():
    """
    AI 竞技场状态日志 Fragment - 每10秒自动刷新
    
    显示简单的 AI 执行状态（是否返回决策、是否下单）
    """
    try:
        from ai.ai_db_manager import get_ai_db_manager
        from datetime import datetime, timedelta
        
        db = get_ai_db_manager()
        
        # 获取最近 2 分钟内的决策（按 AI 分组）
        recent_decisions = db.get_latest_decisions(limit=50)
        
        if not recent_decisions:
            st.caption("⏳ 等待 AI 返回决策...")
            return
        
        # 按 AI 分组统计最近的决策
        ai_status = {}
        now = datetime.now()
        
        for d in recent_decisions:
            agent = d.agent_name
            if agent not in ai_status:
                ai_status[agent] = {
                    'has_decision': True,
                    'signal': d.signal,
                    'time': d.created_at
                }
        
        # 检查每个 AI 的持仓数量
        enabled_ais = ArenaDataInterface.get_enabled_ai_list()
        
        # 构建状态日志
        log_lines = []
        for ai_id in enabled_ais:
            ai_info = AI_MODELS.get(ai_id, {})
            name = ai_info.get('name', ai_id.title())
            
            # 检查是否有决策
            status = ai_status.get(ai_id)
            if status:
                signal = status['signal']
                if signal in ['open_long', 'open_short']:
                    icon = "🟢" if signal == 'open_long' else "🔴"
                    action = "开仓"
                elif signal in ['close_long', 'close_short']:
                    icon = "📤"
                    action = "平仓"
                elif signal in ['hold']:
                    icon = "⏸️"
                    action = "持有"
                else:
                    icon = "⏳"
                    action = "观望"
                log_lines.append(f"{icon} {name}: {action}")
            else:
                log_lines.append(f"⏳ {name}: 等待响应")
        
        # 获取持仓统计
        total_positions = 0
        for ai_id in enabled_ais:
            positions = db.get_open_positions(ai_id)
            total_positions += len(positions)
        
        # 显示状态
        st.markdown(f"""
        <div style="
            background: rgba(255,255,255,0.03);
            border-radius: 6px;
            padding: 8px 10px;
            font-size: 11px;
            color: #aaa;
            margin-bottom: 8px;
        ">
            <div style="margin-bottom: 4px; color: #888;"> AI 状态 | 总持仓: {total_positions}</div>
            {'<br>'.join(log_lines)}
        </div>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.caption(f"状态加载失败: {e}")


@st.fragment(run_every=30)
def _render_ai_accounts_fragment():
    """
    AI 虚拟账户 Fragment - 每30秒自动刷新
    
    显示所有 AI 的虚拟账户概览（初始资金、当前净值、ROI、胜率等）
    使用 get_arena_real_data() 作为统一数据源
    """
    import pandas as pd
    
    st.markdown("### AI 虚拟账户概览")
    
    # 初始资金
    INITIAL_BALANCE = 10000.0
    
    try:
        # 使用统一数据源
        arena_data = get_arena_real_data()
        
        if not arena_data:
            st.info("暂无 AI 账户数据，请先配置并启用 AI")
            return
        
        # 构建表格数据
        account_data = []
        for ai_id, data in arena_data.items():
            # 获取 AI 显示名称
            ai_info = AI_MODELS.get(ai_id, {})
            display_name = ai_info.get('name', ai_id.title())
            
            # 计算当前净值
            roi = data.get('roi', 0)
            total_pnl_usd = data.get('total_pnl_usd', 0)
            unrealized_pnl = data.get('unrealized_pnl', 0)
            total_pnl = total_pnl_usd + unrealized_pnl
            current_balance = INITIAL_BALANCE + total_pnl
            
            # 胜率和交易次数
            win_rate = data.get('win_rate', 0)
            total_trades = data.get('total_trades', 0)
            
            # 排名
            rank = data.get('rank', 0)
            rank_display = f"🥇 #{rank}" if rank == 1 else f"🥈 #{rank}" if rank == 2 else f"🥉 #{rank}" if rank == 3 else f"#{rank}"
            
            # ROI 显示（带颜色标记）
            roi_display = f"+{roi:.2f}%" if roi > 0 else f"{roi:.2f}%"
            
            # 状态
            signal = data.get('signal', 'WAIT')
            if signal in ['open_long', 'BUY']:
                status = "🟢 做多中"
            elif signal in ['open_short', 'SELL']:
                status = "🔴 做空中"
            else:
                status = "⚪ 观望"
            
            account_data.append({
                "排名": rank_display,
                "AI": display_name,
                "初始资金": f"${INITIAL_BALANCE:,.0f}",
                "当前净值": f"${current_balance:,.2f}",
                "ROI": roi_display,
                "胜率": f"{win_rate}%",
                "交易次数": total_trades,
                "状态": status
            })
        
        # 按排名排序
        account_data.sort(key=lambda x: int(x["排名"].replace("🥇 #", "").replace("🥈 #", "").replace("🥉 #", "").replace("#", "")))
        
        if account_data:
            df_accounts = pd.DataFrame(account_data)
            st.dataframe(df_accounts, width="stretch", hide_index=True)
            
            # 统计信息
            total_ais = len(account_data)
            profitable_ais = sum(1 for d in arena_data.values() if d.get('roi', 0) > 0)
            st.caption(f" 共 {total_ais} 个 AI | 盈利: {profitable_ais} | 亏损: {total_ais - profitable_ais}")
        else:
            st.info("暂无 AI 账户数据")
            
    except Exception as e:
        st.warning(f"获取 AI 账户数据失败: {e}")


@st.fragment(run_every=10)
def _render_ai_positions_fragment():
    """
    AI 虚拟持仓 Fragment - 每10秒自动刷新
    
    只刷新持仓表格，不触发整个页面刷新
    """
    import pandas as pd
    
    st.markdown("### 🎮 AI 虚拟持仓（竞技场）")
    
    try:
        from ai.ai_db_manager import get_ai_db_manager
        from ai.ai_indicators import get_data_source
        
        db = get_ai_db_manager()
        data_source = get_data_source()
        
        # 获取所有 AI 的持仓
        all_ai_positions = []
        enabled_ais = ArenaDataInterface.get_enabled_ai_list()
        
        # 获取当前价格缓存
        price_cache = {}
        
        for ai_id in enabled_ais:
            positions = db.get_open_positions(ai_id)
            for pos in positions:
                symbol = pos.get('symbol', '')
                entry_price = pos.get('entry_price', 0)
                qty = pos.get('qty', 0)  # qty 是 USD 仓位金额
                side = pos.get('side', 'long')
                leverage = pos.get('leverage', 1)
                
                # 获取当前价格（带缓存）
                if symbol not in price_cache:
                    try:
                        ohlcv = data_source.fetch_ohlcv(symbol, '1m', 1)
                        price_cache[symbol] = ohlcv[-1][4] if ohlcv else entry_price
                    except:
                        price_cache[symbol] = entry_price
                
                current_price = price_cache.get(symbol, entry_price)
                
                # 修复盈亏计算公式
                # qty 是 USD 仓位金额，盈亏 = 价格变化百分比 * 仓位 * 杠杆
                if entry_price > 0:
                    price_change_pct = (current_price - entry_price) / entry_price
                    if side == 'long':
                        pnl = price_change_pct * qty * leverage
                    else:  # short
                        pnl = -price_change_pct * qty * leverage
                    # 盈亏百分比 = 盈亏 / 仓位 * 100
                    pnl_pct = (pnl / qty) * 100 if qty > 0 else 0
                else:
                    pnl = 0
                    pnl_pct = 0
                
                # AI 显示名称
                ai_info = AI_MODELS.get(ai_id, {})
                display_name = ai_info.get('name', ai_id.title())
                
                # 方向显示
                side_display = "🟢 多" if side == 'long' else "🔴 空"
                
                all_ai_positions.append({
                    "AI": display_name,
                    "交易对": symbol.replace('/USDT:USDT', ''),
                    "方向": side_display,
                    "仓位": f"${qty:,.0f}",
                    "杠杆": f"{leverage}x",
                    "入场价": f"${entry_price:,.2f}",
                    "当前价": f"${current_price:,.2f}",
                    "浮动盈亏": f"${pnl:,.2f}",
                    "盈亏%": f"{'+' if pnl_pct > 0 else ''}{pnl_pct:.2f}%"
                })
        
        if all_ai_positions:
            df_ai_pos = pd.DataFrame(all_ai_positions)
            st.dataframe(df_ai_pos, width="stretch", hide_index=True)
            
            # 统计信息
            total_long = sum(1 for p in all_ai_positions if "多" in p["方向"])
            total_short = sum(1 for p in all_ai_positions if "空" in p["方向"])
            st.caption(f" 共 {len(all_ai_positions)} 个持仓 | 🟢 多: {total_long} | 🔴 空: {total_short}")
        else:
            st.info("AI 暂无虚拟持仓")
    except Exception as e:
        st.warning(f"获取 AI 持仓失败: {e}")


# ============ 主渲染函数 ============

def _restore_scheduler_if_needed():
    """
    检查并恢复调度器状态（UI 重启后自动恢复）
    
    从数据库读取持久化的调度器状态，如果之前是启用的，自动重启调度器
    
    安全检查：
    1. 避免重复恢复（session_state 标记）
    2. 检查调度器是否已在运行
    3. 验证 API Keys 有效性
    """
    # 避免重复恢复 - 使用更持久的标记
    restore_key = '_scheduler_restore_checked'
    if st.session_state.get(restore_key, False):
        return
    
    # 标记已检查，避免重复执行
    st.session_state[restore_key] = True
    
    try:
        from ai.ai_config_manager import get_ai_config_manager
        from ai.arena_scheduler import is_scheduler_running, start_background_scheduler, get_scheduler, stop_scheduler
        
        # 从数据库读取持久化状态
        config_mgr = get_ai_config_manager()
        state = config_mgr.get_scheduler_state()
        db_enabled = state.get('enabled', False)
        
        # 如果调度器正在运行
        if is_scheduler_running():
            # 检查数据库状态：如果数据库显示已禁用，则停止调度器
            if not db_enabled:
                stop_scheduler()
                st.session_state.arena_scheduler_running = False
                st.session_state.ai_takeover_live = False
                return
            
            # 数据库显示启用，同步状态
            st.session_state.arena_scheduler_running = True
            # 同步调度器配置到 session_state
            scheduler = get_scheduler()
            if scheduler:
                st.session_state.ai_timeframes = scheduler.timeframes
                st.session_state.auto_symbols = scheduler.symbols
                st.session_state.arena_selected_ais = scheduler.agents
                st.session_state.ai_takeover_live = scheduler.ai_takeover
            return
        
        # 调度器未运行，检查是否需要恢复
        if not db_enabled:
            return
        
        # 检查状态是否过期（超过 24 小时不自动恢复）
        last_updated = state.get('last_updated', '')
        if last_updated:
            try:
                from datetime import datetime, timedelta
                last_time = datetime.fromisoformat(last_updated)
                if datetime.now() - last_time > timedelta(hours=24):
                    # 状态过期，清除并不恢复
                    config_mgr.clear_scheduler_state()
                    return
            except Exception:
                pass
        
        # 获取 API Keys
        api_configs = ArenaDataInterface.get_ai_api_configs()
        api_keys = {
            ai_id: config.get('api_key', '')
            for ai_id, config in api_configs.items()
            if config.get('enabled') and config.get('api_key')
        }
        
        # 恢复调度器
        agents = state.get('agents', [])
        # 过滤出有效的 agents（必须有 API Key）
        valid_agents = [a for a in agents if a in api_keys]
        
        if valid_agents and api_keys:
            # 再次检查调度器是否已在运行（防止并发）
            if is_scheduler_running():
                st.session_state.arena_scheduler_running = True
                return
            
            start_background_scheduler(
                symbols=state.get('symbols', ['BTC/USDT:USDT']),
                timeframes=state.get('timeframes', ['5m']),
                agents=valid_agents,
                api_keys=api_keys,
                user_prompt=state.get('user_prompt', ''),
                ai_takeover=state.get('ai_takeover', False)
            )
            st.session_state.arena_scheduler_running = True
            st.session_state.ai_takeover_live = state.get('ai_takeover', False)
            # 恢复 session_state 中的配置
            st.session_state.ai_timeframes = state.get('timeframes', ['5m'])
            st.session_state.auto_symbols = state.get('symbols', ['BTC/USDT:USDT'])
            st.session_state.arena_selected_ais = valid_agents  # 恢复选中的 AI
            st.toast("(๑•̀ㅂ•́)و AI 竞技场已自动恢复")
        
        st.session_state._scheduler_restored = True
    except Exception as e:
        st.session_state._scheduler_restored = True
        # 静默失败，不影响 UI
        import logging
        logging.getLogger(__name__).debug(f"[Arena] 恢复调度器失败: {e}")


def render_arena_main(view_model: Dict, actions: Dict):
    """
    NOFX Arena 主渲染函数
    
    使用侧边栏 + 主区域布局（与主界面一致）
    """
    # 注入样式
    render_arena_styles()
    
    # 检查并恢复调度器状态（UI 重启后自动恢复）
    _restore_scheduler_if_needed()
    
    # 渲染入场动画（首次进入时）
    render_intro_animation()
    
    # 获取 Arena 数据
    arena_data = get_arena_mock_data()
    
    # ========== 侧边栏：控制面板 ==========
    with st.sidebar:
        # 注入粉色按钮样式（与主界面一致）
        st.markdown("""
        <style>
        /* 经典模式按钮 - 粉色渐变风格 */
        div[data-testid="stButton"] > button[kind="primary"] {
            background: linear-gradient(135deg, #ff6b9d 0%, #c44569 50%, #ff6b9d 100%) !important;
            background-size: 200% 200% !important;
            animation: pinkGradientArena 3s ease infinite !important;
            border: none !important;
            border-radius: 12px !important;
            padding: 12px 16px !important;
            color: white !important;
            font-weight: 600 !important;
            letter-spacing: 1px !important;
            box-shadow: 0 4px 20px rgba(255, 107, 157, 0.4) !important;
            transition: all 0.3s ease !important;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 25px rgba(255, 107, 157, 0.6) !important;
        }
        @keyframes pinkGradientArena {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        </style>
        """, unsafe_allow_html=True)
        
        # 切换回经典模式按钮
        if st.button("经典模式", key="arena_back_to_classic", width="stretch", type="primary"):
            st.session_state.arena_mode = False
            st.rerun()
        
        # 按钮下方注释
        st.markdown("""
        <div style="
            text-align: center;
            margin-top: -8px;
            margin-bottom: 12px;
        ">
            <span style="color: #718096; font-size: 11px;">点击后切换为经典交易</span>
        </div>
        """, unsafe_allow_html=True)
        
        # ============ 资产看板（与主界面一致的粉色渐变） ============
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 10px 16px;
            border-radius: 10px;
            margin-bottom: 12px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <span style="color: white; font-size: 16px; font-weight: 600;">✦ 资产看板</span>
        </div>
        """, unsafe_allow_html=True)
        
        # 根据运行模式显示不同的余额（与主界面一致）
        current_env_mode = st.session_state.get('env_mode', '● 实盘')
        
        if current_env_mode == "○ 测试":
            # 测试模式: 显示模拟账户余额
            paper_balance = view_model.get('paper_balance', {})
            if paper_balance and paper_balance.get('equity'):
                equity_val = paper_balance.get('equity', 208)
                equity_str = f"${equity_val:,.2f}"
                # 计算浮动盈亏
                wallet_balance = paper_balance.get('wallet_balance', 0) or 0
                unrealized_pnl = paper_balance.get('unrealized_pnl', 0) or 0
                if wallet_balance > 0 and unrealized_pnl != 0:
                    pnl_pct = (unrealized_pnl / wallet_balance) * 100
                    delta_str = f"{unrealized_pnl:+.2f} ({pnl_pct:+.1f}%)"
                else:
                    delta_str = None
            else:
                equity_str = "$208.00"
                delta_str = None
            
            st.metric("模拟净值(USDT)", equity_str, delta=delta_str)
            st.caption("模拟账户余额(非真实资金)")
        else:
            # 实盘模式: 显示 OKX 真实余额
            live_balance = st.session_state.get('live_balance', {})
            if live_balance and live_balance.get('equity'):
                equity = live_balance.get('equity', 0)
                equity_str = f"${equity:,.2f}"
            else:
                equity_str = view_model.get("equity", "----")
            
            st.metric("账户净值(USDT)", equity_str)
            st.caption("OKX 真实账户余额")
        
        st.divider()
        
        # ============ AI 接管交易 ============
        render_ai_takeover_section()
        
        st.divider()
        
        # ============ AI API 配置 ============
        render_ai_api_config_section()
        
        st.divider()
        
        # ============ 交易池配置（与主界面同步） ============
        render_trading_pool_section(actions)
        
        st.divider()
        
        # ============ AI 风格设置（与主界面一致的粉色渐变） ============
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            padding: 8px 14px;
            border-radius: 8px;
            margin-bottom: 12px;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        ">
            <span style="color: white; font-size: 14px; font-weight: 600;">◈ AI 风格设置</span>
        </div>
        """, unsafe_allow_html=True)
        
        # AI 提示词编辑区（简化版）
        ai_enabled = render_command_center()
    
    # ========== 主区域：竞技场 ==========
    # 顶部：AI 竞技场（使用 fragment 实现局部刷新）
    st.markdown("### AI 竞技场")
    _render_arena_section_fragment(ai_enabled)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 中部：多维数据视窗
    tab1, tab2, tab3 = st.tabs([
        "冠军视野",
        "实时 K 线",
        "交易账本"
    ])
    
    with tab1:
        # 冠军视野 - 不使用自动刷新整个 tab
        arena_data = get_arena_real_data()
        render_champion_view(arena_data)
    
    with tab2:
        # K 线图使用 fragment（在 render_live_chart_tab 内部）
        render_live_chart_tab(view_model, actions)
    
    with tab3:
        # 交易账本 - 不使用自动刷新，AI 虚拟持仓部分有自己的 fragment
        render_ledger_tab(view_model, actions)


@st.fragment(run_every=30)
def _render_arena_section_fragment(ai_enabled: bool):
    """
    AI 竞技场卡片 Fragment - 每30秒自动刷新
    
    只刷新 AI 卡片区域，不影响 K 线图
    """
    arena_data = get_arena_real_data()
    render_arena_section(arena_data, ai_enabled)


# ============ 入口函数 ============

def render_main_with_arena(view_model: Dict, actions: Dict):
    """
    带 Arena 模式的主渲染入口
    
    可通过 session_state 切换传统模式和 Arena 模式
    """
    # 检查是否启用 Arena 模式
    arena_mode = st.session_state.get('arena_mode', False)
    
    # 顶部模式切换
    col1, col2, col3 = st.columns([2, 1, 1])
    with col3:
        if st.button("(・∀・) 切换 Arena 模式" if not arena_mode else "(・ω・) 切换经典模式"):
            st.session_state.arena_mode = not arena_mode
            st.rerun()
    
    if arena_mode:
        render_arena_main(view_model, actions)
    else:
        # 调用原有的 render_main
        try:
            from ui.ui_legacy import render_main
            render_main(view_model, actions)
        except ImportError:
            st.error("无法加载经典 UI 模块")


# ============================================================================
# 询问 AI 交易员功能 - 微信聊天风格
# ============================================================================

@st.dialog("AI 交易顾问", width="large")
def _show_ai_advisor_dialog():
    """
    AI 交易顾问 - 微信聊天风格
    
    支持选择不同的 AI 服务商
    """
    from datetime import datetime
    
    # 获取当前选择的币种和周期（与 K 线图选择器同步）
    selected_symbol = st.session_state.get('ai_kline_symbol', 'BTC/USDT:USDT')
    selected_tf = st.session_state.get('ai_kline_tf', '5m')
    
    # 简化币种显示名称
    symbol_short = selected_symbol.replace('/USDT:USDT', '').replace('/USDT', '')
    
    # 初始化聊天历史
    if 'advisor_chat_history' not in st.session_state:
        st.session_state.advisor_chat_history = []
    if 'advisor_analyzing' not in st.session_state:
        st.session_state.advisor_analyzing = False
    
    # 获取已配置的 AI 列表
    available_ais = _get_available_ais_for_advisor()
    current_ai = st.session_state.get('advisor_selected_ai', 'deepseek')
    current_ai_name = "DeepSeek"
    
    # 找到当前 AI 的显示名称
    for ai in available_ais:
        if ai['id'] == current_ai:
            current_ai_name = ai['name']
            break
    
    # 顶部信息栏 - 显示当前分析的币种和 AI 选择
    col_info, col_ai = st.columns([3, 2])
    
    with col_info:
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            border-radius: 12px;
            padding: 12px 16px;
            border: 1px solid rgba(74, 163, 255, 0.3);
        ">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <span style="color: #4aa3ff; font-size: 18px; font-weight: 600;">{symbol_short}</span>
                    <span style="color: #718096; font-size: 14px; margin-left: 8px;">{selected_tf} 周期</span>
                </div>
                <div style="color: #38e6a6; font-size: 12px;">
                    (・ω・) {current_ai_name} 在线
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col_ai:
        # AI 选择器
        if available_ais:
            ai_options = [ai['name'] for ai in available_ais]
            ai_ids = [ai['id'] for ai in available_ais]
            
            try:
                default_idx = ai_ids.index(current_ai) if current_ai in ai_ids else 0
            except:
                default_idx = 0
            
            selected_idx = st.selectbox(
                "选择 AI",
                range(len(ai_options)),
                index=default_idx,
                format_func=lambda x: ai_options[x],
                key="advisor_ai_selector",
                label_visibility="collapsed"
            )
            st.session_state.advisor_selected_ai = ai_ids[selected_idx]
        else:
            st.warning("请先配置 AI API")
    
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    
    # 聊天区域容器
    chat_container = st.container(height=400)
    
    with chat_container:
        # 显示聊天历史
        if not st.session_state.advisor_chat_history:
            # 初始欢迎消息
            st.markdown(f"""
            <div style="display: flex; margin-bottom: 16px;">
                <div style="
                    background: rgba(74, 163, 255, 0.15);
                    border: 1px solid rgba(74, 163, 255, 0.3);
                    border-radius: 12px 12px 12px 0;
                    padding: 12px 16px;
                    max-width: 85%;
                    color: #e2e8f0;
                    font-size: 14px;
                    line-height: 1.6;
                ">
                    <div style="color: #4aa3ff; font-size: 12px; margin-bottom: 6px;">{current_ai_name}</div>
                    (｡･ω･｡) 你好！我是 {current_ai_name} 交易顾问。<br><br>
                    当前选择: <span style="color: #ffd34d; font-weight: 600;">{symbol_short}</span> {selected_tf} 周期<br><br>
                    点击下方「分析行情」按钮，我会帮你分析当前市场走势并给出交易建议。
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # 显示历史消息
            for msg in st.session_state.advisor_chat_history:
                if msg['role'] == 'user':
                    # 用户消息（右侧）
                    st.markdown(f"""
                    <div style="display: flex; justify-content: flex-end; margin-bottom: 16px;">
                        <div style="
                            background: linear-gradient(135deg, #38e6a6 0%, #2dd4bf 100%);
                            border-radius: 12px 12px 0 12px;
                            padding: 12px 16px;
                            max-width: 70%;
                            color: #1a1a2e;
                            font-size: 14px;
                        ">
                            {msg['content']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    # AI 消息（左侧）
                    st.markdown(f"""
                    <div style="display: flex; margin-bottom: 16px;">
                        <div style="
                            background: rgba(74, 163, 255, 0.15);
                            border: 1px solid rgba(74, 163, 255, 0.3);
                            border-radius: 12px 12px 12px 0;
                            padding: 12px 16px;
                            max-width: 85%;
                            color: #e2e8f0;
                            font-size: 14px;
                            line-height: 1.6;
                        ">
                            <div style="color: #4aa3ff; font-size: 12px; margin-bottom: 6px;">DeepSeek</div>
                            {msg['content']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # 底部按钮区域
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        analyze_clicked = st.button(
            f"(・∀・) 分析 {symbol_short} 行情",
            key="advisor_analyze_btn",
            disabled=st.session_state.advisor_analyzing
        )
    
    with col2:
        if st.button("(・_・) 清空对话", key="advisor_clear_btn"):
            st.session_state.advisor_chat_history = []
            st.rerun()
    
    with col3:
        if st.button("关闭", key="advisor_close_btn"):
            st.rerun()
    
    # 执行分析
    if analyze_clicked:
        # 执行 AI 分析（使用独立的宽松提示词）
        with st.spinner(f"(・ω・) 正在分析 {symbol_short}..."):
            result = _perform_advisor_analysis(selected_symbol, selected_tf)
        
        # 构建 AI 回复
        if result and not result.get('error'):
            signal = result.get('signal', 'wait')
            confidence = result.get('confidence', 0)
            reasoning = result.get('reasoning', '暂无分析')
            entry = result.get('entry_price', 0)
            sl = result.get('stop_loss', 0)
            tp = result.get('take_profit', 0)
            
            # 信号文字和颜色
            if signal in ['BUY', 'open_long']:
                signal_text = "做多 LONG"
                signal_color = "#38e6a6"
                signal_emoji = "(๑•̀ㅂ•́)و✧"
            elif signal in ['SELL', 'open_short']:
                signal_text = "做空 SHORT"
                signal_color = "#ff5b6b"
                signal_emoji = "(╯°□°)╯"
            else:
                signal_text = "观望 WAIT"
                signal_color = "#ffd34d"
                signal_emoji = "(・ω・)"
            
            # 计算盈亏比
            rr = 0
            if sl and tp and entry:
                if signal in ['BUY', 'open_long']:
                    risk = entry - sl if entry > sl else 0.01
                    reward = tp - entry
                else:
                    risk = sl - entry if sl > entry else 0.01
                    reward = entry - tp
                rr = reward / risk if risk > 0 else 0
            
            # 显示结果卡片
            st.success(f"{signal_emoji} 分析完成")
            
            # 信号和点位
            st.markdown(f"""
            <div style="background: rgba(0,0,0,0.3); border-radius: 12px; padding: 16px; margin: 10px 0;">
                <div style="font-size: 20px; font-weight: bold; color: {signal_color}; margin-bottom: 12px;">
                    {signal_text}
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px;">
                    <div>入场: <b>${entry:,.2f}</b></div>
                    <div>置信度: <b>{confidence}%</b></div>
                    <div>止损: <span style="color: #ff5b6b;"><b>${sl:,.2f}</b></span></div>
                    <div>止盈: <span style="color: #38e6a6;"><b>${tp:,.2f}</b></span></div>
                    <div>盈亏比: <b>1:{rr:.1f}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # 分析理由
            st.markdown(f"**分析理由:** {reasoning}")
            
        else:
            error_msg = result.get('error', '未知错误') if result else '分析失败'
            st.error(f"(；′⌒`) 分析出错: {error_msg}")


def _get_available_ais_for_advisor():
    """获取可用于 AI 顾问的 AI 列表（包含用户配置的模型）"""
    try:
        # 从配置管理器获取已配置的 AI
        from ai.ai_config_manager import get_ai_config_manager
        config_mgr = get_ai_config_manager()
        configs = config_mgr.get_all_ai_api_configs()
        
        available = []
        ai_names = {
            "deepseek": "DeepSeek",
            "qwen": "通义千问",
            "openai": "GPT",
            "claude": "Claude",
            "perplexity": "Perplexity",
            "spark_lite": "讯飞星火",
            "spark": "讯飞星火",
            "hunyuan": "腾讯混元",
            "glm": "智谱 GLM",
            "doubao": "火山豆包"
        }
        
        # 默认模型映射
        default_models = {
            "deepseek": "deepseek-chat",
            "qwen": "qwen-max",
            "spark": "lite",
            "spark_lite": "lite",
            "hunyuan": "hunyuan-lite",
            "glm": "glm-4-flash",
            "doubao": "doubao-pro-4k",
            "perplexity": "llama-3.1-sonar-small-128k-online",
            "openai": "gpt-4o-mini",
            "claude": "claude-3-haiku-20240307",
        }
        
        for ai_id, config in configs.items():
            if config.get('api_key'):
                # 使用用户配置的模型，如果没有则使用默认模型
                user_model = config.get('model', '') or default_models.get(ai_id, '')
                available.append({
                    "id": ai_id,
                    "name": ai_names.get(ai_id, ai_id),
                    "api_key": config.get('api_key'),
                    "model": user_model,  # 用户配置的模型
                    "verified": config.get('verified', False)
                })
        return available
    except Exception as e:
        print(f"[_get_available_ais_for_advisor] 错误: {e}")
        return []


def _calculate_price_structure(ohlcv: list, indicators: dict) -> str:
    """
    计算价格结构信息，帮助 AI 判断入场点位
    
    使用更精准的方法：
    1. Swing High/Low 识别局部高低点
    2. 斐波那契回撤位
    3. 价格密集区（成交量加权）
    4. 布林带和均线
    """
    if not ohlcv or len(ohlcv) < 50:
        return "数据不足"
    
    # 提取价格数据
    closes = [k[4] for k in ohlcv]
    highs = [k[2] for k in ohlcv]
    lows = [k[3] for k in ohlcv]
    volumes = [k[5] for k in ohlcv]
    
    current_price = closes[-1]
    
    # ========== 1. Swing High/Low 识别 ==========
    def find_swing_points(prices_high, prices_low, lookback=5):
        """识别局部高低点（Swing High/Low）"""
        swing_highs = []
        swing_lows = []
        
        for i in range(lookback, len(prices_high) - lookback):
            # Swing High: 当前高点比前后 lookback 根 K 线都高
            is_swing_high = all(prices_high[i] >= prices_high[i-j] for j in range(1, lookback+1)) and \
                           all(prices_high[i] >= prices_high[i+j] for j in range(1, lookback+1))
            if is_swing_high:
                swing_highs.append(prices_high[i])
            
            # Swing Low: 当前低点比前后 lookback 根 K 线都低
            is_swing_low = all(prices_low[i] <= prices_low[i-j] for j in range(1, lookback+1)) and \
                          all(prices_low[i] <= prices_low[i+j] for j in range(1, lookback+1))
            if is_swing_low:
                swing_lows.append(prices_low[i])
        
        return swing_highs, swing_lows
    
    swing_highs, swing_lows = find_swing_points(highs, lows, lookback=3)
    
    # 筛选当前价格附近的关键位（上方阻力、下方支撑）
    resistances = sorted([h for h in swing_highs if h > current_price])[:3]  # 最近3个阻力
    supports = sorted([l for l in swing_lows if l < current_price], reverse=True)[:3]  # 最近3个支撑
    
    # ========== 2. 斐波那契回撤位 ==========
    # 使用近期最高最低点计算
    recent_high = max(highs[-100:])
    recent_low = min(lows[-100:])
    fib_range = recent_high - recent_low
    
    # 判断趋势方向（用于确定斐波那契方向）
    is_uptrend = closes[-1] > closes[-50] if len(closes) >= 50 else True
    
    if is_uptrend:
        # 上涨趋势：从低点向高点画斐波那契
        fib_236 = recent_low + fib_range * 0.236
        fib_382 = recent_low + fib_range * 0.382
        fib_500 = recent_low + fib_range * 0.500
        fib_618 = recent_low + fib_range * 0.618
        fib_786 = recent_low + fib_range * 0.786
    else:
        # 下跌趋势：从高点向低点画斐波那契
        fib_236 = recent_high - fib_range * 0.236
        fib_382 = recent_high - fib_range * 0.382
        fib_500 = recent_high - fib_range * 0.500
        fib_618 = recent_high - fib_range * 0.618
        fib_786 = recent_high - fib_range * 0.786
    
    # ========== 3. 价格密集区（成交量加权） ==========
    def find_volume_clusters(closes, volumes, num_bins=20):
        """找出成交量密集的价格区间"""
        if not closes or not volumes:
            return []
        
        price_min, price_max = min(closes), max(closes)
        if price_max == price_min:
            return []
        
        bin_size = (price_max - price_min) / num_bins
        volume_profile = {}
        
        for price, vol in zip(closes, volumes):
            bin_idx = int((price - price_min) / bin_size)
            bin_idx = min(bin_idx, num_bins - 1)
            bin_price = price_min + (bin_idx + 0.5) * bin_size
            volume_profile[bin_price] = volume_profile.get(bin_price, 0) + vol
        
        # 按成交量排序，取前3个密集区
        sorted_levels = sorted(volume_profile.items(), key=lambda x: x[1], reverse=True)[:3]
        return [level[0] for level in sorted_levels]
    
    volume_clusters = find_volume_clusters(closes[-200:], volumes[-200:])
    
    # ========== 4. 布林带和均线 ==========
    boll_upper = indicators.get('BOLL_upper', current_price * 1.02)
    boll_middle = indicators.get('BOLL_middle', current_price)
    boll_lower = indicators.get('BOLL_lower', current_price * 0.98)
    
    ma20 = indicators.get('MA_20', current_price)
    ma50 = indicators.get('MA_50', current_price)
    ema12 = indicators.get('EMA_12', current_price)
    ema26 = indicators.get('EMA_26', current_price)
    
    # ========== 5. 价格位置分析 ==========
    price_vs_ma20 = "上方" if current_price > ma20 else "下方"
    price_vs_boll_mid = "上方" if current_price > boll_middle else "下方"
    trend_text = "上涨趋势" if is_uptrend else "下跌趋势"
    
    # 近期走势
    recent_5_closes = closes[-5:]
    trend_pct = ((recent_5_closes[-1] - recent_5_closes[0]) / recent_5_closes[0]) * 100
    
    # ========== 构建价格结构文本 ==========
    structure_text = f"""### 当前状态
- 当前价格: {current_price:.2f}
- 趋势判断: {trend_text}
- 近5根K线: {'上涨' if trend_pct > 0 else '下跌'} {abs(trend_pct):.2f}%

### Swing 支撑阻力位（局部高低点）
- 阻力位: {', '.join([f'{r:.2f}' for r in resistances]) if resistances else '暂无明显阻力'}
- 支撑位: {', '.join([f'{s:.2f}' for s in supports]) if supports else '暂无明显支撑'}

### 斐波那契回撤位（近100根K线）
- 近期最高: {recent_high:.2f}
- 近期最低: {recent_low:.2f}
- Fib 23.6%: {fib_236:.2f}
- Fib 38.2%: {fib_382:.2f}
- Fib 50.0%: {fib_500:.2f}
- Fib 61.8%: {fib_618:.2f}
- Fib 78.6%: {fib_786:.2f}

### 成交量密集区（潜在支撑阻力）
{chr(10).join([f'- {v:.2f}' for v in volume_clusters]) if volume_clusters else '- 暂无明显密集区'}

### 布林带
- 上轨: {boll_upper:.2f}
- 中轨: {boll_middle:.2f} (价格在其{price_vs_boll_mid})
- 下轨: {boll_lower:.2f}

### 均线
- MA20: {ma20:.2f} (价格在其{price_vs_ma20})
- MA50: {ma50:.2f}
- EMA12: {ema12:.2f}
- EMA26: {ema26:.2f}"""
    
    return structure_text


def _perform_advisor_analysis(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    AI 顾问分析（独立模块，使用宽松提示词）
    
    与 AI 交易员不同，这里必须给出方向和点位，不允许拒绝
    增强版：提供更多价格结构信息帮助 AI 判断入场点位
    """
    try:
        # 1. 获取市场数据（增加到 500 根 K 线）
        from ai.ai_indicators import get_data_source, IndicatorCalculator
        
        data_source = get_data_source()
        calculator = IndicatorCalculator()
        
        # 获取 K 线数据（500 根，用于更准确的指标计算和价格结构分析）
        ohlcv = data_source.fetch_ohlcv(symbol, timeframe, 500)
        if not ohlcv or len(ohlcv) < 50:
            return {'error': 'K 线数据不足'}
        
        current_price = ohlcv[-1][4]
        
        # 计算技术指标
        indicators = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR']
        latest_values = calculator.get_latest_values(indicators, ohlcv)
        formatted = calculator.format_for_ai(latest_values, symbol, timeframe)
        
        # 获取 ATR 用于计算止损止盈
        atr = latest_values.get('ATR', current_price * 0.01)
        
        # 新增：计算价格结构信息
        price_structure = _calculate_price_structure(ohlcv, latest_values)
        
        # 2. 获取用户选择的 AI
        selected_ai = st.session_state.get('advisor_selected_ai', 'deepseek')
        
        from ai.ai_config_manager import AIConfigManager
        config_mgr = AIConfigManager()
        ai_configs = config_mgr.get_all_ai_api_configs()
        
        if selected_ai not in ai_configs or not ai_configs[selected_ai].get('api_key'):
            # 尝试找到任何可用的 AI
            for ai_id, config in ai_configs.items():
                if config.get('api_key'):
                    selected_ai = ai_id
                    break
            else:
                return {'error': '请先配置 AI API Key'}
        
        # 3. 增强版提示词 - 包含价格结构信息
        symbol_short = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        analysis_prompt = f"""你是一位专业的加密货币交易顾问。用户询问 {symbol_short} 的交易建议。

## 技术指标
{formatted}

## 当前价格
{current_price:.2f} USDT

## ATR (波动率)
{atr:.2f}

## 价格结构分析
{price_structure}

## 重要要求
1. 你必须给出明确的交易方向和具体点位
2. 入场价应该参考支撑/阻力位，不要简单用当前价
3. 止损应该设在关键支撑/阻力位之外
4. 止盈应该设在下一个阻力/支撑位附近

## 输出要求
1. signal: 必须是 "open_long"（做多）或 "open_short"（做空）
2. entry_price: 入场价（参考支撑阻力位）
3. stop_loss: 止损价（关键位置之外）
4. take_profit: 止盈价（下一个关键位置）
5. confidence: 置信度 1-100
6. reasoning: 简要分析理由（包含关键价位分析，80字以内）

## 输出格式（严格 JSON）
{{
    "signal": "open_long",
    "entry_price": 88500.00,
    "stop_loss": 87800.00,
    "take_profit": 90200.00,
    "confidence": 72,
    "reasoning": "价格回踩布林中轨88600支撑，RSI超卖反弹，目标上轨90000附近"
}}"""

        # 4. 使用通用 AI 客户端调用 API
        import json
        
        api_key = ai_configs[selected_ai].get('api_key', '')
        user_model = ai_configs[selected_ai].get('model', '')  # 用户配置的模型
        
        system_prompt = "你是专业的加密货币交易顾问，擅长技术分析和价格结构分析。必须给出明确的交易方向和基于支撑阻力的具体点位。只输出 JSON，不要其他内容。"
        
        # 尝试使用通用 AI 客户端
        try:
            from ai.ai_providers import UniversalAIClient
            # 使用用户配置的模型
            client = UniversalAIClient(selected_ai, api_key, model_id=user_model if user_model else None)
            client.timeout = 60
            content = client.chat(analysis_prompt, system_prompt=system_prompt, max_tokens=500)
        except ImportError:
            # 回退到直接调用 API
            import httpx
            
            # API 端点映射
            api_endpoints = {
                "deepseek": "https://api.deepseek.com/v1/chat/completions",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                "spark": "https://spark-api-open.xf-yun.com/v1/chat/completions",
                "spark_lite": "https://spark-api-open.xf-yun.com/v1/chat/completions",
                "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1/chat/completions",
                "glm": "https://open.bigmodel.cn/api/paas/v4/chat/completions",
                "doubao": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                "openai": "https://api.openai.com/v1/chat/completions",
                "perplexity": "https://api.perplexity.ai/chat/completions",
            }
            
            # 默认模型映射（当用户没有配置模型时使用）
            default_models = {
                "deepseek": "deepseek-chat",
                "qwen": "qwen-max",
                "spark": "generalv3.5",
                "spark_lite": "lite",
                "hunyuan": "hunyuan-lite",
                "glm": "glm-4-flash",
                "doubao": "doubao-pro-4k",
                "openai": "gpt-4o-mini",
                "perplexity": "llama-3.1-sonar-small-128k-online",
            }
            
            api_url = api_endpoints.get(selected_ai, api_endpoints["deepseek"])
            # 优先使用用户配置的模型，否则使用默认模型
            model = user_model if user_model else default_models.get(selected_ai, "deepseek-chat")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": analysis_prompt}
            ]
            
            with httpx.Client(timeout=60.0) as http_client:
                response = http_client.post(
                    api_url,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                )
                response.raise_for_status()
                data = response.json()
            
            content = data['choices'][0]['message']['content']
        
        # 提取 JSON
        import re
        # 移除 think 标签
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                'signal': result.get('signal', 'open_long'),
                'confidence': result.get('confidence', 50),
                'entry_price': result.get('entry_price', current_price),
                'stop_loss': result.get('stop_loss', current_price - atr),
                'take_profit': result.get('take_profit', current_price + atr * 2),
                'reasoning': result.get('reasoning', '技术指标分析'),
                'current_price': current_price
            }
        else:
            return {'error': '无法解析 AI 响应'}
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}


def _perform_ai_analysis(symbol: str, timeframe: str) -> Dict[str, Any]:
    """
    AI 交易员分析（用于自动交易，使用严格风控）
    """
    try:
        from ai.ai_indicators import get_data_source, IndicatorCalculator
        
        data_source = get_data_source()
        calculator = IndicatorCalculator()
        
        ohlcv = data_source.fetch_ohlcv(symbol, timeframe, 100)
        if not ohlcv or len(ohlcv) < 50:
            return {'error': 'K 线数据不足'}
        
        current_price = ohlcv[-1][4]
        
        indicators = ['MA', 'EMA', 'RSI', 'MACD', 'BOLL', 'KDJ', 'ATR']
        latest_values = calculator.get_latest_values(indicators, ohlcv)
        formatted = calculator.format_for_ai(latest_values, symbol, timeframe)
        
        # 获取用户选择的 AI
        selected_ai = st.session_state.get('advisor_selected_ai', 'deepseek')
        
        from ai.ai_config_manager import AIConfigManager
        config_mgr = AIConfigManager()
        ai_configs = config_mgr.get_all_ai_api_configs()
        
        if selected_ai not in ai_configs or not ai_configs[selected_ai].get('api_key'):
            # 尝试找到任何可用的 AI
            for ai_id, config in ai_configs.items():
                if config.get('api_key'):
                    selected_ai = ai_id
                    break
            else:
                return {'error': '请先配置 AI API Key'}
        
        from ai_brain import create_agent, MarketContext
        import asyncio
        
        agent = create_agent(selected_ai, ai_configs[selected_ai].get('api_key', ''))
        
        context = MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            current_price=current_price,
            ohlcv=ohlcv,
            indicators=latest_values,
            formatted_indicators=formatted
        )
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(agent.get_decision(context, ""))
        finally:
            loop.close()
        
        return {
            'signal': result.signal,
            'confidence': result.confidence,
            'entry_price': result.entry_price or current_price,
            'stop_loss': result.stop_loss,
            'take_profit': result.take_profit,
            'reasoning': result.reasoning,
            'thinking': result.thinking,
            'current_price': current_price,
            'ai_name': selected_ai
        }
        
    except Exception as e:
        import traceback
        return {'error': str(e), 'traceback': traceback.format_exc()}


# ============ 测试入口 ============

if __name__ == "__main__":
    # 独立测试 Arena UI
    st.set_page_config(
        page_title="NOFX Arena",
        page_icon="⚔️",
        layout="wide"
    )
    
    # 模拟 view_model 和 actions
    mock_view_model = {
        "paper_balance": {"equity": 10500},
        "open_positions": {},
        "strategy_options": [
            ('(・∀・) 趋势策略 v1', 'strategy_v1'),
            ('(・∀・) 趋势策略 v2', 'strategy_v2')
        ]
    }
    
    mock_actions = {}
    
    # 渲染
    render_arena_main(mock_view_model, mock_actions)


