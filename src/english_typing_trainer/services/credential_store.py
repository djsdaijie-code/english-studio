from __future__ import annotations

import ctypes
import os
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
