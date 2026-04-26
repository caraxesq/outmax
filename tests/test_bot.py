from __future__ import annotations

from app.bot.handlers import is_admin
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
    main_menu_keyboard,
)


def test_admin_guard(settings):
    assert is_admin(settings, 1) is True
    assert is_admin(settings, 3) is False
    assert is_admin(settings, None) is False


def test_main_menu_contains_russian_management_buttons():
    keyboard = main_menu_keyboard()
    button_texts = [button.text for row in keyboard.keyboard for button in row]

    assert button_texts == [
        BTN_STATUS,
        BTN_ACCOUNTS,
        BTN_UPLOAD_LIST,
        BTN_TEMPLATE,
        BTN_START_CAMPAIGN,
        BTN_STOP_CAMPAIGN,
        BTN_ADD_ACCOUNT,
        BTN_HELP,
    ]


def test_help_text_is_russian_and_has_no_command_catalog():
    assert "Панель управления" in HELP_TEXT
    assert "Команды:" not in HELP_TEXT
    assert "/start_campaign" not in HELP_TEXT
