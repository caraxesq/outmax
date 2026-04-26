from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message as BotMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.accounts.login import BotLoginManager
from app.accounts.manager import AccountManager
from app.bot.keyboards import (
    BTN_ACCOUNTS,
    BTN_ADD_ACCOUNT,
    BTN_HELP,
    BTN_START_CAMPAIGN,
    BTN_STATUS,
    BTN_STOP_CAMPAIGN,
    BTN_TEMPLATE,
    BTN_UPLOAD_LIST,
    HELP_TEXT,
    accounts_keyboard,
    campaign_start_keyboard,
    main_menu_keyboard,
    template_keyboard,
)
from app.config import Settings
from app.db.models import Account, Campaign, Message, Reply
from app.messaging.queue import CampaignQueue
from app.recipients.importer import RecipientImporter

logger = logging.getLogger(__name__)


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
    user_states: dict[int, str] = field(default_factory=dict)


async def require_admin(message: BotMessage, settings: Settings) -> bool:
    if not is_admin(settings, message.from_user.id if message.from_user else None):
        await message.answer("Доступ закрыт.")
        return False
    return True


async def require_admin_callback(callback: CallbackQuery, settings: Settings) -> bool:
    if not is_admin(settings, callback.from_user.id if callback.from_user else None):
        await callback.answer("Доступ закрыт.", show_alert=True)
        return False
    return True


def _admin_id(message: BotMessage) -> int:
    return message.from_user.id if message.from_user else 0


def _template_prompt() -> str:
    return (
        "Отправьте новый шаблон одним сообщением.\n\n"
        "Можно использовать переменные из CSV, например:\n"
        "Привет, {{ name }}! Видел ваш интерес к {{ niche }}."
    )


async def send_main_menu(message: BotMessage, text: str | None = None) -> None:
    await message.answer(text or HELP_TEXT, reply_markup=main_menu_keyboard())


async def render_status(runtime: BotRuntime) -> str:
    async with runtime.sessionmaker() as session:
        sent = await session.scalar(select(func.count(Message.id)).where(Message.status == "sent"))
        pending = await session.scalar(select(func.count(Message.id)).where(Message.status == "pending"))
        failed = await session.scalar(select(func.count(Message.id)).where(Message.status == "failed"))
        skipped = await session.scalar(select(func.count(Message.id)).where(Message.status == "skipped"))
        replies = await session.scalar(select(func.count(Reply.id)))
        campaigns = await session.scalar(select(func.count(Campaign.id)).where(Campaign.status == "running"))
        accounts_count = await session.scalar(select(func.count(Account.id)).where(Account.enabled.is_(True)))
    return (
        "Статус системы\n\n"
        f"Отправлено: {sent or 0}\n"
        f"В очереди: {pending or 0}\n"
        f"Ошибки: {failed or 0}\n"
        f"Пропущено: {skipped or 0}\n"
        f"Ответов получено: {replies or 0}\n"
        f"Активных кампаний: {campaigns or 0}\n"
        f"Включённых аккаунтов: {accounts_count or 0}"
    )


async def render_accounts(runtime: BotRuntime) -> tuple[str, object]:
    created = await runtime.account_manager.scan_sessions()
    accounts = await runtime.account_manager.list_accounts()
    if not accounts:
        text = (
            "Аккаунты не найдены.\n\n"
            "Положите готовые .session файлы в папку sessions или используйте кнопку "
            "\"Добавить аккаунт\", когда будут заполнены API_ID и API_HASH."
        )
        return text, accounts_keyboard([])

    lines = [f"Список аккаунтов обновлён. Новых session-файлов: {created}", ""]
    for account in accounts:
        enabled = "включён" if account.enabled else "отключён"
        lines.append(
            f"#{account.id} {account.session_name}\n"
            f"Статус: {account.status}, {enabled}\n"
            f"Сегодня: {account.sent_today}/{account.daily_limit}"
        )
    return "\n\n".join(lines), accounts_keyboard(accounts)


async def start_campaign_for_segment(runtime: BotRuntime, segment: str | None) -> str:
    if not runtime.current_template:
        return "Сначала задайте шаблон через кнопку \"Шаблон\"."
    campaign = await runtime.campaign_queue.create_campaign("Кампания из бота", runtime.current_template, segment=segment)
    created = await runtime.campaign_queue.start_campaign(campaign.id)
    segment_text = segment if segment else "все получатели"
    return f"Кампания #{campaign.id} запущена.\nСегмент: {segment_text}\nВ очереди сообщений: {created}"


