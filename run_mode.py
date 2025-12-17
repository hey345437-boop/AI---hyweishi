# run_mode.py
# 统一运行模式定义
#
# 本系统只支持两种运行模式：
# - LIVE: 实盘模式，真实下单
# - PAPER: 实盘测试模式，用实盘行情但本地模拟下单
#
# 两种模式都必须使用实盘 API Key，绝对禁止 demo/sandbox

from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RunMode(Enum):
    """
    运行模式枚举
    
    LIVE: 实盘模式 - 真实下单，真实资金
    PAPER: 实盘测试模式 - 实盘行情，本地模拟下单
    """
    LIVE = "live"
    PAPER = "paper"
    
    @classmethod
    def from_string(cls, mode_str: str) -> "RunMode":
        """
        从字符串转换为 RunMode 枚举
        
        支持的映射：
        - 'live' -> LIVE
        - 'paper', 'paper_on_real', 'sim', 'simulation' -> PAPER
        
        Args:
            mode_str: 模式字符串
        
        Returns:
            RunMode 枚举值
        
        Raises:
            ValueError: 如果是禁止的模式（demo/sandbox/test）
        """
        if not mode_str:
            return cls.PAPER
        
        mode_lower = mode_str.lower().strip()
        
        # 禁止的模式
        FORBIDDEN_MODES = {'demo', 'sandbox', 'test'}
        if mode_lower in FORBIDDEN_MODES:
            raise ValueError(
                f"模式 '{mode_str}' 不允许！本系统只支持 'live' 和 'paper' 模式。"
                f"禁止使用 demo/sandbox/test。"
            )
        
        # 映射到 LIVE
        if mode_lower == 'live':
            return cls.LIVE
        
        # 映射到 PAPER（兼容旧命名）
        PAPER_ALIASES = {'paper', 'paper_on_real', 'sim', 'simulation', 'paper_trading'}
        if mode_lower in PAPER_ALIASES:
            if mode_lower != 'paper':
                logger.warning(f"模式 '{mode_str}' 已废弃，自动映射为 'paper'")
            return cls.PAPER
        
        # 未知模式，默认 PAPER 并警告
        logger.warning(f"未知模式 '{mode_str}'，默认使用 'paper' 模式")
        return cls.PAPER
    
    def is_paper(self) -> bool:
        """是否为模拟模式"""
        return self == RunMode.PAPER
    
    def is_live(self) -> bool:
        """是否为实盘模式"""
        return self == RunMode.LIVE
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"RunMode.{self.name}"


# 便捷函数
def get_run_mode(mode_str: Optional[str] = None) -> RunMode:
    """
    获取运行模式
    
    Args:
        mode_str: 模式字符串，如果为 None 则从环境变量读取
    
    Returns:
        RunMode 枚举值
    """
    import os
    
    if mode_str is None:
        mode_str = os.getenv('RUN_MODE', 'paper')
    
    return RunMode.from_string(mode_str)


def is_paper_mode(mode_str: Optional[str] = None) -> bool:
    """检查是否为模拟模式"""
    return get_run_mode(mode_str).is_paper()


def is_live_mode(mode_str: Optional[str] = None) -> bool:
    """检查是否为实盘模式"""
    return get_run_mode(mode_str).is_live()


# UI 显示映射
RUN_MODE_DISPLAY = {
    RunMode.LIVE: "💰 实盘",
    RunMode.PAPER: "🛰️ 实盘测试"
}

# DB 存储映射（统一使用 'live' 和 'paper'）
RUN_MODE_TO_DB = {
    RunMode.LIVE: "live",
    RunMode.PAPER: "paper"
}

# DB 值到 RunMode 的映射
DB_TO_RUN_MODE = {
    "live": RunMode.LIVE,
    "paper": RunMode.PAPER,
    # 兼容旧值
    "sim": RunMode.PAPER,
    "paper_on_real": RunMode.PAPER
}


def run_mode_to_display(mode: RunMode) -> str:
    """将 RunMode 转换为 UI 显示文本"""
    return RUN_MODE_DISPLAY.get(mode, "🛰️ 实盘测试")


def run_mode_to_db(mode: RunMode) -> str:
    """将 RunMode 转换为 DB 存储值"""
    return RUN_MODE_TO_DB.get(mode, "paper")


def db_to_run_mode(db_value: str) -> RunMode:
    """将 DB 存储值转换为 RunMode"""
    return DB_TO_RUN_MODE.get(db_value, RunMode.PAPER)
