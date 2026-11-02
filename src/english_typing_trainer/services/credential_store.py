from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes
from typing import Protocol


class CredentialStore(Protocol):
    def get(self) -> str | None: ...
    def set(self, secret: str) -> None: ...
    def delete(self) -> None: ...


class MemoryCredentialStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def get(self) -> str | None:
        return self.value

    def set(self, secret: str) -> None:
        self.value = secret

    def delete(self) -> None:
        self.value = None


class FallbackCredentialStore:
    """Reads legacy credentials once without deleting them, then writes only to the new target."""
    def __init__(self, primary: CredentialStore, legacy: CredentialStore | None = None) -> None:
        self.primary=primary; self.legacy=legacy

    def get(self) -> str | None:
        value=self.primary.get()
        if value or self.legacy is None:return value
        value=self.legacy.get()
        if value:self.primary.set(value)
        return value

    def set(self, secret: str) -> None: self.primary.set(secret)
    def delete(self) -> None: self.primary.delete()


class WindowsCredentialStore:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD), ("Type", wintypes.DWORD), ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR), ("LastWritten", wintypes.FILETIME), ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)), ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD), ("Attributes", wintypes.LPVOID),
            ("TargetAlias", wintypes.LPWSTR), ("UserName", wintypes.LPWSTR),
        ]

    def __init__(self, target_name: str = "EnglishTypingTrainer/DeepSeekAPI", user_name: str = "DeepSeek API") -> None:
        if os.name != "nt":
            raise OSError("Windows Credential Manager 仅支持 Windows。")
        self.target_name = target_name
        self.user_name = user_name
        self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        pointer_type = ctypes.POINTER(self.CREDENTIALW)
        self._advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(pointer_type)]
        self._advapi.CredReadW.restype = wintypes.BOOL
        self._advapi.CredWriteW.argtypes = [ctypes.POINTER(self.CREDENTIALW), wintypes.DWORD]
        self._advapi.CredWriteW.restype = wintypes.BOOL
        self._advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._advapi.CredDeleteW.restype = wintypes.BOOL
        self._advapi.CredFree.argtypes = [wintypes.LPVOID]

    def get(self) -> str | None:
        pointer = ctypes.POINTER(self.CREDENTIALW)()
        if not self._advapi.CredReadW(self.target_name, self.CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            if ctypes.get_last_error() == self.ERROR_NOT_FOUND:
                return None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            credential = pointer.contents
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-16-le")
        finally:
            self._advapi.CredFree(pointer)

    def set(self, secret: str) -> None:
        encoded = secret.encode("utf-16-le")
        blob = (ctypes.c_ubyte * len(encoded)).from_buffer_copy(encoded)
        credential = self.CREDENTIALW()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = self.target_name
        credential.CredentialBlobSize = len(encoded)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = self.user_name
        if not self._advapi.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def delete(self) -> None:
        if not self._advapi.CredDeleteW(self.target_name, self.CRED_TYPE_GENERIC, 0):
            if ctypes.get_last_error() != self.ERROR_NOT_FOUND:
                raise ctypes.WinError(ctypes.get_last_error())


class MacOSCredentialStore:
    """Uses only the native Keychain backend; no plaintext or memory fallback."""

    def __init__(self, service_name: str, user_name: str, *, backend=None) -> None:
        self.service_name = service_name
        self.user_name = user_name
        self._backend = backend

    def _keychain(self):
        if self._backend is None:
            try:
                from keyring.backends.macOS import Keyring
                self._backend = Keyring()
            except Exception:
                raise OSError("无法访问 macOS 钥匙串，请检查系统权限。") from None
        return self._backend

    def get(self) -> str | None:
        try:
            return self._keychain().get_password(self.service_name, self.user_name)
        except Exception:
            raise OSError("无法读取 macOS 钥匙串，请解锁钥匙串后重试。") from None

    def set(self, secret: str) -> None:
        try:
            self._keychain().set_password(self.service_name, self.user_name, secret)
        except Exception:
            raise OSError("无法保存到 macOS 钥匙串，请检查系统授权后重试。") from None

    def delete(self) -> None:
        try:
            if self.get() is not None:
                self._keychain().delete_password(self.service_name, self.user_name)
        except Exception:
            raise OSError("无法删除 macOS 钥匙串中的凭据，请检查系统授权。") from None


def create_credential_store(service: str, *, platform: str | None = None) -> CredentialStore:
    platform = platform or sys.platform
    if service not in {"deepseek", "tts"}:
        raise ValueError("未知凭据服务。")
    target, user, legacy = (
        ("English Studio/DeepSeek API", "DeepSeek API", "EnglishTypingTrainer/DeepSeekAPI")
        if service == "deepseek"
        else ("English Studio/MiniMax TTS", "MiniMax TTS", "EnglishTypingTrainer/MiniMax TTS")
    )
    if platform == "darwin":
        return MacOSCredentialStore(target, user)
    if platform == "win32":
        return FallbackCredentialStore(WindowsCredentialStore(target, user), WindowsCredentialStore(legacy, user))
    raise OSError("当前系统没有受支持的安全凭据存储。")


def credential_storage_label() -> str:
    return "macOS 钥匙串" if sys.platform == "darwin" else "Windows 凭据管理器"


def mask_api_key(api_key: str | None) -> str:
    if not api_key:
        return "未保存"
    suffix = api_key[-4:] if len(api_key) >= 4 else api_key
    return f"sk-****{suffix}"


def mask_secret(secret: str | None) -> str:
    if not secret:
        return "未保存"
    suffix = secret[-4:] if len(secret) >= 4 else secret
    return f"••••••••{suffix}"