def build_router(runtime: BotRuntime) -> Router:
    router = Router()

    @router.message(Command("start"))
    async def start(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        await send_main_menu(message, "Готово. Управление теперь через кнопки ниже.")

    @router.message(F.text == BTN_HELP)
    async def help_button(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        await send_main_menu(message, HELP_TEXT)

    @router.message(Command("status"))
    @router.message(F.text == BTN_STATUS)
    async def status(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        try:
            await message.answer(await render_status(runtime), reply_markup=main_menu_keyboard())
        except Exception:
            logger.exception("Status button failed")
            await message.answer("Не получилось получить статус. Ошибка записана в лог.", reply_markup=main_menu_keyboard())

    @router.message(Command("accounts"))
    @router.message(F.text == BTN_ACCOUNTS)
    async def accounts(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        try:
            text, keyboard = await render_accounts(runtime)
            await message.answer(text, reply_markup=keyboard)
        except Exception:
            logger.exception("Accounts button failed")
            await message.answer("Не получилось загрузить аккаунты. Ошибка записана в лог.", reply_markup=main_menu_keyboard())

    @router.callback_query(F.data == "accounts:refresh")
    async def accounts_refresh(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        try:
            text, keyboard = await render_accounts(runtime)
            if callback.message:
                await callback.message.answer(text, reply_markup=keyboard)
            await callback.answer("Обновлено")
        except Exception:
            logger.exception("Accounts refresh failed")
            await callback.answer("Не получилось обновить список", show_alert=True)

    @router.callback_query(F.data.startswith("account:"))
    async def account_toggle(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        try:
            _, action, raw_account_id = callback.data.split(":")
            account_id = int(raw_account_id)
            enabled = action == "enable"
            updated = await runtime.account_manager.set_enabled(account_id, enabled)
            if not updated:
                await callback.answer("Аккаунт не найден", show_alert=True)
                return
            text, keyboard = await render_accounts(runtime)
            if callback.message:
                await callback.message.answer(text, reply_markup=keyboard)
            await callback.answer("Готово")
        except Exception:
            logger.exception("Account toggle failed")
            await callback.answer("Не получилось изменить аккаунт", show_alert=True)

    @router.message(Command("add_account"))
    @router.message(F.text == BTN_ADD_ACCOUNT)
    async def add_account(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        try:
            reply = await runtime.login_manager.start(_admin_id(message))
            await message.answer(reply, reply_markup=main_menu_keyboard())
        except Exception:
            logger.exception("Add account button failed")
            await message.answer("Не получилось начать подключение аккаунта. Ошибка записана в лог.", reply_markup=main_menu_keyboard())

    @router.message(Command("upload_list"))
    @router.message(F.text == BTN_UPLOAD_LIST)
    async def upload_list(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        runtime.user_states[_admin_id(message)] = "awaiting_csv"
        await message.answer(
            "Отправьте CSV-файл документом.\n\n"
            "Обязательное поле: user_id или username.\n"
            "Дополнительные колонки станут переменными шаблона.",
            reply_markup=main_menu_keyboard(),
        )

    @router.message(F.document)
    async def receive_document(message: BotMessage, bot: Bot) -> None:
        if not await require_admin(message, runtime.settings):
            return
        try:
            if not message.document:
                await message.answer("Не вижу файл. Отправьте CSV документом.", reply_markup=main_menu_keyboard())
                return
            file_name = message.document.file_name or ""
            if file_name and not file_name.lower().endswith(".csv"):
                await message.answer("Нужен CSV-файл. Попробуйте отправить файл с расширением .csv.", reply_markup=main_menu_keyboard())
                return
            file = await bot.get_file(message.document.file_id)
            data = await bot.download_file(file.file_path)
            result = await runtime.recipient_importer.import_csv_bytes(data.read())
            runtime.user_states.pop(_admin_id(message), None)
            await message.answer(
                "Импорт завершён.\n"
                f"Добавлено: {result.imported}\n"
                f"Дубликатов: {result.duplicates}\n"
                f"Некорректных строк: {result.invalid}",
                reply_markup=main_menu_keyboard(),
            )
        except UnicodeDecodeError:
            await message.answer("Файл не похож на UTF-8 CSV. Сохраните таблицу как CSV UTF-8 и отправьте снова.", reply_markup=main_menu_keyboard())
        except Exception:
            logger.exception("CSV import failed")
            await message.answer("Не получилось импортировать CSV. Ошибка записана в лог.", reply_markup=main_menu_keyboard())

    @router.message(Command("set_template"))
    @router.message(F.text == BTN_TEMPLATE)
    async def template(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        text = message.text or ""
        if text.startswith("/set_template") and text.partition(" ")[2].strip():
            runtime.current_template = text.partition(" ")[2].strip()
            await message.answer("Шаблон сохранён.", reply_markup=main_menu_keyboard())
            return
        current = runtime.current_template or "шаблон пока не задан"
        await message.answer(
            f"Текущий шаблон:\n{current}\n\nНажмите \"Изменить шаблон\", чтобы задать новый.",
            reply_markup=template_keyboard(),
        )

    @router.callback_query(F.data == "template:edit")
    async def template_edit(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        runtime.user_states[callback.from_user.id] = "awaiting_template"
        if callback.message:
            await callback.message.answer(_template_prompt(), reply_markup=main_menu_keyboard())
        await callback.answer()

    @router.message(Command("start_campaign"))
    @router.message(F.text == BTN_START_CAMPAIGN)
    async def start_campaign(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        if not runtime.current_template:
            await message.answer("Сначала задайте шаблон через кнопку \"Шаблон\".", reply_markup=main_menu_keyboard())
            return
        await message.answer("Кого поставить в очередь?", reply_markup=campaign_start_keyboard())

    @router.callback_query(F.data == "campaign:start:all")
    async def campaign_all(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        try:
            text = await start_campaign_for_segment(runtime, None)
            if callback.message:
                await callback.message.answer(text, reply_markup=main_menu_keyboard())
            await callback.answer("Кампания запущена")
        except Exception:
            logger.exception("Campaign start failed")
            await callback.answer("Не получилось запустить кампанию", show_alert=True)

    @router.callback_query(F.data == "campaign:segment")
    async def campaign_segment(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        runtime.user_states[callback.from_user.id] = "awaiting_segment"
        if callback.message:
            await callback.message.answer("Введите название сегмента из CSV.", reply_markup=main_menu_keyboard())
        await callback.answer()

    @router.message(Command("stop_campaign"))
    @router.message(F.text == BTN_STOP_CAMPAIGN)
    async def stop_campaign(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        try:
            stopped = await runtime.campaign_queue.stop_campaign()
            await message.answer(f"Остановлено кампаний: {stopped}", reply_markup=main_menu_keyboard())
        except Exception:
            logger.exception("Stop campaign failed")
            await message.answer("Не получилось остановить кампании. Ошибка записана в лог.", reply_markup=main_menu_keyboard())

    @router.callback_query(F.data == "state:cancel")
    async def cancel_state(callback: CallbackQuery) -> None:
        if not await require_admin_callback(callback, runtime.settings):
            return
        runtime.user_states.pop(callback.from_user.id, None)
        if callback.message:
            await callback.message.answer("Действие отменено.", reply_markup=main_menu_keyboard())
        await callback.answer()

    @router.message()
    async def text_input_or_menu(message: BotMessage) -> None:
        if not await require_admin(message, runtime.settings):
            return
        admin_id = _admin_id(message)
        text = (message.text or "").strip()

        try:
            login_reply = await runtime.login_manager.handle_input(admin_id, text)
            if login_reply:
                await message.answer(login_reply, reply_markup=main_menu_keyboard())
                return

            state = runtime.user_states.get(admin_id)
            if state == "awaiting_template":
                if not text:
                    await message.answer("Шаблон не может быть пустым. Отправьте текст шаблона.", reply_markup=main_menu_keyboard())
                    return
                runtime.current_template = text
                runtime.user_states.pop(admin_id, None)
                await message.answer("Шаблон сохранён.", reply_markup=main_menu_keyboard())
                return

            if state == "awaiting_segment":
                if not text:
                    await message.answer("Введите название сегмента или нажмите \"Отмена\".", reply_markup=main_menu_keyboard())
                    return
                runtime.user_states.pop(admin_id, None)
                await message.answer(await start_campaign_for_segment(runtime, text), reply_markup=main_menu_keyboard())
                return

            if state == "awaiting_csv":
                await message.answer("Сейчас я жду CSV-файл документом. Текст не импортируется.", reply_markup=main_menu_keyboard())
                return

            await send_main_menu(message, "Я не распознал действие. Используйте кнопки ниже.")
        except Exception:
            logger.exception("Text handler failed")
            await message.answer(
                "Что-то пошло не так при обработке действия. Ошибка записана в лог, меню остаётся доступным.",
                reply_markup=main_menu_keyboard(),
            )

    return router
