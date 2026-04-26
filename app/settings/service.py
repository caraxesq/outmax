from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import AppSetting


@dataclass(frozen=True)
class RuntimeSettings:
    send_per_hour: int = 12
    delay_minutes: int = 5
    cooldown_after_messages: int = 20
    cooldown_minutes: int = 40

    @property
    def send_delay_seconds(self) -> int:
        hourly_delay = 3600 // max(self.send_per_hour, 1)
        manual_delay = self.delay_minutes * 60
        return max(hourly_delay, manual_delay)

    @property
    def cooldown_seconds(self) -> int:
        return self.cooldown_minutes * 60


class SettingsService:
    KEYS = {
        "send_per_hour": "send_per_hour",
        "delay_minutes": "delay_minutes",
        "cooldown_after_messages": "cooldown_after_messages",
        "cooldown_minutes": "cooldown_minutes",
    }

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], settings: Settings):
        self.sessionmaker = sessionmaker
        self.settings = settings

    def defaults(self) -> RuntimeSettings:
        return RuntimeSettings(
            send_per_hour=12,
            delay_minutes=5,
            cooldown_after_messages=self.settings.cooldown_after_messages or 20,
            cooldown_minutes=max(1, self.settings.cooldown_seconds // 60) if self.settings.cooldown_seconds else 40,
        )

    async def get(self) -> RuntimeSettings:
        defaults = self.defaults()
        async with self.sessionmaker() as session:
            rows = await session.scalars(select(AppSetting))
            values = {row.key: row.value for row in rows}
        return RuntimeSettings(
            send_per_hour=self._int(values.get("send_per_hour"), defaults.send_per_hour, minimum=1),
            delay_minutes=self._int(values.get("delay_minutes"), defaults.delay_minutes, minimum=1),
            cooldown_after_messages=self._int(
                values.get("cooldown_after_messages"),
                defaults.cooldown_after_messages,
                minimum=1,
            ),
            cooldown_minutes=self._int(values.get("cooldown_minutes"), defaults.cooldown_minutes, minimum=1),
        )

    async def update(
        self,
        *,
        send_per_hour: int | None = None,
        delay_minutes: int | None = None,
        cooldown_after_messages: int | None = None,
        cooldown_minutes: int | None = None,
    ) -> RuntimeSettings:
        updates = {
            "send_per_hour": send_per_hour,
            "delay_minutes": delay_minutes,
            "cooldown_after_messages": cooldown_after_messages,
            "cooldown_minutes": cooldown_minutes,
        }
        async with self.sessionmaker() as session:
            for key, value in updates.items():
                if value is None:
                    continue
                cleaned = max(1, int(value))
                setting = await session.get(AppSetting, key)
                if setting is None:
                    session.add(AppSetting(key=key, value=str(cleaned)))
                else:
                    setting.value = str(cleaned)
            await session.commit()
        return await self.get()

    @staticmethod
    def _int(value: str | None, default: int, minimum: int) -> int:
        if value is None:
            return default
        try:
            return max(minimum, int(value))
        except ValueError:
            return default
