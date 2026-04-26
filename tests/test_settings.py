from __future__ import annotations

from app.db.models import AppSetting
from app.settings.service import RuntimeSettings, SettingsService


async def test_runtime_settings_persist_and_merge_with_defaults(sessionmaker, settings):
    service = SettingsService(sessionmaker, settings)

    await service.update(send_per_hour=12, delay_minutes=5, cooldown_after_messages=20, cooldown_minutes=40)
    runtime = await service.get()

    assert runtime == RuntimeSettings(
        send_per_hour=12,
        delay_minutes=5,
        cooldown_after_messages=20,
        cooldown_minutes=40,
    )
