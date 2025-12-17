"""
config_manager.py - API 密钥配置管理模块

功能：
1. 从 UI 保存 API Key 到本地加密文件
2. 启动时优先从文件读取，回退到环境变量
3. 支持热更新内存配置（无需重启）

安全性：
- 使用 Fernet 对称加密存储敏感信息
- 加密密钥从环境变量 MYTRADINGBOT_MASTER_PASS 派生
"""

import os
import json
import base64
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path(os.getenv("MYTRADINGBOT_DATA_DIR", "./data"))
SECRETS_FILE = CONFIG_DIR / "secrets.enc"

# 尝试导入加密库
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography 库未安装，将使用 Base64 编码（不安全）")


@dataclass
class APICredentials:
    """API 凭证数据结构"""
    # 交易专用 Key
    trade_api_key: str = ""
    trade_api_secret: str = ""
    trade_api_passphrase: str = ""
    
    # 行情专用 Key
    market_api_key: str = ""
    market_api_secret: str = ""
    market_api_passphrase: str = ""
    
    # 元数据
    updated_at: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'APICredentials':
        return cls(
            trade_api_key=data.get('trade_api_key', ''),
            trade_api_secret=data.get('trade_api_secret', ''),
            trade_api_passphrase=data.get('trade_api_passphrase', ''),
            market_api_key=data.get('market_api_key', ''),
            market_api_secret=data.get('market_api_secret', ''),
            market_api_passphrase=data.get('market_api_passphrase', ''),
            updated_at=data.get('updated_at', '')
        )
    
    def has_trade_key(self) -> bool:
        """是否配置了交易 Key"""
        return bool(self.trade_api_key and self.trade_api_secret and self.trade_api_passphrase)
    
    def has_market_key(self) -> bool:
        """是否配置了行情 Key"""
        return bool(self.market_api_key and self.market_api_secret and self.market_api_passphrase)
    
    def get_trade_key_tail(self) -> str:
        """获取交易 Key 尾部（脱敏显示）"""
        return self.trade_api_key[-4:] if self.trade_api_key else ""
    
    def get_market_key_tail(self) -> str:
        """获取行情 Key 尾部（脱敏显示）"""
        return self.market_api_key[-4:] if self.market_api_key else ""


