"""
FastAPI route handlers for all bill-related endpoints.
"""
from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from engine.assign import validate_assignments
from engine.split import compute_breakdown
from models.schemas import (
    AssignRequest,
    BillBreakdown,
    BillStateResponse,
    CorrectionRequest,
    ExtractedBill,
    ItemAssignment,
    Person,
    PeopleRequest,
    UploadResponse,
)
from storage.db import (
    AsyncSessionLocal,
    get_bill,
    save_bill,
    update_bill_assignments,
    update_bill_breakdown,
    update_bill_extracted,
    update_bill_people,
)
from vision.extract import extract_bill
from vision.preprocess import preprocess_image

router = APIRouter(prefix="/bills", tags=["bills"])


# ── Session dependency ────────────────────────────────────────────────────────
async def get_session():
    async with AsyncSessionLocal() as session:
        yield session


# ── Helper to rehydrate a stored bill record ─────────────────────────────────
def _load_state(record) -> dict[str, Any]:
    extracted = ExtractedBill.model_validate_json(record.extracted_json)
    people = [Person.model_validate(p) for p in json.loads(record.people_json or "[]")]
    assignments = [
        ItemAssignment.model_validate(a)
        for a in json.loads(record.assignments_json or "[]")
    ]
    breakdown = (
        BillBreakdown.model_validate_json(record.breakdown_json)
        if record.breakdown_json
        else None
    )
    return dict(extracted=extracted, people=people, assignments=assignments, breakdown=breakdown)


# ── POST /bills/upload ────────────────────────────────────────────────────────
@router.post("/upload", response_model=UploadResponse)
async def upload_bill(
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """
    Accept 1–3 bill images, preprocess, extract via Gemini, persist, return.
    """
    if not 1 <= len(files) <= 3:
        raise HTTPException(400, "Upload between 1 and 3 images per bill.")

    bill_id = str(uuid.uuid4())

    # Preprocess each image
    preprocessed = []
    for f in files:
        raw = await f.read()
        try:
            pp = preprocess_image(raw)
        except Exception:
            pp = raw  # Fall back to raw if preprocessing fails
        preprocessed.append(pp)

    # Gemini extraction
    try:
        extracted = await extract_bill(preprocessed, bill_id)
    except Exception as exc:
        raise HTTPException(502, f"Gemini extraction failed: {exc}") from exc

    await save_bill(session, bill_id, extracted)
    return UploadResponse(bill_id=bill_id, extracted=extracted)


# ── GET /bills/{bill_id} ──────────────────────────────────────────────────────
@router.get("/{bill_id}", response_model=BillStateResponse)
async def get_bill_state(bill_id: str, session: AsyncSession = Depends(get_session)):
    record = await get_bill(session, bill_id)
    if not record:
        raise HTTPException(404, f"Bill {bill_id!r} not found.")
    state = _load_state(record)
    return BillStateResponse(bill_id=bill_id, **state)


# ── PATCH /bills/{bill_id}/correct ───────────────────────────────────────────
@router.patch("/{bill_id}/correct", response_model=ExtractedBill)
async def correct_bill(
    bill_id: str,
    correction: CorrectionRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Apply human corrections as a diff. Re-runs subtotal/total computation
    after each correction so the ReviewScreen can show live feedback.
    """
    record = await get_bill(session, bill_id)
    if not record:
        raise HTTPException(404, f"Bill {bill_id!r} not found.")

    extracted = ExtractedBill.model_validate_json(record.extracted_json)

    # Apply partial corrections
    if correction.restaurant_name is not None:
        extracted.restaurant_name = correction.restaurant_name
    if correction.date is not None:
        extracted.date = correction.date
    if correction.line_items is not None:
        extracted.line_items = correction.line_items
    if correction.charges is not None:
        extracted.charges = correction.charges
    if correction.printed_subtotal is not None:
        extracted.printed_subtotal = correction.printed_subtotal
    if correction.printed_total is not None:
        extracted.printed_total = correction.printed_total
    if correction.trust_computed is not None:
        extracted.trust_computed = correction.trust_computed

    # Recompute backend totals after correction
    from vision.extract import _backend_sanity_checks
    extracted = _backend_sanity_checks(extracted)

    await update_bill_extracted(session, bill_id, extracted.model_dump_json())
    return extracted


# ── POST /bills/{bill_id}/people ──────────────────────────────────────────────
@router.post("/{bill_id}/people", response_model=list[Person])
async def set_people(
    bill_id: str,
    req: PeopleRequest,
    session: AsyncSession = Depends(get_session),
):
    record = await get_bill(session, bill_id)
    if not record:
        raise HTTPException(404, f"Bill {bill_id!r} not found.")
    people_json = json.dumps([p.model_dump() for p in req.people])
    await update_bill_people(session, bill_id, people_json)
    return req.people


# ── POST /bills/{bill_id}/assign ──────────────────────────────────────────────
@router.post("/{bill_id}/assign", response_model=list[ItemAssignment])
async def set_assignments(
    bill_id: str,
    req: AssignRequest,
    session: AsyncSession = Depends(get_session),
):
    record = await get_bill(session, bill_id)
    if not record:
        raise HTTPException(404, f"Bill {bill_id!r} not found.")

    extracted = ExtractedBill.model_validate_json(record.extracted_json)
    all_item_ids = [item.id for item in extracted.line_items]
    unassigned = validate_assignments(all_item_ids, req.assignments)
    if unassigned:
        raise HTTPException(
            400,
            f"Items not yet assigned: {unassigned}. Assign all items before computing.",
        )

    assignments_json = json.dumps([a.model_dump() for a in req.assignments])
    await update_bill_assignments(session, bill_id, assignments_json)
    return req.assignments


# ── GET /bills/{bill_id}/compute ──────────────────────────────────────────────
@router.get("/{bill_id}/compute", response_model=BillBreakdown)
async def compute_bill(bill_id: str, session: AsyncSession = Depends(get_session)):
    """Run the SplitEngine and return the per-person breakdown."""
    record = await get_bill(session, bill_id)
    if not record:
        raise HTTPException(404, f"Bill {bill_id!r} not found.")

    state = _load_state(record)
    extracted: ExtractedBill = state["extracted"]
    people: list[Person] = state["people"]
    assignments: list[ItemAssignment] = state["assignments"]

    if not people:
        raise HTTPException(400, "Add at least one person before computing.")
    if not assignments:
        raise HTTPException(400, "Assign all items before computing.")

    try:
        breakdown = compute_breakdown(extracted, people, assignments)
    except (ValueError, AssertionError) as exc:
        raise HTTPException(422, str(exc)) from exc

    await update_bill_breakdown(session, bill_id, breakdown.model_dump_json())
    return breakdown
