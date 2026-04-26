from __future__ import annotations

from app.accounts.manager import choose_account
from app.db.models import Account


def test_choose_account_balances_lowest_sent_count(settings):
    first = Account(id=1, session_name="a", status="active", enabled=True, daily_limit=5, sent_today=3)
    second = Account(id=2, session_name="b", status="active", enabled=True, daily_limit=5, sent_today=1)
    assert choose_account([first, second]).id == 2


def test_choose_account_ignores_disabled_or_limited(settings):
    disabled = Account(id=1, session_name="a", status="active", enabled=False, daily_limit=5, sent_today=0)
    limited = Account(id=2, session_name="b", status="limited", enabled=True, daily_limit=5, sent_today=0)
    assert choose_account([disabled, limited]) is None
