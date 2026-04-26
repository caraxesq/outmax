from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.manager import AccountManager
from app.config import Settings
from app.db.models import Message, Recipient, utcnow
from app.settings.service import SettingsService

logger = logging.getLogger(__name__)

try:
    from telethon.errors import FloodWaitError
except Exception:  # pragma: no cover
    class FloodWaitError(Exception):  # type: ignore[no-redef]
        def __init__(self, seconds: int = 0):
            self.seconds = seconds


class MessageWorker:
    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        account_manager: AccountManager,
        settings_service: SettingsService | None = None,
        sleep_func=asyncio.sleep,
    ):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.account_manager = account_manager
        self.settings_service = settings_service or SettingsService(sessionmaker, settings)
        self.sleep_func = sleep_func
        self._running = False

    async def start(self) -> None:
        self._running = True
        while self._running:
            did_work = await self.run_once()
            if not did_work:
                await self.sleep_func(self.settings.worker_idle_seconds)

    def stop(self) -> None:
        self._running = False

    async def run_once(self) -> bool:
        await self.account_manager.refresh_limited_accounts()
        async with self.sessionmaker() as session:
            message = await session.scalar(
                select(Message)
                .where(Message.status == "pending", Message.scheduled_at <= utcnow())
                .order_by(Message.created_at)
                .limit(1)
            )
            if message is None:
                return False
            account = await self.account_manager.pick_available_account()
            if account is None:
                return False
            recipient = await session.get(Recipient, message.recipient_id)
            if recipient is None or recipient.do_not_contact:
                message.status = "skipped"
                message.last_error = "recipient unavailable or do_not_contact"
                await session.commit()
                return True
            peer: int | str | None = recipient.user_id or recipient.username
            if peer is None:
                message.status = "skipped"
                message.last_error = "recipient has no user_id or username"
                await session.commit()
                return True
            message.status = "sending"
            message.account_id = account.id
            message.attempts += 1
            await session.commit()

        try:
            runtime_settings = await self.settings_service.get()
            await self.account_manager.send_message(account, peer, message.text)
            await self.account_manager.mark_sent(
                account.id,
                cooldown_after_messages=runtime_settings.cooldown_after_messages,
                cooldown_seconds=runtime_settings.cooldown_seconds,
            )
            async with self.sessionmaker() as session:
                fresh = await session.get(Message, message.id)
                if fresh:
                    fresh.status = "sent"
                    fresh.sent_at = utcnow()
                    fresh.last_error = None
                    await session.commit()
            await self.sleep_func(runtime_settings.send_delay_seconds)
            return True
        except FloodWaitError as exc:
            seconds = int(getattr(exc, "seconds", 60) or 60)
            await self.account_manager.mark_limited(account.id, seconds, f"FloodWait {seconds}s")
            await self._reschedule(message.id, f"FloodWait {seconds}s", seconds)
            return True
        except Exception as exc:
            logger.warning("Message send failed: %s", exc)
            await self._handle_failure(message.id, str(exc))
            return True

    async def _reschedule(self, message_id: int, error: str, seconds: int) -> None:
        async with self.sessionmaker() as session:
            message = await session.get(Message, message_id)
            if message:
                message.status = "pending"
                message.last_error = error
                message.scheduled_at = utcnow() + timedelta(seconds=seconds)
                await session.commit()

    async def _handle_failure(self, message_id: int, error: str) -> None:
        async with self.sessionmaker() as session:
            message = await session.get(Message, message_id)
            if message is None:
                return
            if message.attempts >= self.settings.max_retries:
                message.status = "failed"
            else:
                message.status = "pending"
                message.scheduled_at = utcnow() + timedelta(seconds=60 * message.attempts)
            message.last_error = error
            await session.commit()
