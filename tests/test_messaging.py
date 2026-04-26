from __future__ import annotations

from sqlalchemy import select

from app.accounts.manager import AccountManager
from app.db.models import Account, Campaign, Message, Recipient
from app.messaging.queue import CampaignQueue
from app.messaging.worker import FloodWaitError, MessageWorker
from app.templates.renderer import MessageRenderer


async def no_sleep(_seconds):
    return None


class FakeAccountManager(AccountManager):
    def __init__(self, settings, sessionmaker):
        super().__init__(settings, sessionmaker)
        self.sent: list[tuple[int | str, str]] = []
        self.fail_with = None

    async def send_message(self, account, peer, text):
        if self.fail_with:
            raise self.fail_with
        self.sent.append((peer, text))


async def seed_message(sessionmaker):
    async with sessionmaker() as session:
        account = Account(session_name="acc", status="active", enabled=True, daily_limit=5)
        recipient = Recipient(user_id=10, username="user", metadata_json={"name": "Ann"}, do_not_contact=False)
        campaign = Campaign(name="c", template_text="Hi {{ name }}", status="running")
        session.add_all([account, recipient, campaign])
        await session.flush()
        message = Message(campaign_id=campaign.id, recipient_id=recipient.id, text="Hi Ann", status="pending")
        session.add(message)
        await session.commit()
        return message.id


async def test_worker_sends_pending_message(settings, sessionmaker):
    message_id = await seed_message(sessionmaker)
    manager = FakeAccountManager(settings, sessionmaker)
    worker = MessageWorker(settings, sessionmaker, manager, sleep_func=no_sleep)
    assert await worker.run_once() is True
    async with sessionmaker() as session:
        message = await session.get(Message, message_id)
    assert message.status == "sent"
    assert manager.sent == [(10, "Hi Ann")]


async def test_worker_handles_floodwait(settings, sessionmaker):
    message_id = await seed_message(sessionmaker)
    manager = FakeAccountManager(settings, sessionmaker)
    manager.fail_with = FloodWaitError(30)
    worker = MessageWorker(settings, sessionmaker, manager, sleep_func=no_sleep)
    assert await worker.run_once() is True
    async with sessionmaker() as session:
        message = await session.get(Message, message_id)
        account = await session.scalar(select(Account))
    assert message.status == "pending"
    assert "FloodWait" in message.last_error
    assert account.status == "limited"


async def test_campaign_queue_creates_messages(settings, sessionmaker):
    async with sessionmaker() as session:
        session.add(Recipient(user_id=1, username="ann", metadata_json={"name": "Ann"}, segment="a"))
        session.add(Recipient(user_id=2, username="bob", metadata_json={"name": "Bob"}, segment="b"))
        await session.commit()
    queue = CampaignQueue(sessionmaker, MessageRenderer(settings))
    campaign = await queue.create_campaign("c", "Hi {{ name }}", segment="a")
    created = await queue.start_campaign(campaign.id)
    assert created == 1
