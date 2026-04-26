from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Campaign, Message, Recipient
from app.templates.renderer import MessageRenderer, TemplateRenderError


class CampaignQueue:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], renderer: MessageRenderer):
        self.sessionmaker = sessionmaker
        self.renderer = renderer

    async def create_campaign(self, name: str, template_text: str, segment: str | None = None) -> Campaign:
        async with self.sessionmaker() as session:
            campaign = Campaign(name=name, template_text=template_text, segment=segment, status="draft")
            session.add(campaign)
            await session.commit()
            await session.refresh(campaign)
            return campaign

    async def start_campaign(self, campaign_id: int, use_ai: bool = False) -> int:
        async with self.sessionmaker() as session:
            campaign = await session.get(Campaign, campaign_id)
            if campaign is None:
                raise ValueError(f"Campaign {campaign_id} not found")
            query = select(Recipient).where(Recipient.do_not_contact.is_(False))
            if campaign.segment:
                query = query.where(Recipient.segment == campaign.segment)
            recipients = list(await session.scalars(query))
            created = 0
            for recipient in recipients:
                variables = dict(recipient.metadata_json or {})
                variables.update(
                    {
                        "user_id": recipient.user_id,
                        "username": recipient.username,
                        "segment": recipient.segment,
                    }
                )
                try:
                    text = await self.renderer.render(campaign.template_text, variables, use_ai=use_ai)
                except TemplateRenderError as exc:
                    session.add(
                        Message(
                            campaign_id=campaign.id,
                            recipient_id=recipient.id,
                            text="",
                            status="skipped",
                            last_error=str(exc),
                        )
                    )
                    continue
                session.add(Message(campaign_id=campaign.id, recipient_id=recipient.id, text=text, status="pending"))
                created += 1
            campaign.status = "running"
            campaign.started_at = datetime.now(UTC)
            await session.commit()
            return created

    async def stop_campaign(self, campaign_id: int | None = None) -> int:
        async with self.sessionmaker() as session:
            campaign_query = update(Campaign).where(Campaign.status == "running").values(status="stopped", stopped_at=datetime.now(UTC))
            message_query = update(Message).where(Message.status == "pending").values(status="skipped", last_error="campaign stopped")
            if campaign_id is not None:
                campaign_query = campaign_query.where(Campaign.id == campaign_id)
                message_query = message_query.where(Message.campaign_id == campaign_id)
            campaign_result = await session.execute(campaign_query)
            await session.execute(message_query)
            await session.commit()
            return campaign_result.rowcount or 0
