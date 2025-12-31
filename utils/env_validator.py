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
#   Copyright (c) 2024-2025 HeWeiShi. All Rights Reserved.
#   License: Apache License 2.0
#
# ============================================================================
# env_validator.py - 环境变量验证模块
"""
环境变量验证器，用于验证关键配置的安全性和完整性。
"""

import os
import logging
import subprocess
import re
from typing import Tuple, Optional, Dict

logger = logging.getLogger(__name__)


def _scan_local_proxy_ports_impl() -> Optional[int]:
    """
    智能扫描本地监听端口，检测代理软件
    
    通过 netstat 命令获取所有监听端口，然后筛选可能是代理的端口
    
    Returns:
        Optional[int]: 检测到的代理端口，如果没有则返回 None
    """
    try:
        # 使用 netstat 获取所有监听端口
        if os.name == 'nt':
            result = subprocess.run(
                ['netstat', '-an'],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
        else:
            result = subprocess.run(
                ['netstat', '-tlnp'],
                capture_output=True,
                text=True,
                timeout=5
            )
        
        if result.returncode != 0:
            return None
        
        # 解析输出，提取 127.0.0.1 上的监听端口
        listening_ports = set()
        for line in result.stdout.split('\n'):
            # Windows: TCP    127.0.0.1:7890    0.0.0.0:0    LISTENING
            # Linux: tcp    0    0    127.0.0.1:7890    0.0.0.0:*    LISTEN
            if 'LISTEN' in line.upper():
                # 提取端口号
                match = re.search(r'127\.0\.0\.1[:\.](\d+)', line)
                if match:
                    port = int(match.group(1))
                    # 排除常见非代理端口
                    if port not in [80, 443, 3000, 3001, 5000, 5001, 8000, 8001, 8501, 8502]:
                        listening_ports.add(port)
        
        # 代理软件常用端口范围和特征
        proxy_port_ranges = [
            (1080, 1090),    # SOCKS 代理常用范围
            (7890, 7900),    # Clash 常用范围
            (10800, 10820),  # V2Ray 常用范围
            (8080, 8090),    # HTTP 代理常用范围
            (2080, 2090),    # 备用范围
            (6150, 6160),    # Surge 范围
            (33200, 33220),  # 自定义范围
            (41090, 41100),  # 自定义范围
            (49490, 49500),  # 自定义范围
        ]
        
        # 优先检查在代理端口范围内的监听端口
        for port in sorted(listening_ports):
            for start, end in proxy_port_ranges:
                if start <= port <= end:
                    # 验证端口是否真的是 HTTP 代理
                    if _test_http_proxy(port):
                        return port
        
        # 如果没有在常用范围内找到，尝试所有监听端口
        for port in sorted(listening_ports):
            if 1024 < port < 65535:  # 排除系统端口
                if _test_http_proxy(port):
                    return port
        
        return None
    except Exception as e:
        logger.debug(f"扫描本地端口失败: {e}")
        return None


def _test_http_proxy(port: int) -> bool:
    """
    测试指定端口是否是 HTTP 代理
    
    Args:
        port: 端口号
        
    Returns:
        bool: 是否是 HTTP 代理
    """
    import socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            # 发送 HTTP CONNECT 请求测试
            sock.send(b'CONNECT www.google.com:443 HTTP/1.1\r\nHost: www.google.com:443\r\n\r\n')
            sock.settimeout(2)
            try:
                response = sock.recv(1024)
                sock.close()
                # 如果收到 HTTP 响应，说明是代理
                if b'HTTP/' in response or b'200' in response or b'Connection' in response:
                    return True
            except socket.timeout:
                sock.close()
                # 超时也可能是代理（某些代理不响应 CONNECT）
                return True
        sock.close()
        return False
    except Exception:
        return False


class EnvironmentValidator:
    """环境变量验证器"""
    
    # 不安全的默认密码（必须检测并拒绝）
    INSECURE_DEFAULT_PASS = 'default_insecure_pass'
    
    # 开发模式默认密码（仅用于本地开发）
    DEV_DEFAULT_PASSWORD = '770880'
    
    @staticmethod
    def detect_system_proxy() -> Dict[str, str]:
        """
        自动检测系统代理设置
        
        检测顺序：
        1. 环境变量 (http_proxy, https_proxy, socks5_proxy)
        2. Windows 系统代理设置
        3. 扫描本地监听端口（智能检测代理软件）
        4. 常见代理软件端口 (Clash, V2Ray, SSR 等)
        
        Returns:
            Dict[str, str]: 代理配置字典，包含 http_proxy, https_proxy, socks5_proxy
        """
        proxy_config = {
            'http_proxy': '',
            'https_proxy': '',
            'socks5_proxy': ''
        }
        
        # 1. 首先检查环境变量
        env_http = os.getenv('http_proxy', '') or os.getenv('HTTP_PROXY', '')
        env_https = os.getenv('https_proxy', '') or os.getenv('HTTPS_PROXY', '')
        env_socks = os.getenv('socks5_proxy', '') or os.getenv('SOCKS5_PROXY', '') or os.getenv('all_proxy', '')
        
        if env_http or env_https or env_socks:
            proxy_config['http_proxy'] = env_http
            proxy_config['https_proxy'] = env_https or env_http
            proxy_config['socks5_proxy'] = env_socks
            logger.info(f"从环境变量检测到代理: {proxy_config}")
            return proxy_config
        
        # 2. Windows 系统代理检测
        if os.name == 'nt':
            try:
                # 读取 Windows 注册表中的代理设置
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                    r'Software\Microsoft\Windows\CurrentVersion\Internet Settings') as key:
                    proxy_enable, _ = winreg.QueryValueEx(key, 'ProxyEnable')
                    if proxy_enable:
                        proxy_server, _ = winreg.QueryValueEx(key, 'ProxyServer')
                        if proxy_server:
                            # 解析代理服务器地址
                            if '://' not in proxy_server:
                                proxy_server = f'http://{proxy_server}'
                            proxy_config['http_proxy'] = proxy_server
                            proxy_config['https_proxy'] = proxy_server
                            logger.info(f"从 Windows 系统设置检测到代理: {proxy_server}")
                            return proxy_config
            except Exception as e:
                logger.debug(f"读取 Windows 代理设置失败: {e}")
        
        # 3. 智能扫描本地监听端口（检测代理软件）
        detected_port = _scan_local_proxy_ports_impl()
        if detected_port:
            proxy_url = f'http://127.0.0.1:{detected_port}'
            proxy_config['http_proxy'] = proxy_url
            proxy_config['https_proxy'] = proxy_url
            logger.info(f"智能检测到本地代理端口: {detected_port}")
            return proxy_config
        
        # 4. 检测常见代理软件端口（扩展列表，覆盖更多场景）
        common_proxy_ports = [
            # Clash 系列
            (7890, 'http'),   # Clash 默认 HTTP
            (7891, 'socks5'), # Clash 默认 SOCKS
            (7892, 'http'),   # Clash Verge 备用
            (7893, 'http'),   # Clash for Windows 备用
            # 自定义高端口（用户常用）
            (49494, 'http'),  # 自定义端口
            (33210, 'http'),  # 自定义端口
            (41091, 'http'),  # 自定义端口
            # V2Ray 系列
            (10808, 'socks5'), # V2Ray 默认 SOCKS
            (10809, 'http'),  # V2Ray 默认 HTTP
            (10810, 'http'),  # V2RayN 备用
            (10811, 'http'),  # V2RayN 备用
            # SSR/SS 系列
            (1080, 'socks5'), # SSR/SS 默认
            (1081, 'http'),   # SSR HTTP
            (1082, 'http'),   # SS 备用
            (1086, 'http'),   # ShadowsocksX-NG
            (1087, 'http'),   # ShadowsocksX-NG HTTP
            # 其他代理软件
            (8080, 'http'),   # 通用 HTTP 代理
            (8118, 'http'),   # Privoxy
            (9090, 'http'),   # Clash Dashboard / 其他
            (2080, 'http'),   # 备用端口
            (2081, 'http'),   # 备用端口
            # Surge / Quantumult
            (6152, 'http'),   # Surge
            (6153, 'socks5'), # Surge SOCKS
        ]
        
        import socket
        for port, proxy_type in common_proxy_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result = sock.connect_ex(('127.0.0.1', port))
                sock.close()
                
                if result == 0:
                    if proxy_type == 'http':
                        proxy_url = f'http://127.0.0.1:{port}'
                        proxy_config['http_proxy'] = proxy_url
                        proxy_config['https_proxy'] = proxy_url
                    else:
                        proxy_config['socks5_proxy'] = f'socks5://127.0.0.1:{port}'
                    logger.info(f"检测到本地代理端口 {port} ({proxy_type})")
                    return proxy_config
            except Exception:
                continue
        
        logger.debug("未检测到系统代理")
        return proxy_config
    
    @staticmethod
    def apply_proxy_to_env(proxy_config: Dict[str, str] = None) -> Dict[str, str]:
        """
        将代理配置应用到环境变量
        
        Args:
            proxy_config: 代理配置，如果为 None 则自动检测
            
        Returns:
            Dict[str, str]: 应用的代理配置
        """
        if proxy_config is None:
            proxy_config = EnvironmentValidator.detect_system_proxy()
        
        if proxy_config.get('http_proxy'):
            os.environ['http_proxy'] = proxy_config['http_proxy']
            os.environ['HTTP_PROXY'] = proxy_config['http_proxy']
        
        if proxy_config.get('https_proxy'):
            os.environ['https_proxy'] = proxy_config['https_proxy']
            os.environ['HTTPS_PROXY'] = proxy_config['https_proxy']
        
        if proxy_config.get('socks5_proxy'):
            os.environ['socks5_proxy'] = proxy_config['socks5_proxy']
            os.environ['all_proxy'] = proxy_config['socks5_proxy']
        
        return proxy_config
    
    @staticmethod
    def get_proxy_for_ccxt() -> Optional[Dict[str, str]]:
        """
        获取适用于 CCXT 的代理配置
        
        Returns:
            Optional[Dict[str, str]]: CCXT 代理配置，如 {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
        """
        proxy_config = EnvironmentValidator.detect_system_proxy()
        
        if not proxy_config.get('http_proxy') and not proxy_config.get('https_proxy'):
            return None
        
        ccxt_proxy = {}
        if proxy_config.get('http_proxy'):
            ccxt_proxy['http'] = proxy_config['http_proxy']
        if proxy_config.get('https_proxy'):
            ccxt_proxy['https'] = proxy_config['https_proxy']
        
        return ccxt_proxy if ccxt_proxy else None
    
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
