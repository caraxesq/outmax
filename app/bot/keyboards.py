from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


BTN_STATUS = "Статус"
BTN_ACCOUNTS = "Аккаунты"
BTN_UPLOAD_LIST = "Загрузить CSV"
BTN_TEMPLATE = "Шаблон"
BTN_START_CAMPAIGN = "Запустить кампанию"
BTN_STOP_CAMPAIGN = "Остановить кампании"
BTN_ADD_ACCOUNT = "Добавить аккаунт"
BTN_HELP = "Помощь"

HELP_TEXT = (
    "Панель управления Outmax.\n\n"
    "Выберите действие кнопкой ниже:\n"
    "Статус - посмотреть отправки, очередь, ответы и активные аккаунты.\n"
    "Аккаунты - обновить список session-файлов, включать и отключать аккаунты.\n"
    "Загрузить CSV - импортировать получателей из файла с user_id или username.\n"
    "Шаблон - задать текст сообщения с переменными вроде {{ name }}.\n"
    "Запустить кампанию - поставить сообщения в очередь.\n"
    "Остановить кампании - остановить активные кампании и очистить ожидание.\n"
    "Добавить аккаунт - подключить Telegram user-аккаунт, если включен bot-login."
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_ACCOUNTS)],
            [KeyboardButton(text=BTN_UPLOAD_LIST), KeyboardButton(text=BTN_TEMPLATE)],
            [KeyboardButton(text=BTN_START_CAMPAIGN), KeyboardButton(text=BTN_STOP_CAMPAIGN)],
            [KeyboardButton(text=BTN_ADD_ACCOUNT), KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие",
    )


def accounts_keyboard(accounts: list) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="Обновить список", callback_data="accounts:refresh")]
    ]
    for account in accounts:
        action = "disable" if account.enabled else "enable"
        label = "Отключить" if account.enabled else "Включить"
        rows.append([InlineKeyboardButton(text=f"{label} #{account.id}", callback_data=f"account:{action}:{account.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
