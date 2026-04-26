from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_admin_ids_parse(settings):
    assert settings.admin_id_set == {1, 2}
    assert settings.telegram_api_ready is True


def test_invalid_delay_rejected(tmp_path):
    with pytest.raises(ValidationError):
        Settings(
            BOT_TOKEN="x",
            ADMIN_IDS="1",
            API_ID=1,
            API_HASH="h",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            SESSIONS_DIR=tmp_path / "sessions",
            LOG_DIR=tmp_path / "logs",
            MIN_SEND_DELAY=10,
            MAX_SEND_DELAY=1,
        )
