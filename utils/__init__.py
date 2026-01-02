# -*- coding: utf-8 -*-
"""
工具模块

包含日志、符号处理、加密、时间转换等工具函数
"""

from .logging_utils import (
    get_logger,
    setup_logger,
    render_scan_block,
    render_idle_block,
    render_risk_check,
    fix_windows_encoding,
    SafeStreamHandler,
    CustomFormatter
)
from .symbol_utils import (
    normalize_symbol,
    normalize_symbol_list,
    parse_symbol_input,
    to_okx_inst_id,
    from_okx_inst_id,
    is_symbol_whitelisted,
    get_whitelist,
    SYMBOL_WHITELIST
)
from .crypto_utils import (
    encrypt_text,
    decrypt_text,
    encrypt_bytes,
    decrypt_bytes
)
from .beijing_time_converter import (
    BeijingTimeConverter,
    DualChannelChartRenderer,
    BEIJING_TZ
)
from .candle_time_utils import (
    is_candle_closed,
    get_closed_candles,
    get_latest_closed_candle,
    get_timeframe_ms,
    get_server_time_from_ohlcv,
    utc_ms_to_beijing,
    utc_ms_to_beijing_str,
    convert_ohlcv_to_beijing_df,
    format_scan_summary,
    ClosedCandleSignalTracker,
    get_closed_candle_tracker,
    normalize_daily_timeframe,
    TIMEFRAME_MS,
    OKX_DAILY_TIMEFRAME
)
from .env_validator import (
    EnvironmentValidator,
    check_production_security
)

__all__ = [
    # logging_utils
    'get_logger', 'setup_logger', 'render_scan_block', 'render_idle_block',
    'render_risk_check', 'fix_windows_encoding', 'SafeStreamHandler', 'CustomFormatter',
    # symbol_utils
    'normalize_symbol', 'normalize_symbol_list', 'parse_symbol_input',
    'to_okx_inst_id', 'from_okx_inst_id', 'is_symbol_whitelisted', 'get_whitelist',
    'SYMBOL_WHITELIST',
    # crypto_utils
    'encrypt_text', 'decrypt_text', 'encrypt_bytes', 'decrypt_bytes',
    # beijing_time_converter
    'BeijingTimeConverter', 'DualChannelChartRenderer', 'BEIJING_TZ',
    # candle_time_utils
    'is_candle_closed', 'get_closed_candles', 'get_latest_closed_candle',
    'get_timeframe_ms', 'get_server_time_from_ohlcv', 'utc_ms_to_beijing',
    'utc_ms_to_beijing_str', 'convert_ohlcv_to_beijing_df', 'format_scan_summary',
    'ClosedCandleSignalTracker', 'get_closed_candle_tracker',
    'normalize_daily_timeframe', 'TIMEFRAME_MS', 'OKX_DAILY_TIMEFRAME',
    # env_validator
    'EnvironmentValidator', 'check_production_security'
]
