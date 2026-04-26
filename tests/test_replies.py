from __future__ import annotations

from app.replies.listener import ReplyListener


class FakeBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text, kwargs))


async def test_reply_notification(settings, sessionmaker):
    bot = FakeBot()
    listener = ReplyListener(settings, sessionmaker, bot)
    await listener.notify_admins(7, 99, "alice", "hello")
    assert len(bot.messages) == 2
    assert "alice" in bot.messages[0][1]
