from __future__ import annotations

from sqlalchemy import select

from app.db.models import Recipient
from app.recipients.importer import RecipientImporter


async def test_import_csv_deduplicates_and_preserves_metadata(sessionmaker):
    csv_text = "user_id,username,name,niche,segment\n1,@Alice,Alice,fitness,a\n1,@Alice,Alice,fitness,a\n,bob,Bob,travel,b\n,,Nope,x,c\n"
    result = await RecipientImporter(sessionmaker).import_csv_text(csv_text)
    assert result.imported == 2
    assert result.duplicates == 1
    assert result.invalid == 1
    async with sessionmaker() as session:
        recipients = list(await session.scalars(select(Recipient).order_by(Recipient.id)))
    assert recipients[0].metadata_json["name"] == "Alice"
    assert recipients[1].username == "bob"
