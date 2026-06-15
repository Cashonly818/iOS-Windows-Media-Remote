"""
认证管理器 - PIN 码验证
首次运行时自动生成 4 位数字 PIN，存储在本地文件中
用户在手机浏览器输入 PIN 后获取 token，后续请求携带 token
"""

import os
import hashlib
import secrets
import time

PIN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'pin.conf')
TOKEN_EXPIRE_SECONDS = 86400 * 7  # token 有效期 7 天


class AuthManager:
    """PIN 码认证管理器"""

    def __init__(self):
        self._pin_hash: str = ''
        self._tokens: dict = {}  # token_hash -> expire_time
        self._load_pin()

    def _load_pin(self):
        """从文件加载 PIN 哈希"""
        if os.path.exists(PIN_FILE):
            try:
                with open(PIN_FILE, 'r') as f:
                    self._pin_hash = f.read().strip()
                if self._pin_hash:
                    print(f"[Auth] PIN 验证已启用")
            except Exception:
                pass

    def _save_pin(self):
        """保存 PIN 哈希到文件"""
        try:
            with open(PIN_FILE, 'w') as f:
                f.write(self._pin_hash)
            # 设置文件为隐藏 (Windows)
            try:
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(PIN_FILE, 2)
            except Exception:
                pass
        except Exception as e:
            print(f"[Auth] 无法保存 PIN: {e}")

    def is_pin_set(self) -> bool:
        """是否已设置 PIN"""
        return bool(self._pin_hash)

    def setup_pin(self, pin: str) -> bool:
        """设置新 PIN (4位数字)"""
        pin = pin.strip()
        if len(pin) != 4 or not pin.isdigit():
            return False
        self._pin_hash = self._hash(pin)
        self._save_pin()
        return True

    def verify_pin(self, pin: str) -> bool:
        """验证 PIN 是否正确"""
        if not self._pin_hash:
            return True  # 未设置 PIN 时无需验证
        pin = pin.strip()
        return self._hash(pin) == self._pin_hash

    def generate_token(self) -> str:
        """生成一个新的认证 token"""
        token = secrets.token_hex(16)
        token_hash = self._hash(token)
        self._tokens[token_hash] = time.time() + TOKEN_EXPIRE_SECONDS
        # 清理过期 token
        self._cleanup_tokens()
        return token

    def verify_token(self, token: str) -> bool:
        """验证 token 是否有效"""
        if not self._pin_hash:
            return True  # 未设置 PIN 时放行所有请求
        if not token:
            return False
        token_hash = self._hash(token)
        expire = self._tokens.get(token_hash, 0)
        if expire > time.time():
            # 刷新过期时间
            self._tokens[token_hash] = time.time() + TOKEN_EXPIRE_SECONDS
            return True
        return False

    def get_pin_hint(self) -> str:
        """获取 PIN 提示"""
        if not self._pin_hash:
            return ''
        return '请输入 4 位数字 PIN'

    def _hash(self, s: str) -> str:
        """SHA256 哈希"""
        return hashlib.sha256(s.encode()).hexdigest()

    def _cleanup_tokens(self):
        """清理过期 token"""
        now = time.time()
        expired = [k for k, v in self._tokens.items() if v < now]
        for k in expired:
            del self._tokens[k]
