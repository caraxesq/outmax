from __future__ import annotations

from app.bot.handlers import is_admin


def test_admin_guard(settings):
    assert is_admin(settings, 1) is True
    assert is_admin(settings, 3) is False
    assert is_admin(settings, None) is False
