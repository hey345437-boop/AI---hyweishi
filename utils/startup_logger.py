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
# startup_logger.py - 启动日志模块
"""
系统启动日志模块，记录关键启动信息以便诊断问题。
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StartupLog:
    """启动日志数据"""
    timestamp: str = ""
    python_version: str = ""
    working_directory: str = ""
    database_type: str = ""
    database_path: str = ""
    exchange_type: str = ""
    environment_mode: str = ""
    features_enabled: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def log_startup_info() -> StartupLog:
    """
    记录系统启动信息
    
    Returns:
        StartupLog: 启动日志数据
    """
    startup_log = StartupLog()
    startup_log.timestamp = datetime.now().isoformat()
    startup_log.python_version = sys.version
    startup_log.working_directory = os.getcwd()
    
    logger.info("=" * 60)
    logger.info(" MyTradingBot 系统启动")
    logger.info("=" * 60)
    logger.info(f"📅 启动时间: {startup_log.timestamp}")
    logger.info(f"🐍 Python 版本: {startup_log.python_version}")
    logger.info(f"📁 工作目录: {startup_log.working_directory}")
    
    return startup_log


def log_database_info(startup_log: StartupLog) -> None:
    """
    记录数据库配置信息
    
    Args:
        startup_log: 启动日志对象
    """
    try:
        from db_config import get_db_config_from_env_and_secrets
        
        db_kind, db_config = get_db_config_from_env_and_secrets()
        startup_log.database_type = db_kind
        
        if db_kind == "postgres":
            # 脱敏显示 PostgreSQL URL
            url = db_config.get("url", "")
            if "@" in url:
                safe_url = url.split("@")[0].split(":")[0] + ":***@" + url.split("@")[1]
            else:
                safe_url = "<configured>"
            startup_log.database_path = safe_url
            logger.info(f"🗄️ 数据库类型: PostgreSQL")
            logger.info(f"🔗 连接: {safe_url}")
        else:
            startup_log.database_path = db_config.get("path", "")
            logger.info(f"🗄️ 数据库类型: SQLite")
            logger.info(f"📂 路径: {startup_log.database_path}")
        
        # 测试连接
        from db_bridge import _get_connection
        conn, _ = _get_connection()
        conn.close()
        logger.info(" 数据库连接测试成功")
        startup_log.features_enabled.append("database")
        
    except Exception as e:
        error_msg = f"数据库初始化失败: {str(e)}"
        startup_log.errors.append(error_msg)
        logger.error(f" {error_msg}")
        logger.error("💡 修复建议: 检查 DATABASE_URL 环境变量或确保 data 目录可写")


def log_exchange_info(startup_log: StartupLog, exchange_type: str = "okx") -> None:
    """
    记录交易所配置信息
    
    Args:
        startup_log: 启动日志对象
        exchange_type: 交易所类型
    """
    startup_log.exchange_type = exchange_type
    
    try:
        run_mode = os.getenv("RUN_MODE", "sim")
        startup_log.environment_mode = run_mode
        
        mode_desc = {
            "sim": "🛰️ 模拟模式（不执行真实交易）",
            "paper": "📝 沙盒模式（使用测试环境）",
            "live": " 实盘模式（真实交易）"
        }
        
        logger.info(f"🏦 交易所: {exchange_type.upper()}")
        logger.info(f" 运行模式: {mode_desc.get(run_mode, run_mode)}")
        
        if run_mode == "live":
            logger.warning("⚠️ 警告: 当前为实盘模式，将使用真实资金交易！")
            startup_log.warnings.append("实盘模式已启用")
        
        startup_log.features_enabled.append(f"exchange_{exchange_type}")
        
    except Exception as e:
        error_msg = f"交易所配置检查失败: {str(e)}"
        startup_log.errors.append(error_msg)
        logger.error(f" {error_msg}")


def log_security_info(startup_log: StartupLog) -> None:
    """
    记录安全配置信息
    
    Args:
        startup_log: 启动日志对象
    """
    try:
        from env_validator import EnvironmentValidator
        
        # 检查加密密钥
        key_valid, key_error = EnvironmentValidator.validate_encryption_key()
        if key_valid:
            logger.info(" 加密密钥: 已配置")
            startup_log.features_enabled.append("encryption")
        else:
            startup_log.errors.append(key_error)
            logger.error(f" 加密密钥: {key_error}")
            logger.error("💡 修复建议: 设置 MYTRADINGBOT_MASTER_PASS 环境变量")
        
        # 检查访问密码
        pwd_valid, pwd_warning, _ = EnvironmentValidator.validate_access_password()
        if pwd_valid:
            if pwd_warning:
                startup_log.warnings.append("使用开发模式默认密码")
                logger.warning(f"⚠️ 访问密码: {pwd_warning}")
            else:
                logger.info("🔑 访问密码: 已配置")
            startup_log.features_enabled.append("access_control")
        else:
            startup_log.errors.append(pwd_warning)
            logger.error(f" 访问密码: {pwd_warning}")
        
    except ImportError:
        logger.warning("⚠️ 环境验证模块未找到，跳过安全检查")


def log_startup_failure(error: str, remediation: str) -> None:
    """
    记录启动失败信息
    
    Args:
        error: 错误描述
        remediation: 修复建议
    """
    logger.error("=" * 60)
    logger.error(" 系统启动失败")
    logger.error("=" * 60)
    logger.error(f"错误: {error}")
    logger.error(f"💡 修复建议: {remediation}")
    logger.error("=" * 60)


def log_startup_success(startup_log: StartupLog) -> None:
    """
    记录启动成功摘要
    
    Args:
        startup_log: 启动日志对象
    """
    logger.info("=" * 60)
    logger.info(" 系统启动成功")
    logger.info("=" * 60)
    logger.info(f" 启用的功能: {', '.join(startup_log.features_enabled)}")
    
    if startup_log.warnings:
        logger.warning(f"⚠️ 警告数量: {len(startup_log.warnings)}")
        for w in startup_log.warnings:
            logger.warning(f"   - {w}")
    
    if startup_log.errors:
        logger.error(f" 错误数量: {len(startup_log.errors)}")
        for e in startup_log.errors:
            logger.error(f"   - {e}")
    
    logger.info("=" * 60)


def run_startup_checks() -> StartupLog:
    """
    运行所有启动检查
    
    Returns:
        StartupLog: 完整的启动日志
    """
    startup_log = log_startup_info()
    log_database_info(startup_log)
    log_exchange_info(startup_log)
    log_security_info(startup_log)
    
    if startup_log.errors:
        log_startup_failure(
            f"发现 {len(startup_log.errors)} 个错误",
            "请检查上述错误信息并修复配置"
        )
    else:
        log_startup_success(startup_log)
    
    return startup_log
