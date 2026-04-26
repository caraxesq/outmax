from __future__ import annotations

import html
from dataclasses import dataclass

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import Message as BotMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.login import BotLoginManager
from app.accounts.manager import AccountManager
from app.config import Settings
from app.db.models import Account, Campaign, Message, Reply
from app.messaging.queue import CampaignQueue
from app.recipients.importer import RecipientImporter


def is_admin(settings: Settings, user_id: int | None) -> bool:
    return user_id in settings.admin_id_set if user_id is not None else False


@dataclass
class BotRuntime:
    settings: Settings
    sessionmaker: async_sessionmaker[AsyncSession]
    account_manager: AccountManager
    recipient_importer: RecipientImporter
    campaign_queue: CampaignQueue
    login_manager: BotLoginManager
    current_template: str = ""


async def require_admin(message: BotMessage, settings: Settings) -> bool:
    if not is_admin(settings, message.from_user.id if message.from_user else None):
        await message.answer("Access denied.")
        return False
    return True


def build_router(runtime: BotRuntime) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def start(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        await message.answer(
            "Outmax control bot is running.\n"
            "Commands: /accounts /add_account /upload_list /set_template /start_campaign /stop_campaign /status"
        )

    @router.message(Command("accounts"))
    async def accounts(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        created = await runtime.account_manager.scan_sessions()
        accounts_list = await runtime.account_manager.list_accounts()
        if not accounts_list:
            await message.answer("No accounts registered. Put .session files in sessions/ or use /add_account.")
            return
        lines = [f"Scanned sessions. New accounts: {created}"]
        for account in accounts_list:
            lines.append(
                f"#{account.id} {account.session_name} status={account.status} enabled={account.enabled} "
                f"sent_today={account.sent_today}/{account.daily_limit}"
            )
        await message.answer("\n".join(lines))

    @router.message(Command("add_account"))
    async def add_account(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        reply = await runtime.login_manager.start(message.from_user.id)
        await message.answer(reply)

    @router.message(Command("upload_list"))
    async def upload_list(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        await message.answer("Send a CSV document with user_id or username columns.")

    @router.message(F.document)
    async def receive_document(message: BotMessage, bot: Bot) -> None:
        if not await require_admin(message, runtime.settings):
            return
        if not message.document:
            return
        file = await bot.get_file(message.document.file_id)
        data = await bot.download_file(file.file_path)
        result = await runtime.recipient_importer.import_csv_bytes(data.read())
        await message.answer(
            f"CSV import complete: imported={result.imported}, duplicates={result.duplicates}, invalid={result.invalid}"
        )

    @router.message(Command("set_template"))
    async def set_template(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        text = message.text or ""
        template = text.partition(" ")[2].strip()
        if not template:
            await message.answer("Usage: /set_template Привет, {{ name }}!")
            return
        runtime.current_template = template
        await message.answer("Template saved.")

    @router.message(Command("start_campaign"))
    async def start_campaign(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        if not runtime.current_template:
            await message.answer("Set a template first with /set_template.")
            return
        arg = (message.text or "").partition(" ")[2].strip()
        segment = arg or None
        campaign = await runtime.campaign_queue.create_campaign("bot campaign", runtime.current_template, segment=segment)
        created = await runtime.campaign_queue.start_campaign(campaign.id)
        await message.answer(f"Campaign #{campaign.id} started. Queued messages: {created}")

    @router.message(Command("stop_campaign"))
    async def stop_campaign(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        stopped = await runtime.campaign_queue.stop_campaign()
        await message.answer(f"Stopped campaigns: {stopped}")

    @router.message(Command("status"))
    async def status(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        async with runtime.sessionmaker() as session:
            sent = await session.scalar(select(func.count(Message.id)).where(Message.status == "sent"))
            pending = await session.scalar(select(func.count(Message.id)).where(Message.status == "pending"))
            replies = await session.scalar(select(func.count(Reply.id)))
            campaigns = await session.scalar(select(func.count(Campaign.id)).where(Campaign.status == "running"))
            accounts_count = await session.scalar(select(func.count(Account.id)).where(Account.enabled.is_(True)))
        await message.answer(
            f"Status\nsent={sent or 0}\npending={pending or 0}\nreplies={replies or 0}\n"
            f"running_campaigns={campaigns or 0}\nactive_accounts={accounts_count or 0}"
        )

    @router.message()
    async def login_input_or_unknown(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        reply = await runtime.login_manager.handle_input(message.from_user.id, message.text or "")
        if reply:
            await message.answer(html.escape(reply))
            return
        await message.answer("Unknown command.")

    return router
