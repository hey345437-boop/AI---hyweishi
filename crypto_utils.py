import os
import base64
import hashlib
import logging
from typing import Tuple, Dict

logger = logging.getLogger(__name__)

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:
    AESGCM = None

# 不安全的默认密码
INSECURE_DEFAULT_PASS = 'default_insecure_pass'


def _is_production_mode() -> bool:
    """检查是否为生产模式"""
    run_mode = os.getenv('RUN_MODE', '').lower()
    production = os.getenv('PRODUCTION', '').lower()
    return run_mode == 'live' or production == 'true'


def _derive_key_from_env() -> bytes:
    """Derive a 32-byte key from environment variable MYTRADINGBOT_CIPHER_KEY.
    If not provided, derive from MYTRADINGBOT_MASTER_PASS (SHA256).
    
    Raises:
        RuntimeError: 在生产模式下使用默认密钥时抛出
    """
    b64 = os.getenv('MYTRADINGBOT_CIPHER_KEY')
    if b64:
        try:
            key = base64.b64decode(b64)
            if len(key) not in (16, 24, 32):
                # ensure 32 bytes
                key = hashlib.sha256(key).digest()
            return key
        except Exception:
            pass
    
    passwd = os.getenv('MYTRADINGBOT_MASTER_PASS', INSECURE_DEFAULT_PASS)
    
    # 检查是否使用了不安全的默认密码
    if passwd == INSECURE_DEFAULT_PASS:
        if _is_production_mode():
            raise RuntimeError(
                "[ERROR] Security Error: Cannot use default encryption key in production mode!\n"
                "Please set MYTRADINGBOT_MASTER_PASS environment variable to a secure password.\n"
                "Example: export MYTRADINGBOT_MASTER_PASS='your_secure_password_here'"
            )
        else:
            logger.warning(
                "[WARNING] Using default encryption key, for development only! "
                "Please set MYTRADINGBOT_MASTER_PASS environment variable."
            )
    
    return hashlib.sha256(passwd.encode('utf-8')).digest()


def encrypt_bytes(plaintext: bytes) -> Dict[str, str]:
    """Encrypt bytes using AES-GCM. Returns base64-encoded dict {ciphertext, iv}."""
    if AESGCM is None:
        raise RuntimeError('cryptography AESGCM not available')
    key = _derive_key_from_env()
    aesgcm = AESGCM(key)
    iv = os.urandom(12)
    ct = aesgcm.encrypt(iv, plaintext, None)
    # AESGCM encrypt returns ciphertext||tag; we store iv and ct
    return {
        'ciphertext': base64.b64encode(ct).decode('ascii'),
        'iv': base64.b64encode(iv).decode('ascii')
    }


def decrypt_bytes(ciphertext_b64: str, iv_b64: str) -> bytes:
    if AESGCM is None:
        raise RuntimeError('cryptography AESGCM not available')
    key = _derive_key_from_env()
    aesgcm = AESGCM(key)
    ct = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)
    pt = aesgcm.decrypt(iv, ct, None)
    return pt


def encrypt_text(text: str) -> Dict[str, str]:
    return encrypt_bytes(text.encode('utf-8'))


def decrypt_text(ciphertext_b64: str, iv_b64: str) -> str:
    return decrypt_bytes(ciphertext_b64, iv_b64).decode('utf-8')
