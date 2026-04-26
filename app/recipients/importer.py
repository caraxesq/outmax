from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Recipient


@dataclass
class ImportResult:
    imported: int
    skipped: int
    duplicates: int
    invalid: int


class RecipientImporter:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        self.sessionmaker = sessionmaker

    async def import_csv_text(self, csv_text: str) -> ImportResult:
        reader = csv.DictReader(io.StringIO(csv_text))
        imported = skipped = duplicates = invalid = 0
        seen: set[str] = set()

        async with self.sessionmaker() as session:
            for row in reader:
                normalized = {str(k).strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
                user_id = self._parse_user_id(normalized.get("user_id"))
                username = self._normalize_username(normalized.get("username"))
                if user_id is None and username is None:
                    invalid += 1
                    continue
                key = f"id:{user_id}" if user_id is not None else f"username:{username}"
                if key in seen:
                    duplicates += 1
                    continue
                seen.add(key)
                exists = await session.scalar(
                    select(Recipient).where(
                        or_(
                            Recipient.user_id == user_id if user_id is not None else False,
                            Recipient.username == username if username is not None else False,
                        )
                    )
                )
                if exists:
                    duplicates += 1
                    continue
                do_not_contact = str(normalized.get("do_not_contact", "")).lower() in {"1", "true", "yes", "y"}
                metadata = self._metadata(normalized)
                session.add(
                    Recipient(
                        user_id=user_id,
                        username=username,
                        segment=normalized.get("segment") or None,
                        metadata_json=metadata,
                        do_not_contact=do_not_contact,
                    )
                )
                imported += 1
            await session.commit()
        return ImportResult(imported=imported, skipped=skipped, duplicates=duplicates, invalid=invalid)

    async def import_csv_bytes(self, data: bytes) -> ImportResult:
        return await self.import_csv_text(data.decode("utf-8-sig"))

    @staticmethod
    def _parse_user_id(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(str(value))
        except ValueError:
            return None

    @staticmethod
    def _normalize_username(value: Any) -> str | None:
        if value in (None, ""):
            return None
        username = str(value).strip()
        if username.startswith("@"):
            username = username[1:]
        return username.lower() or None

    @staticmethod
    def _metadata(row: dict[str, Any]) -> dict[str, Any]:
        excluded = {"user_id", "username", "segment", "do_not_contact"}
        return {key: value for key, value in row.items() if key not in excluded and value not in (None, "")}
