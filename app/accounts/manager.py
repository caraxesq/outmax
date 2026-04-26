from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import Account, utcnow

logger = logging.getLogger(__name__)

try:
    from telethon import TelegramClient
except Exception:  # pragma: no cover - import guard for static tests without deps
    TelegramClient = None  # type: ignore[assignment]


def normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def choose_account(accounts: list[Account], now: datetime | None = None) -> Account | None:
    now = now or utcnow()
    eligible: list[Account] = []
    for account in accounts:
        cooldown_until = normalize_datetime(account.cooldown_until)
        limited_until = normalize_datetime(account.limited_until)
        if not account.enabled or account.status != "active":
            continue
        if account.sent_today >= account.daily_limit:
            continue
        if cooldown_until and cooldown_until > now:
            continue
        if limited_until and limited_until > now:
            continue
        eligible.append(account)
    if not eligible:
        return None
    return sorted(eligible, key=lambda item: (item.sent_today, normalize_datetime(item.last_sent_at) or datetime.min.replace(tzinfo=UTC)))[0]


class AccountManager:
    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.clients: dict[int, Any] = {}

    async def scan_sessions(self) -> int:
        self.settings.sessions_dir.mkdir(parents=True, exist_ok=True)
        session_files = sorted(Path(self.settings.sessions_dir).glob("*.session"))
        created = 0
        async with self.sessionmaker() as session:
            for session_file in session_files:
                existing = await session.scalar(select(Account).where(Account.session_name == session_file.stem))
                if existing:
                    continue
                session.add(
                    Account(
                        session_name=session_file.stem,
                        status="active",
                        enabled=True,
                        daily_limit=self.settings.daily_account_limit,
                    )
                )
                created += 1
            await session.commit()
        return created

    async def list_accounts(self) -> list[Account]:
        async with self.sessionmaker() as session:
            rows = await session.scalars(select(Account).order_by(Account.id))
            return list(rows)

    async def set_enabled(self, account_id: int, enabled: bool) -> bool:
        async with self.sessionmaker() as session:
            account = await session.get(Account, account_id)
            if not account:
                return False
            account.enabled = enabled
            account.status = "active" if enabled and account.status == "disabled" else account.status
            if not enabled:
                account.status = "disabled"
            await session.commit()
            return True

    async def pick_available_account(self) -> Account | None:
        async with self.sessionmaker() as session:
            rows = await session.scalars(select(Account).where(Account.enabled.is_(True)))
            return choose_account(list(rows))

    def session_path(self, account: Account) -> Path:
        return self.settings.sessions_dir / account.session_name

    async def get_client(self, account: Account):
        if TelegramClient is None:
            raise RuntimeError("Telethon is not installed")
        if account.id in self.clients:
            return self.clients[account.id]
        client = TelegramClient(str(self.session_path(account)), self.settings.api_id, self.settings.api_hash)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError(f"Telegram account {account.session_name} is not authorized")
        self.clients[account.id] = client
        return client

    async def send_message(self, account: Account, peer: int | str, text: str) -> None:
        client = await self.get_client(account)
        await client.send_message(peer, text)

    async def mark_sent(
        self,
        account_id: int,
        cooldown_after_messages: int | None = None,
        cooldown_seconds: int | None = None,
    ) -> None:
        async with self.sessionmaker() as session:
            account = await session.get(Account, account_id)
            if account:
                account.sent_today += 1
                account.last_sent_at = utcnow()
                cooldown_after = cooldown_after_messages or self.settings.cooldown_after_messages
                cooldown_for = cooldown_seconds if cooldown_seconds is not None else self.settings.cooldown_seconds
                if cooldown_after and account.sent_today % cooldown_after == 0:
                    account.cooldown_until = utcnow() + timedelta(seconds=cooldown_for)
                await session.commit()

    async def mark_limited(self, account_id: int, seconds: int, reason: str) -> None:
        async with self.sessionmaker() as session:
            account = await session.get(Account, account_id)
            if account:
                account.status = "limited"
                account.limited_until = utcnow() + timedelta(seconds=seconds)
                account.error_message = reason
                await session.commit()

    async def refresh_limited_accounts(self) -> None:
        async with self.sessionmaker() as session:
            rows = await session.scalars(select(Account).where(Account.status == "limited"))
            now = utcnow()
            for account in rows:
                limited_until = normalize_datetime(account.limited_until)
                if limited_until and limited_until <= now:
                    account.status = "active"
                    account.error_message = None
            await session.commit()

    async def start_authorized_clients(self) -> list[tuple[Account, Any]]:
        started: list[tuple[Account, Any]] = []
        for account in await self.list_accounts():
            if not account.enabled or account.status not in {"active", "limited"}:
                continue
            try:
                client = await self.get_client(account)
                started.append((account, client))
            except Exception as exc:
                logger.warning("Could not start Telegram client for account %s: %s", account.session_name, exc)
        return started

    async def close(self) -> None:
        clients = list(self.clients.values())
        self.clients.clear()
        for client in clients:
            try:
                await client.disconnect()
            except Exception:
                logger.exception("Could not disconnect Telegram client")
        await asyncio.sleep(0)
