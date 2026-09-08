"""
SQLite storage for BillSplit AI using SQLAlchemy async.
Uses a simple JSON-blob approach: the full bill state is stored as JSON,
avoiding complex relational joins while keeping the data model flexible.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import Column, DateTime, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./billsplit.db")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class BillRecord(Base):
    __tablename__ = "bills"

    bill_id = Column(String, primary_key=True, index=True)
    extracted_json = Column(Text, nullable=False)          # ExtractedBill JSON
    people_json = Column(Text, nullable=True, default="[]")
    assignments_json = Column(Text, nullable=True, default="[]")
    breakdown_json = Column(Text, nullable=True, default=None)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def save_bill(session: AsyncSession, bill_id: str, extracted: Any) -> None:
    from models.schemas import ExtractedBill
    record = BillRecord(
        bill_id=bill_id,
        extracted_json=extracted.model_dump_json(),
        people_json="[]",
        assignments_json="[]",
    )
    session.add(record)
    await session.commit()


async def get_bill(session: AsyncSession, bill_id: str) -> BillRecord | None:
    result = await session.execute(select(BillRecord).where(BillRecord.bill_id == bill_id))
    return result.scalar_one_or_none()


async def update_bill_extracted(session: AsyncSession, bill_id: str, extracted_json: str) -> None:
    record = await get_bill(session, bill_id)
    if record:
        record.extracted_json = extracted_json
        record.updated_at = datetime.utcnow()
        await session.commit()


async def update_bill_people(session: AsyncSession, bill_id: str, people_json: str) -> None:
    record = await get_bill(session, bill_id)
    if record:
        record.people_json = people_json
        record.updated_at = datetime.utcnow()
        await session.commit()


async def update_bill_assignments(
    session: AsyncSession, bill_id: str, assignments_json: str
) -> None:
    record = await get_bill(session, bill_id)
    if record:
        record.assignments_json = assignments_json
        record.updated_at = datetime.utcnow()
        await session.commit()


async def update_bill_breakdown(
    session: AsyncSession, bill_id: str, breakdown_json: str
) -> None:
    record = await get_bill(session, bill_id)
    if record:
        record.breakdown_json = breakdown_json
        record.updated_at = datetime.utcnow()
        await session.commit()
