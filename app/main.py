from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.accounts.login import BotLoginManager
from app.accounts.manager import AccountManager
from app.bot.handlers import BotRuntime, build_router
from app.config import get_settings
from app.db.init import init_db
from app.db.session import create_sessionmaker
from app.logging_config import configure_logging
from app.messaging.queue import CampaignQueue
from app.messaging.worker import MessageWorker
from app.recipients.importer import RecipientImporter
from app.replies.listener import ReplyListener
from app.settings.service import SettingsService
from app.templates.renderer import MessageRenderer

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    settings.ensure_runtime_dirs()
    configure_logging(settings)
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is required")
    if not settings.admin_id_set:
        raise RuntimeError("ADMIN_IDS is required")
    if not settings.telegram_api_ready:
        logger.warning("API_ID/API_HASH are missing; starting control bot without Telegram user-account clients")

    await init_db()
    sessionmaker = create_sessionmaker(settings=settings)
    bot = Bot(settings.bot_token)
    dispatcher = Dispatcher()

    account_manager = AccountManager(settings, sessionmaker)
    await account_manager.scan_sessions()
    renderer = MessageRenderer(settings)
    settings_service = SettingsService(sessionmaker, settings)
    campaign_queue = CampaignQueue(sessionmaker, renderer)
    runtime = BotRuntime(
        settings=settings,
        sessionmaker=sessionmaker,
        account_manager=account_manager,
        recipient_importer=RecipientImporter(sessionmaker),
        campaign_queue=campaign_queue,
        login_manager=BotLoginManager(settings, sessionmaker),
        settings_service=settings_service,
    )
    dispatcher.include_router(build_router(runtime))

    reply_listener = ReplyListener(settings, sessionmaker, bot)
    if settings.telegram_api_ready:
        for account, client in await account_manager.start_authorized_clients():
            reply_listener.attach(account.id, client)

    worker = MessageWorker(settings, sessionmaker, account_manager, settings_service=settings_service)
    worker_task = asyncio.create_task(worker.start())
    try:
        logger.info("Outmax service started")
        await dispatcher.start_polling(bot)
    finally:
        worker.stop()
        worker_task.cancel()
        await account_manager.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
