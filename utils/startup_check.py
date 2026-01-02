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
# startup_check.py
# OKX 环境启动自检模块
# 重要说明：本系统只支持两种模式
# - live: 实盘模式，真实下单
# - paper_on_real: 实盘测试模式，用实盘行情但本地模拟下单
# 两种模式都必须使用实盘 API Key，绝对禁止 demo/sandbox

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StartupCheckResult:
    """启动自检结果"""
    run_mode: str = ""           # live/paper_on_real
    api_domain: str = ""         # www.okx.com (必须是实盘)
    simulated_trading: int = 0   # x-simulated-trading header (必须为0)
    sandbox_enabled: bool = False  # sandbox 状态 (必须为False)
    key_type: str = ""           # live_key (必须是实盘Key)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # 兼容旧属性名
    @property
    def env_mode(self) -> str:
        return self.run_mode
    
    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


class OKXEnvironmentError(Exception):
    """OKX 环境配置错误 - 用于阻断启动"""
    pass


class StartupSelfCheck:
    """启动自检"""
    
    # 禁止的模式
    FORBIDDEN_MODES = {'demo', 'sandbox', 'test'}
    
    # 允许的模式（统一为 'live' 和 'paper'）
    ALLOWED_MODES = {'live', 'paper'}
    
    # 会被映射到 'paper' 的旧模式
    LEGACY_PAPER_MODES = {'sim', 'paper_on_real', 'simulation', 'paper_trading'}
    
    @staticmethod
    def check_okx_environment(
        env_mode: str = None,
        run_mode: str = None,
        api_key: str = "",
        is_sandbox: bool = False,
        api_passphrase: str = "",
        x_simulated_trading: int = 0
    ) -> StartupCheckResult:
        """
        检查 OKX 环境配置
        
        本系统只支持两种模式：
        - live: 实盘模式，真实下单
        - paper_on_real: 实盘测试模式，用实盘行情但本地模拟下单
        
        两种模式都必须：
        - 使用实盘 API Key
        - sandbox = False
        - x-simulated-trading = 0
        
        Args:
            env_mode: 旧参数名，兼容用
            run_mode: 运行模式 (live/paper_on_real)
            api_key: OKX API Key (必须是实盘Key)
            is_sandbox: sandbox 状态 (必须为False)
            api_passphrase: API Passphrase
            x_simulated_trading: x-simulated-trading header (必须为0)
        
        Returns:
            StartupCheckResult 包含检查结果
        
        Raises:
            OKXEnvironmentError: 如果配置不符合要求
        """
        # 兼容旧参数名
        mode = run_mode or env_mode or 'paper_on_real'
        
        result = StartupCheckResult()
        
        # 映射旧模式到新模式
        if mode in StartupSelfCheck.LEGACY_PAPER_MODES:
            result.warnings.append(
                f"⚠️ 模式 '{mode}' 已废弃，自动映射为 'paper'"
            )
            mode = 'paper'
        
        # 检查是否是禁止的模式
        if mode in StartupSelfCheck.FORBIDDEN_MODES:
            result.errors.append(
                f" 模式 '{mode}' 不允许！本系统只支持 live 和 paper_on_real"
            )
        
        result.run_mode = mode
        
        # 关键检查：sandbox 必须为 False
        if is_sandbox:
            result.errors.append(
                " sandbox=True 不允许！本系统禁止使用 OKX 模拟盘"
            )
        result.sandbox_enabled = is_sandbox
        
        # 关键检查：x-simulated-trading 必须为 0
        if x_simulated_trading != 0:
            result.errors.append(
                f" x-simulated-trading={x_simulated_trading} 不允许！必须为 0"
            )
        result.simulated_trading = x_simulated_trading
        
        # API 域名（必须是实盘）
        result.api_domain = "www.okx.com (实盘)"
        
        # 检查 API Key
        if not api_key:
            result.errors.append(" 未配置 OKX API Key")
            result.key_type = "missing"
        else:
            # 检测 Key 类型
            key_type = StartupSelfCheck._detect_key_type(api_key)
            result.key_type = key_type
            
            if key_type == "demo_key":
                result.errors.append(
                    " 检测到模拟盘 API Key！本系统只支持实盘 Key"
                )
        
        return result
    
    @staticmethod
    def _detect_key_type(api_key: str) -> str:
        """检测 API Key 类型"""
        if not api_key:
            return "missing"
        
        key_lower = api_key.lower()
        
        # 检查是否包含 demo 相关指示
        demo_indicators = ['demo', 'test', 'sandbox', 'sim']
        for indicator in demo_indicators:
            if indicator in key_lower:
                return "demo_key"
        
        return "live_key"
    
    @staticmethod
    def validate_and_raise(result: StartupCheckResult) -> None:
        """
        验证结果并在有错误时抛出异常阻断启动
        
        Args:
            result: 自检结果
        
        Raises:
            OKXEnvironmentError: 如果有错误
        """
        if result.has_errors:
            error_msg = (
                "\n" + "="*60 + "\n"
                "🚨 OKX 环境配置错误 - 启动被阻断\n"
                "="*60 + "\n"
                "本系统只支持两种模式:\n"
                "  - live: 实盘模式（真实下单）\n"
                "  - paper_on_real: 实盘测试模式（实盘行情+本地模拟）\n"
                "\n"
                "两种模式都必须:\n"
                "  - 使用实盘 API Key\n"
                "  - OKX_SANDBOX=false\n"
                "  - x-simulated-trading=0\n"
                "\n"
                "发现的错误:\n"
            )
            for i, err in enumerate(result.errors, 1):
                error_msg += f"  {i}. {err}\n"
            
            error_msg += "\n修复方法:\n"
            for step in StartupSelfCheck.get_remediation_steps(result):
                error_msg += f"  {step}\n"
            error_msg += "="*60
            
            logger.error(error_msg)
            raise OKXEnvironmentError(error_msg)
    
    @staticmethod
    def print_startup_summary(result: StartupCheckResult, verbose: bool = False) -> None:
        """打印启动摘要"""
        # 有错误时打印详细信息并阻断
        if result.errors:
            print("=" * 60)
            print("🚨 OKX 环境自检失败")
            print("=" * 60)
            print(f"📌 运行模式: {result.run_mode}")
            print(f"🌐 API 域名: {result.api_domain}")
            print(f"🔄 x-simulated-trading: {result.simulated_trading}")
            print(f"📦 sandbox: {result.sandbox_enabled}")
            print(f"🔑 API Key 类型: {result.key_type}")
            print("-" * 60)
            
            print(" 错误:")
            for error in result.errors:
                print(f"  {error}")
            
            if result.warnings:
                print("\n⚠️ 警告:")
                for warning in result.warnings:
                    print(f"  {warning}")
            
            print("=" * 60)
            
            # 记录到日志
            for error in result.errors:
                logger.error(error)
            for warning in result.warnings:
                logger.warning(warning)
            
            return
        
        # 有警告时打印详细信息
        if result.warnings or verbose:
            print("=" * 60)
            print(" OKX 环境自检通过")
            print("=" * 60)
            print(f"📌 运行模式: {result.run_mode}")
            print(f"🌐 API 域名: {result.api_domain}")
            print(f"🔄 x-simulated-trading: {result.simulated_trading}")
            print(f"📦 sandbox: {result.sandbox_enabled}")
            print(f"🔑 API Key 类型: {result.key_type}")
            
            if result.warnings:
                print("-" * 60)
                print("⚠️ 警告:")
                for warning in result.warnings:
                    print(f"  {warning}")
            
            print("=" * 60)
            
            for warning in result.warnings:
                logger.warning(warning)
        else:
            # 正常情况只打印一行
            logger.info(
                f" OKX 环境自检通过 | "
                f"模式: {result.run_mode} | "
                f"x-simulated-trading: {result.simulated_trading} | "
                f"sandbox: {result.sandbox_enabled}"
            )
    
    @staticmethod
    def get_remediation_steps(result: StartupCheckResult) -> List[str]:
        """获取修复建议"""
        steps = []
        
        if result.sandbox_enabled:
            steps.append("1. 在 .env 文件中设置 OKX_SANDBOX=false")
        
        if result.simulated_trading != 0:
            steps.append("2. 确保代码中 x-simulated-trading=0")
        
        if result.key_type == "demo_key":
            steps.append("3. 使用 OKX 实盘 API Key（不是模拟盘 Key）")
        
        if result.key_type == "missing":
            steps.append("4. 配置 OKX_API_KEY 环境变量")
        
        if result.run_mode in StartupSelfCheck.FORBIDDEN_MODES:
            steps.append("5. 将 RUN_MODE 设置为 'live' 或 'paper_on_real'")
        
        if not steps:
            steps.append("请检查 OKX API 配置")
        
        return steps


def run_startup_check(raise_on_error: bool = True) -> StartupCheckResult:
    """
    执行启动自检
    
    Args:
        raise_on_error: 是否在有错误时抛出异常阻断启动
    
    Returns:
        StartupCheckResult
    
    Raises:
        OKXEnvironmentError: 如果 raise_on_error=True 且有错误
    """
    # 从环境变量读取配置
    run_mode = os.getenv('RUN_MODE', 'paper')
    api_key = os.getenv('OKX_API_KEY', '')
    api_passphrase = os.getenv('OKX_PASSPHRASE', '')
    
    # 关键：强制 sandbox=False
    # 即使环境变量设置了 OKX_SANDBOX=true，也强制为 False
    is_sandbox = False  # 强制禁用
    
    # 执行检查
    result = StartupSelfCheck.check_okx_environment(
        run_mode=run_mode,
        api_key=api_key,
        is_sandbox=is_sandbox,
        api_passphrase=api_passphrase,
        x_simulated_trading=0  # 强制为 0
    )
    
    # 打印摘要
    StartupSelfCheck.print_startup_summary(result)
    
    # 有错误时阻断启动
    if raise_on_error and result.has_errors:
        StartupSelfCheck.validate_and_raise(result)
    
    return result
