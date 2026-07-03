import base64
import json
import secrets
from typing import Any, Dict

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# =========================
# 使用者端解鎖碼加密工具
# =========================
# 設計原則：
# 1. 伺服器不需要 ENCRYPTION_KEY
# 2. Render / 環境變數不保存解密密鑰
# 3. DB 不保存明文解鎖碼
# 4. 解鎖碼遺失，密文就無法還原
# 5. 加密單位是 JSON payload，方便你開發階段調整欄位

KDF_ITERATIONS = 600_000
KEY_LENGTH = 32
SALT_LENGTH = 16
NONCE_LENGTH = 12
VERSION = 1


class UnlockCodeError(Exception):
    """解鎖碼錯誤、密文被改過，或 AAD 條件不一致時丟出。"""


def generate_unlock_code() -> str:
    """
    產生給使用者保存的解鎖碼。

    注意：
    - 只顯示給使用者一次
    - 不要存 DB 明文
    - 使用者遺失後，原密文無法救回
    """

    return secrets.token_urlsafe(32)


def build_aad(
    user_id: Any,
    bot_id: Any,
    chat_id: Any,
    data_type: str,
    record_key: str = "default",
) -> str:
    """
    AAD 不會被加密，但會被驗證。
    用途：防止有人把 A 使用者的密文搬到 B 使用者底下混用。
    """

    return f"{user_id}:{bot_id}:{chat_id}:{data_type}:{record_key}"


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _b64_decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("utf-8"))


def derive_key(unlock_code: str, salt: bytes) -> bytes:
    """由使用者解鎖碼 + salt 派生 AES-256 key。"""

    if not unlock_code:
        raise ValueError("unlock_code is required")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_LENGTH,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )

    return kdf.derive(str(unlock_code).encode("utf-8"))


def encrypt_payload(unlock_code: str, payload: Dict[str, Any], aad: str = "") -> Dict[str, Any]:
    """
    加密一包 JSON payload。

    回傳格式可直接存進 PostgreSQL JSONB。
    """

    if payload is None:
        payload = {}

    salt = secrets.token_bytes(SALT_LENGTH)
    nonce = secrets.token_bytes(NONCE_LENGTH)
    key = derive_key(unlock_code, salt)

    plaintext = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")

    ciphertext = AESGCM(key).encrypt(
        nonce,
        plaintext,
        aad.encode("utf-8"),
    )

    return {
        "v": VERSION,
        "kdf": "PBKDF2HMAC-SHA256",
        "iterations": KDF_ITERATIONS,
        "salt": _b64_encode(salt),
        "nonce": _b64_encode(nonce),
        "ciphertext": _b64_encode(ciphertext),
    }


def decrypt_payload(unlock_code: str, encrypted_data: Dict[str, Any], aad: str = "") -> Dict[str, Any]:
    """
    解密 JSON payload。

    解鎖碼錯誤、AAD 不一致、密文被改過，都會丟 UnlockCodeError。
    """

    if not encrypted_data:
        raise UnlockCodeError("empty encrypted_data")

    try:
        salt = _b64_decode(encrypted_data["salt"])
        nonce = _b64_decode(encrypted_data["nonce"])
        ciphertext = _b64_decode(encrypted_data["ciphertext"])

        iterations = int(encrypted_data.get("iterations") or KDF_ITERATIONS)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LENGTH,
            salt=salt,
            iterations=iterations,
        )

        key = kdf.derive(str(unlock_code).encode("utf-8"))

        plaintext = AESGCM(key).decrypt(
            nonce,
            ciphertext,
            aad.encode("utf-8"),
        )

        data = json.loads(plaintext.decode("utf-8"))

        if not isinstance(data, dict):
            raise UnlockCodeError("payload is not a JSON object")

        return data

    except (InvalidTag, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise UnlockCodeError("解鎖碼錯誤、資料歸屬不符，或密文已被改動") from exc
