from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


BTN_STATUS = "Статус"
BTN_ACCOUNTS = "Аккаунты"
BTN_LEADS = "Лиды"
BTN_TEMPLATE = "Шаблон"
BTN_START_CAMPAIGN = "Запустить кампанию"
BTN_STOP_CAMPAIGN = "Остановить кампании"
BTN_SETTINGS = "Параметры"
BTN_ADD_ACCOUNT = "Добавить аккаунт"
BTN_HELP = "Помощь"

HELP_TEXT = (
    "Панель управления Outmax.\n\n"
    "Выберите действие кнопкой ниже:\n"
    "Статус - посмотреть отправки, очередь, ответы и активные аккаунты.\n"
    "Аккаунты - обновить список session-файлов, включать и отключать аккаунты.\n"
    "Лиды - добавить username вручную или загрузить таблицу с username.\n"
    "Шаблон - задать текст сообщения с переменными вроде {{ name }}.\n"
    "Запустить кампанию - поставить сообщения в очередь.\n"
    "Остановить кампании - остановить активные кампании и очистить ожидание.\n"
    "Параметры - настроить скорость, задержки и перерывы.\n"
    "Добавить аккаунт - подключить Telegram user-аккаунт, если включен bot-login."
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_ACCOUNTS)],
            [KeyboardButton(text=BTN_LEADS), KeyboardButton(text=BTN_TEMPLATE)],
            [KeyboardButton(text=BTN_START_CAMPAIGN), KeyboardButton(text=BTN_STOP_CAMPAIGN)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_ADD_ACCOUNT)],
            [KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие",
    )


def accounts_panel_keyboard(accounts: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Загрузить session-файл", callback_data="accounts:upload_session")],
        [InlineKeyboardButton(text="Подключить по коду", callback_data="accounts:code_login")],
        [InlineKeyboardButton(text="Обновить список", callback_data="accounts:refresh")],
    ]
    for account in accounts:
        action = "disable" if account.enabled else "enable"
        label = "Отключить" if account.enabled else "Включить"
        rows.append([InlineKeyboardButton(text=f"{label} #{account.id}", callback_data=f"account:{action}:{account.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def accounts_keyboard(accounts: list) -> InlineKeyboardMarkup:
    return accounts_panel_keyboard(accounts)


def leads_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Ввести username", callback_data="leads:text")],
            [InlineKeyboardButton(text="Загрузить таблицу/файл", callback_data="leads:file")],
            [InlineKeyboardButton(text="Отмена", callback_data="state:cancel")],
        ]
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Сообщений в час", callback_data="settings:send_per_hour")],
            [InlineKeyboardButton(text="Задержка между сообщениями", callback_data="settings:delay_minutes")],
            [InlineKeyboardButton(text="После скольких сообщений перерыв", callback_data="settings:cooldown_after_messages")],
            [InlineKeyboardButton(text="Длина перерыва", callback_data="settings:cooldown_minutes")],
            [InlineKeyboardButton(text="Отмена", callback_data="state:cancel")],
        ]
    )


def campaign_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Все получатели", callback_data="campaign:start:all")],
            [InlineKeyboardButton(text="Выбрать сегмент", callback_data="campaign:segment")],
            [InlineKeyboardButton(text="Отмена", callback_data="state:cancel")],
        ]
    )


def template_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Изменить шаблон", callback_data="template:edit")],
            [InlineKeyboardButton(text="Отмена", callback_data="state:cancel")],
        ]
    )
