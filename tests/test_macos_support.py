from __future__ import annotations

from pathlib import Path
import sys
from uuid import uuid4

import pytest

from english_typing_trainer.services.app_paths import AppPathService
from english_typing_trainer.services.credential_store import MacOSCredentialStore, create_credential_store


def test_macos_data_path_uses_application_support_and_ignores_windows_environment(monkeypatch, tmp_path):
    monkeypatch.delenv("ENGLISH_TYPING_TRAINER_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "windows"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    paths = AppPathService(platform="darwin").ensure_directories()
    assert paths.data_dir == tmp_path / "home" / "Library" / "Application Support" / "EnglishStudio"
    assert paths.logs_dir.is_dir() and paths.audio_cache_dir.is_dir()
    assert not (tmp_path / "windows").exists()


def test_macos_explicit_data_directory_and_environment_override_take_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGLISH_TYPING_TRAINER_DATA_DIR", str(tmp_path / "override"))
    assert AppPathService(platform="darwin").get_paths().data_dir == tmp_path / "override"
    assert AppPathService(tmp_path / "isolated", platform="darwin").get_paths().data_dir == tmp_path / "isolated"


def test_macos_never_attempts_windows_legacy_migration(monkeypatch, tmp_path):
    monkeypatch.delenv("ENGLISH_TYPING_TRAINER_DATA_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(AppPathService, "_migrate_legacy_default_data", lambda _: pytest.fail("Windows migration on Mac"))
    AppPathService(platform="darwin").ensure_directories()


class Backend:
    def __init__(self):
        self.values = {}

    def get_password(self, service, user):
        return self.values.get((service, user))

    def set_password(self, service, user, password):
        self.values[service, user] = password

    def delete_password(self, service, user):
        del self.values[service, user]


def test_keychain_roundtrip_uses_distinct_services_and_idempotent_delete():
    backend = Backend()
    first = MacOSCredentialStore("deepseek", "key", backend=backend)
    second = MacOSCredentialStore("tts", "key", backend=backend)
    assert first.get() is None
    first.set("mock-deepseek-key")
    second.set("mock-tts-key")
    assert first.get() == "mock-deepseek-key"
    assert second.get() == "mock-tts-key"
    first.delete()
    first.delete()
    assert second.get() == "mock-tts-key"


@pytest.mark.parametrize("operation", ["get", "set", "delete"])
def test_keychain_errors_never_expose_secret_or_backend_message(operation):
    class BrokenBackend:
        def get_password(self, *_args):
            raise RuntimeError("backend-error-with-mock-secret")

        def set_password(self, *_args):
            raise RuntimeError("backend-error-with-mock-secret")

    store = MacOSCredentialStore("service", "user", backend=BrokenBackend())
    with pytest.raises(OSError) as error:
        getattr(store, operation)(*( ["mock-secret"] if operation == "set" else []))
    assert "mock-secret" not in str(error.value)
    assert "钥匙串" in str(error.value)


def test_macos_factory_does_not_instantiate_windows_store(monkeypatch):
    import english_typing_trainer.services.credential_store as module
    monkeypatch.setattr(module, "WindowsCredentialStore", lambda *_: pytest.fail("Windows API on Mac"))
    assert isinstance(create_credential_store("deepseek", platform="darwin"), MacOSCredentialStore)
    assert isinstance(create_credential_store("tts", platform="darwin"), MacOSCredentialStore)


def test_windows_factory_preserves_both_legacy_credential_targets(monkeypatch):
    import english_typing_trainer.services.credential_store as module
    calls = []
    monkeypatch.setattr(module, "WindowsCredentialStore", lambda target, user: calls.append((target, user)))
    create_credential_store("deepseek", platform="win32")
    create_credential_store("tts", platform="win32")
    assert [target for target, _ in calls] == [
        "English Studio/DeepSeek API", "EnglishTypingTrainer/DeepSeekAPI",
        "English Studio/MiniMax TTS", "EnglishTypingTrainer/MiniMax TTS",
    ]


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires native macOS Keychain")
def test_native_macos_keychain_roundtrip():
    store = MacOSCredentialStore(f"Shiju Build Test/{uuid4()}", "isolated-test")
    try:
        assert store.get() is None
        store.set("isolated-build-test-not-a-real-api-key")
        assert store.get() == "isolated-build-test-not-a-real-api-key"
    finally:
        store.delete()


def test_macos_bundle_audit_rejects_user_database(tmp_path):
    from scripts.package_macos import audit_bundle
    (tmp_path / "typing_trainer.db").write_bytes(b"private")
    with pytest.raises(RuntimeError, match="Unexpected personal/runtime files"):
        audit_bundle(tmp_path)


def test_command_and_control_shortcuts_do_not_reach_typing_handlers(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication
    from english_typing_trainer.ui.practice_view import PracticeInputEdit
    app = QApplication.instance() or QApplication([])
    editor = PracticeInputEdit()
    received = []
    editor.key_received.connect(received.append)
    for modifier in (Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.MetaModifier):
        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, modifier, "c"))
        editor.keyPressEvent(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, modifier, "v"))
    assert received == []
    editor.close()


@pytest.mark.parametrize("platform, override", [("darwin", ""), ("darwin", "custom.pem"), ("win32", "")])
def test_bundled_macos_certificates_preserve_explicit_overrides(monkeypatch, platform, override):
    from types import SimpleNamespace
    from english_typing_trainer.services import network_security

    monkeypatch.setattr(network_security.sys, "platform", platform)
    monkeypatch.setenv("SSL_CERT_FILE", override)
    monkeypatch.setitem(sys.modules, "certifi", SimpleNamespace(where=lambda: "bundled-cacert.pem"))
    network_security.configure_https_certificates()
    import os
    assert os.environ["SSL_CERT_FILE"] == ("bundled-cacert.pem" if platform == "darwin" and not override else override)
