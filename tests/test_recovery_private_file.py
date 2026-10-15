"""복구 키의 실제 권한과 실패 시 비밀 미기록 경계를 검증한다."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pytest

from src.llm_batch.ledger.private_file import create_private_file, private_file_permissions_ok, restrict_private_file
from src.llm_batch.ledger.recovery_activation import (
    RecoveryActivationError, load_or_create_recovery_activation_hmac_key,
)


def test_restricted_file_has_platform_private_permissions():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "empty.key"
        path.touch()
        restrict_private_file(path)
        assert private_file_permissions_ok(path)
        assert path.read_bytes() == b""


def test_new_file_is_private_at_creation_and_cannot_replace_existing_file():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "new.key"
        descriptor = create_private_file(path)
        try:
            assert private_file_permissions_ok(path)
            os.write(descriptor, b"test sentinel")
        finally:
            os.close(descriptor)
        with pytest.raises(OSError):
            create_private_file(path)
        assert path.read_bytes() == b"test sentinel"


def test_key_is_private_before_any_secret_write():
    with TemporaryDirectory() as tmp:
        key_path = Path(tmp) / "recovery.key"
        native_write = os.write
        observations = []

        def checked_write(fd, data):
            temporary = list(Path(tmp).glob(".*.tmp"))
            assert len(temporary) == 1
            observations.append(private_file_permissions_ok(temporary[0]))
            assert observations[-1]
            return native_write(fd, data)

        with patch("src.llm_batch.ledger.recovery_activation.os.write", side_effect=checked_write):
            first = load_or_create_recovery_activation_hmac_key(key_path)
        assert observations
        assert first == load_or_create_recovery_activation_hmac_key(key_path)
        assert private_file_permissions_ok(key_path)


def test_permission_failure_never_publishes_key_or_writes_secret():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "recovery.key"
        with patch("src.llm_batch.ledger.recovery_activation.restrict_private_file", side_effect=OSError("denied")), patch("src.llm_batch.ledger.recovery_activation.os.write") as write:
            with pytest.raises(RecoveryActivationError, match="denied"):
                load_or_create_recovery_activation_hmac_key(path)
        write.assert_not_called()
        assert not path.exists()
        assert not list(Path(tmp).glob(".*.tmp"))


def test_hardlinked_existing_key_is_rejected_without_modification():
    with TemporaryDirectory() as tmp:
        original = Path(tmp) / "original.key"
        original.write_text("ab" * 32 + "\n", encoding="ascii")
        linked = Path(tmp) / "linked.key"
        os.link(original, linked)
        before = original.read_bytes()
        with pytest.raises(RecoveryActivationError, match="regular unlinked"):
            load_or_create_recovery_activation_hmac_key(linked)
        assert original.read_bytes() == linked.read_bytes() == before
