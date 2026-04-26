from __future__ import annotations

import html
import json
import logging
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import Reply

logger = logging.getLogger(__name__)

try:
    from telethon import events
except Exception:  # pragma: no cover
    events = None  # type: ignore[assignment]


class ReplyListener:
    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession], bot: Bot):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.bot = bot

    def attach(self, account_id: int, client: Any) -> None:
        if events is None:
            return

        @client.on(events.NewMessage(incoming=True))
        async def _handler(event):  # noqa: ANN001
            sender = await event.get_sender()
            sender_id = getattr(sender, "id", None)
            username = getattr(sender, "username", None)
            text = event.raw_text or ""
            async with self.sessionmaker() as session:
                session.add(
                    Reply(
                        account_id=account_id,
                        sender_id=sender_id,
                        sender_username=username,
                        text=text,
                        raw_json=self._safe_raw(event),
                    )
                )
                await session.commit()
            await self.notify_admins(account_id, sender_id, username, text)

    async def notify_admins(self, account_id: int, sender_id: int | None, username: str | None, text: str) -> None:
        link = f"https://t.me/{username}" if username else (f"tg://user?id={sender_id}" if sender_id else "unknown sender")
        body = (
            "<b>New Telegram reply</b>\n"
            f"Account ID: <code>{account_id}</code>\n"
            f"Sender: <a href=\"{html.escape(link)}\">{html.escape(username or str(sender_id or 'unknown'))}</a>\n"
            f"Text: {html.escape(text[:3500])}"
        )
        for admin_id in self.settings.admin_id_set:
            try:
                await self.bot.send_message(admin_id, body, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                logger.exception("Could not notify admin %s about reply", admin_id)

    @staticmethod
    def _safe_raw(event) -> dict | None:  # noqa: ANN001
        try:
            return json.loads(event.message.to_json())
        except Exception:
            return None
