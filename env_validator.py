# env_validator.py - 环境变量验证模块
"""
环境变量验证器，用于验证关键配置的安全性和完整性。
"""

import os
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """环境变量验证器"""
    
    # 不安全的默认密码（必须检测并拒绝）
    INSECURE_DEFAULT_PASS = 'default_insecure_pass'
    
    # 开发模式默认密码（仅用于本地开发）
    DEV_DEFAULT_PASSWORD = 'dev123'
    
    @staticmethod
    def is_production_mode() -> bool:
        """
        检查是否为生产模式
        
        生产模式判断条件：
        1. RUN_MODE 环境变量设置为 'live'
        2. 或者 PRODUCTION 环境变量设置为 'true'
        
        Returns:
            bool: 是否为生产模式
        """
        run_mode = os.getenv('RUN_MODE', '').lower()
        production = os.getenv('PRODUCTION', '').lower()
        
        return run_mode == 'live' or production == 'true'
    
    @staticmethod
    def validate_encryption_key() -> Tuple[bool, str]:
        """
        验证加密密钥配置
        
        检查 MYTRADINGBOT_MASTER_PASS 环境变量：
        1. 必须设置
        2. 不能等于默认不安全值
        3. 生产模式下必须满足以上条件
        
        Returns:
            Tuple[bool, str]: (是否有效, 错误信息或空字符串)
        """
        master_pass = os.getenv('MYTRADINGBOT_MASTER_PASS', '')
        cipher_key = os.getenv('MYTRADINGBOT_CIPHER_KEY', '')
        
        is_production = EnvironmentValidator.is_production_mode()
        
        # 如果设置了 CIPHER_KEY，优先使用
        if cipher_key:
            return True, ''
        
        # 检查 MASTER_PASS
        if not master_pass:
            if is_production:
                return False, '生产模式下必须设置 MYTRADINGBOT_MASTER_PASS 环境变量'
            else:
                logger.warning('⚠️ 未设置 MYTRADINGBOT_MASTER_PASS，使用默认密钥（仅限开发环境）')
                return True, ''
        
        # 检查是否使用了不安全的默认值
        if master_pass == EnvironmentValidator.INSECURE_DEFAULT_PASS:
            if is_production:
                return False, '生产模式下不能使用默认加密密钥，请设置安全的 MYTRADINGBOT_MASTER_PASS'
            else:
                logger.warning('⚠️ 使用了默认加密密钥，仅限开发环境使用')
                return True, ''
        
        return True, ''
    
    @staticmethod
    def validate_access_password(run_mode: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        验证访问密码配置
        
        Args:
            run_mode: 运行模式，如果为 None 则从环境变量读取
        
        Returns:
            Tuple[bool, str, Optional[str]]: (是否有效, 错误信息, 要使用的密码)
            - 如果有效且设置了密码，返回 (True, '', password)
            - 如果有效但使用默认密码，返回 (True, 'warning_message', default_password)
            - 如果无效，返回 (False, 'error_message', None)
        """
        password = os.getenv('STREAMLIT_ACCESS_PASSWORD', '').strip()
        
        if run_mode is None:
            run_mode = os.getenv('RUN_MODE', 'sim').lower()
        else:
            run_mode = run_mode.lower()
        
        is_production = run_mode == 'live'
        
        # 如果设置了密码，直接使用
        if password:
            return True, '', password
        
        # 未设置密码
        if is_production:
            return False, '生产模式下必须设置 STREAMLIT_ACCESS_PASSWORD 环境变量', None
        
        # 开发模式，使用默认密码并警告
        warning_msg = '⚠️ 未设置 STREAMLIT_ACCESS_PASSWORD，使用开发模式默认密码（不安全）'
        logger.warning(warning_msg)
        return True, warning_msg, EnvironmentValidator.DEV_DEFAULT_PASSWORD
    
    @staticmethod
    def validate_all() -> Tuple[bool, list]:
        """
        验证所有关键环境变量
        
        Returns:
            Tuple[bool, list]: (是否全部有效, 错误信息列表)
        """
        errors = []
        
        # 验证加密密钥
        key_valid, key_error = EnvironmentValidator.validate_encryption_key()
        if not key_valid:
            errors.append(key_error)
        
        # 验证访问密码
        pwd_valid, pwd_error, _ = EnvironmentValidator.validate_access_password()
        if not pwd_valid:
            errors.append(pwd_error)
        
        return len(errors) == 0, errors


# 便捷函数
def check_production_security() -> Tuple[bool, list]:
    """
    检查生产环境安全配置
    
    Returns:
        Tuple[bool, list]: (是否安全, 问题列表)
    """
    return EnvironmentValidator.validate_all()
