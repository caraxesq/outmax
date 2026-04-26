from __future__ import annotations

import asyncio
import getpass
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db.models import Account
from app.db.session import create_sessionmaker

try:
    from telethon import TelegramClient
    from telethon.errors import SessionPasswordNeededError
except Exception:  # pragma: no cover
    TelegramClient = None  # type: ignore[assignment]
    SessionPasswordNeededError = Exception  # type: ignore[assignment]


def safe_session_name(phone: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]+", "_", phone).strip("_")
    return f"account_{cleaned}"


async def register_session(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
    session_name: str,
    phone: str | None = None,
    username: str | None = None,
) -> Account:
    async with sessionmaker() as db:
        account = await db.scalar(select(Account).where(Account.session_name == session_name))
        if account is None:
            account = Account(
                session_name=session_name,
                phone=phone,
                username=username,
                status="active",
                enabled=True,
                daily_limit=settings.daily_account_limit,
            )
            db.add(account)
        else:
            account.phone = phone or account.phone
            account.username = username or account.username
            account.status = "active"
            account.enabled = True
        await db.commit()
        await db.refresh(account)
        return account


@dataclass
class BotLoginState:
    session_name: str
    phone: str | None = None
    code_hash: str | None = None
    stage: str = "phone"
    client: object | None = None


class BotLoginManager:
    def __init__(self, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.states: dict[int, BotLoginState] = {}

    def enabled_for(self, admin_id: int) -> bool:
        return self.settings.enable_bot_login and admin_id in self.settings.admin_id_set

    async def start(self, admin_id: int) -> str:
        if not self.enabled_for(admin_id):
            return "Bot login disabled. Set ENABLE_BOT_LOGIN=true and use an admin account."
        self.states[admin_id] = BotLoginState(session_name="")
        return "Send the phone number for the Telegram user account."

    async def handle_input(self, admin_id: int, text: str) -> str | None:
        state = self.states.get(admin_id)
        if not state or not self.enabled_for(admin_id):
            return None
        if TelegramClient is None:
            return "Telethon is not installed."

        if state.stage == "phone":
            phone = text.strip()
            session_name = safe_session_name(phone)
            client = TelegramClient(str(self.settings.sessions_dir / session_name), self.settings.api_id, self.settings.api_hash)
            await client.connect()
            sent = await client.send_code_request(phone)
            state.phone = phone
            state.session_name = session_name
            state.code_hash = sent.phone_code_hash
            state.client = client
            state.stage = "code"
            return "Code sent. Send the login code."

        if state.stage == "code":
            assert state.client is not None
            try:
                await state.client.sign_in(state.phone, text.strip(), phone_code_hash=state.code_hash)
            except SessionPasswordNeededError:
                state.stage = "password"
                return "Two-factor password is required. Send the 2FA password."
            return await self._finish(admin_id, state)

        if state.stage == "password":
            assert state.client is not None
            await state.client.sign_in(password=text)
            return await self._finish(admin_id, state)

        return None

    async def _finish(self, admin_id: int, state: BotLoginState) -> str:
        me = await state.client.get_me()  # type: ignore[union-attr]
        username = getattr(me, "username", None)
        await register_session(self.sessionmaker, self.settings, state.session_name, state.phone, username)
        await state.client.disconnect()  # type: ignore[union-attr]
        self.states.pop(admin_id, None)
        return f"Account added: {state.session_name}"


async def cli_login() -> None:
    if TelegramClient is None:
        raise RuntimeError("Telethon is not installed")
    settings = get_settings()
    settings.ensure_runtime_dirs()
    sessionmaker = create_sessionmaker(settings=settings)
    phone = input("Telegram phone: ").strip()
    session_name = safe_session_name(phone)
    client = TelegramClient(str(settings.sessions_dir / session_name), settings.api_id, settings.api_hash)
    await client.connect()
    sent = await client.send_code_request(phone)
    code = input("Login code: ").strip()
    try:
        await client.sign_in(phone, code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        password = getpass.getpass("2FA password: ")
        await client.sign_in(password=password)
    me = await client.get_me()
    await register_session(sessionmaker, settings, session_name, phone, getattr(me, "username", None))
    await client.disconnect()
    print(f"Session created: {settings.sessions_dir / (session_name + '.session')}")


if __name__ == "__main__":
    asyncio.run(cli_login())
