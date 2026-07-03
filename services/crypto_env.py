import base64
import hashlib
import json
import os
import secrets
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =========================
# 環境變數主密鑰加密工具
# =========================
# 設計目的：
# - Supabase 只保存密文
# - 程式讀取後自動解密給原本流程使用
# - 不需要使用者每次 /解鎖
# - APP_ENCRYPTION_SECRET 只放 Render Environment Variables

PREFIX = "ENCv1:"
ENV_NAME = "APP_ENCRYPTION_SECRET"
NONCE_LENGTH = 12


class EnvCryptoError(Exception):
    """環境密鑰缺失、密文格式錯誤或解密失敗時使用。"""


def _get_master_key() -> bytes:
    secret = os.getenv(ENV_NAME)

    if not secret:
        raise EnvCryptoError(f"{ENV_NAME} is not set")

    # 允許你在 Render 放任意長度字串，這裡固定壓成 AES-256 key。
    return hashlib.sha256(secret.encode("utf-8")).digest()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text.encode("utf-8"))


def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_text(plain_text: Any, aad: str = "") -> str:
    """
    把文字加密成可直接存進 TEXT 欄位的字串。

    aad：不加密但會參與驗證，用來防止密文被搬到不該放的位置仍可解密。
    """
    if plain_text is None:
        plain_text = ""

    plain_text = str(plain_text)

    # 避免重複加密。
    if is_encrypted(plain_text):
        return plain_text

    key = _get_master_key()
    aesgcm = AESGCM(key)
    nonce = secrets.token_bytes(NONCE_LENGTH)

    ciphertext = aesgcm.encrypt(
        nonce,
        plain_text.encode("utf-8"),
        str(aad or "").encode("utf-8"),
    )

    payload = {
        "v": 1,
        "n": _b64e(nonce),
        "c": _b64e(ciphertext),
    }

    return PREFIX + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def decrypt_text(value: Any, aad: str = "") -> str:
    """
    把 ENCv1 密文解回明文。

    若遇到舊資料明文，會原樣回傳，讓舊資料在遷移前仍能使用。
    """
    if value is None:
        return ""

    value = str(value)

    # 舊明文資料：先照常回傳，避免一部署就讀不到舊資料。
    if not is_encrypted(value):
        return value

    try:
        raw = value[len(PREFIX):]
        payload = json.loads(raw)

        nonce = _b64d(payload["n"])
        ciphertext = _b64d(payload["c"])

        key = _get_master_key()
        aesgcm = AESGCM(key)

        plain = aesgcm.decrypt(
            nonce,
            ciphertext,
            str(aad or "").encode("utf-8"),
        )

        return plain.decode("utf-8")

    except (KeyError, json.JSONDecodeError, InvalidTag, ValueError) as exc:
        raise EnvCryptoError("decrypt_text failed") from exc


def aad_for(table: str, field: str, *parts: Any) -> str:
    """統一產生 AAD，讓不同 table / 欄位的密文不能任意混用。"""
    safe_parts = [str(p) for p in parts]
    return ":".join([str(table), str(field), *safe_parts])
