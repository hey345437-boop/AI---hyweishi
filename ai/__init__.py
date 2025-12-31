# -*- coding: utf-8 -*-
"""
AI 决策模块

包含 AI 大模型集成、决策引擎、指标计算等
"""

from .ai_brain import (
    MarketContext,
    AIDecisionResult,
    BaseAgent,
    SYSTEM_PROMPT_TEMPLATE,
    USER_PROMPT_TEMPLATE
)
from .ai_providers import (
    AI_PROVIDERS,
    AIProvider,
    AIModel,
    UniversalAIClient,
    verify_api_key,
    verify_api_key_sync,
    get_available_providers,
    get_provider,
    create_client
)
from .ai_config_manager import (
    AIConfigManager,
    get_ai_config_manager,
    PROMPT_PRESETS,
    PromptPreset
)
from .ai_db_manager import (
    AIDBManager,
    get_ai_db_manager,
    AIDecision,
    AIStats
)
from .ai_indicators import (
    IndicatorCalculator,
    get_ai_indicators,
    get_batch_ai_indicators,
    calc_ma,
    calc_ema,
    calc_rsi,
    calc_macd,
    calc_boll,
    calc_kdj,
    calc_atr
)
from .ai_trade_bridge import (
    AITradeBridge,
    AITradeSignal,
    AITradeResult,
    AITradeMode,
    get_ai_trade_bridge,
    execute_ai_signal
)
from .ai_api_validator import verify_api_key as validate_api_key

__all__ = [
    # ai_brain
    'MarketContext', 'AIDecisionResult', 'BaseAgent',
    'SYSTEM_PROMPT_TEMPLATE', 'USER_PROMPT_TEMPLATE',
    # ai_providers
    'AI_PROVIDERS', 'AIProvider', 'AIModel', 'UniversalAIClient',
    'verify_api_key', 'verify_api_key_sync', 'get_available_providers',
    'get_provider', 'create_client',
    # ai_config_manager
    'AIConfigManager', 'get_ai_config_manager', 'PROMPT_PRESETS', 'PromptPreset',
    # ai_db_manager
    'AIDBManager', 'get_ai_db_manager', 'AIDecision', 'AIStats',
    # ai_indicators
    'IndicatorCalculator', 'get_ai_indicators', 'get_batch_ai_indicators',
    'calc_ma', 'calc_ema', 'calc_rsi', 'calc_macd', 'calc_boll', 'calc_kdj', 'calc_atr',
    # ai_trade_bridge
    'AITradeBridge', 'AITradeSignal', 'AITradeResult', 'AITradeMode',
    'get_ai_trade_bridge', 'execute_ai_signal',
    # ai_api_validator
    'validate_api_key'
]