class ConfigManager:
    """
    配置管理器
    
    职责：
    1. 加密存储 API 凭证
    2. 启动时加载配置
    3. 支持热更新
    """
    
    def __init__(self):
        self._credentials: Optional[APICredentials] = None
        self._fernet: Optional['Fernet'] = None
        self._init_encryption()
        self._ensure_config_dir()
    
    def _init_encryption(self):
        """初始化加密器"""
        if not CRYPTO_AVAILABLE:
            return
        
        # 从环境变量获取主密钥
        master_pass = os.getenv("MYTRADINGBOT_MASTER_PASS", "default_insecure_key")
        
        # 派生 Fernet 密钥（32 字节 base64）
        key_bytes = hashlib.sha256(master_pass.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        
        self._fernet = Fernet(fernet_key)
    
    def _ensure_config_dir(self):
        """确保配置目录存在"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def _encrypt(self, data: str) -> str:
        """加密数据"""
        if self._fernet:
            encrypted = self._fernet.encrypt(data.encode())
            return encrypted.decode()
        else:
            # 回退到 Base64（不安全，仅用于无加密库的情况）
            return base64.b64encode(data.encode()).decode()
    
    def _decrypt(self, data: str) -> str:
        """解密数据"""
        if self._fernet:
            decrypted = self._fernet.decrypt(data.encode())
            return decrypted.decode()
        else:
            return base64.b64decode(data.encode()).decode()
    
    def save_credentials(self, credentials: APICredentials) -> bool:
        """
        保存 API 凭证到加密文件
        
        参数:
        - credentials: API 凭证对象
        
        返回:
        - 是否保存成功
        """
        try:
            # 更新时间戳
            credentials.updated_at = datetime.now().isoformat()
            
            # 序列化并加密
            json_data = json.dumps(credentials.to_dict(), ensure_ascii=False)
            encrypted_data = self._encrypt(json_data)
            
            # 写入文件
            with open(SECRETS_FILE, 'w', encoding='utf-8') as f:
                f.write(encrypted_data)
            
            # 更新内存缓存
            self._credentials = credentials
            
            # 🔥 热更新：同步更新 os.environ（让其他模块立即生效）
            self._update_environ(credentials)
            
            logger.info(f"[ConfigManager] API 凭证已保存到 {SECRETS_FILE}")
            return True
            
        except Exception as e:
            logger.error(f"[ConfigManager] 保存凭证失败: {e}")
            return False
    
    def load_credentials(self) -> APICredentials:
        """
        加载 API 凭证
        
        优先级：
        1. 内存缓存
        2. 加密文件
        3. 环境变量
        
        返回:
        - API 凭证对象
        """
        # 1. 检查内存缓存
        if self._credentials:
            return self._credentials
        
        # 2. 尝试从文件加载
        if SECRETS_FILE.exists():
            try:
                with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
                    encrypted_data = f.read()
                
                json_data = self._decrypt(encrypted_data)
                data = json.loads(json_data)
                self._credentials = APICredentials.from_dict(data)
                
                logger.info(f"[ConfigManager] 从文件加载 API 凭证成功")
                return self._credentials
                
            except Exception as e:
                logger.warning(f"[ConfigManager] 从文件加载失败: {e}，回退到环境变量")
        
        # 3. 回退到环境变量
        self._credentials = APICredentials(
            trade_api_key=os.getenv("OKX_API_KEY", ""),
            trade_api_secret=os.getenv("OKX_API_SECRET", ""),
            trade_api_passphrase=os.getenv("OKX_API_PASSPHRASE", ""),
            market_api_key=os.getenv("MARKET_DATA_API_KEY", ""),
            market_api_secret=os.getenv("MARKET_DATA_SECRET", ""),
            market_api_passphrase=os.getenv("MARKET_DATA_PASSPHRASE", ""),
            updated_at="from_env"
        )
        
        logger.info("[ConfigManager] 从环境变量加载 API 凭证")
        return self._credentials
    
    def _update_environ(self, credentials: APICredentials):
        """
        热更新环境变量
        
        让其他模块（如 market_api.py）能立即读取到新配置
        """
        # 交易 Key
        if credentials.trade_api_key:
            os.environ["OKX_API_KEY"] = credentials.trade_api_key
        if credentials.trade_api_secret:
            os.environ["OKX_API_SECRET"] = credentials.trade_api_secret
        if credentials.trade_api_passphrase:
            os.environ["OKX_API_PASSPHRASE"] = credentials.trade_api_passphrase
        
        # 行情 Key
        if credentials.market_api_key:
            os.environ["MARKET_DATA_API_KEY"] = credentials.market_api_key
        if credentials.market_api_secret:
            os.environ["MARKET_DATA_SECRET"] = credentials.market_api_secret
        if credentials.market_api_passphrase:
            os.environ["MARKET_DATA_PASSPHRASE"] = credentials.market_api_passphrase
        
        logger.info("[ConfigManager] 环境变量已热更新")
    
    def get_trade_credentials(self) -> Tuple[str, str, str]:
        """
        获取交易专用凭证
        
        返回:
        - (api_key, secret, passphrase) 元组
        """
        creds = self.load_credentials()
        return (creds.trade_api_key, creds.trade_api_secret, creds.trade_api_passphrase)
    
    def get_market_credentials(self) -> Tuple[str, str, str, bool]:
        """
        获取行情专用凭证（优先行情 Key，回退交易 Key）
        
        返回:
        - (api_key, secret, passphrase, is_dedicated) 元组
        """
        creds = self.load_credentials()
        
        if creds.has_market_key():
            return (creds.market_api_key, creds.market_api_secret, 
                    creds.market_api_passphrase, True)
        else:
            return (creds.trade_api_key, creds.trade_api_secret, 
                    creds.trade_api_passphrase, False)
    
    def get_credentials_status(self) -> Dict[str, Any]:
        """
        获取凭证状态（用于 UI 显示）
        
        返回:
        - 状态字典
        """
        creds = self.load_credentials()
        return {
            "has_trade_key": creds.has_trade_key(),
            "has_market_key": creds.has_market_key(),
            "trade_key_tail": creds.get_trade_key_tail(),
            "market_key_tail": creds.get_market_key_tail(),
            "updated_at": creds.updated_at,
            "source": "file" if SECRETS_FILE.exists() else "env"
        }
    
    def clear_credentials(self) -> bool:
        """
        清除保存的凭证
        
        返回:
        - 是否清除成功
        """
        try:
            if SECRETS_FILE.exists():
                SECRETS_FILE.unlink()
            self._credentials = None
            logger.info("[ConfigManager] 凭证已清除")
            return True
        except Exception as e:
            logger.error(f"[ConfigManager] 清除凭证失败: {e}")
            return False
    
    def reload(self):
        """强制重新加载配置"""
        self._credentials = None
        self.load_credentials()


# 全局单例
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """获取配置管理器单例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


# ============ 便捷函数 ============

def save_api_credentials(
    trade_key: str = None,
    trade_secret: str = None,
    trade_passphrase: str = None,
    market_key: str = None,
    market_secret: str = None,
    market_passphrase: str = None
) -> bool:
    """
    保存 API 凭证（便捷函数）
    
    只更新传入的非空字段，保留其他字段
    """
    manager = get_config_manager()
    current = manager.load_credentials()
    
    # 合并更新
    new_creds = APICredentials(
        trade_api_key=trade_key if trade_key else current.trade_api_key,
        trade_api_secret=trade_secret if trade_secret else current.trade_api_secret,
        trade_api_passphrase=trade_passphrase if trade_passphrase else current.trade_api_passphrase,
        market_api_key=market_key if market_key else current.market_api_key,
        market_api_secret=market_secret if market_secret else current.market_api_secret,
        market_api_passphrase=market_passphrase if market_passphrase else current.market_api_passphrase,
    )
    
    return manager.save_credentials(new_creds)


def get_api_status() -> Dict[str, Any]:
    """获取 API 配置状态（便捷函数）"""
    return get_config_manager().get_credentials_status()


def mask_key(key: str, show_chars: int = 4) -> str:
    """
    掩码处理 Key（用于显示）
    
    示例: "abcdefgh12345678" -> "****5678"
    """
    if not key:
        return ""
    if len(key) <= show_chars:
        return "*" * len(key)
    return "*" * (len(key) - show_chars) + key[-show_chars:]
