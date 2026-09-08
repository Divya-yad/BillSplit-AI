"""
Pydantic v2 schemas for BillSplit AI.
All monetary values use Decimal to avoid float precision errors.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Shared primitives
# ──────────────────────────────────────────────

class Confidence(BaseModel):
    value: float = Field(ge=0.0, le=1.0)
    reason: Literal["clear", "blurry", "occluded", "handwritten", "inferred", "low_contrast"] = "clear"


# ──────────────────────────────────────────────
# Extraction layer  (Gemini → structured JSON)
# ──────────────────────────────────────────────

class LineItem(BaseModel):
    id: str
    raw_text: str                        # Exact OCR string — audit trail
    name: str                            # Cleaned / normalised name
    quantity: float = 1.0
    unit_price: Decimal
    total_price: Decimal
    confidence: Confidence
    script: Literal["latin", "devanagari", "mixed", "other"] = "latin"
    photo_index: int = 0                 # Which photo this came from (multi-photo)
    bbox: list[float] | None = None      # [x0,y0,x1,y1] normalised 0–1, optional


class Charge(BaseModel):
    """Service charge, GST/CGST/SGST, packaging fee, discount — anything not a food item."""
    id: str
    label: str                           # e.g. "CGST 2.5%", "Service Charge", "Loyalty Discount"
    kind: Literal["tax", "service_charge", "discount", "other_fee"]
    amount: Decimal | None = None        # Absolute rupee value if printed
    percent: float | None = None         # Percentage if printed instead of flat amount
    applies_to: Literal["subtotal", "subtotal_minus_discount", "total"] = "subtotal"
    confidence: Confidence


class ExtractedBill(BaseModel):
    bill_id: str
    restaurant_name: str | None = None
    date: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    charges: list[Charge] = Field(default_factory=list)

    # Verbatim from the printed receipt (Gemini reads, does not calculate)
    printed_subtotal: Decimal | None = None
    printed_total: Decimal | None = None

    # Computed by the backend, never by the LLM
    computed_subtotal: Decimal = Decimal("0")
    computed_total: Decimal = Decimal("0")

    total_mismatch: bool = False
    mismatch_delta: Decimal | None = None
    overall_confidence: float = 1.0
    needs_review: bool = False           # True if any field confidence < threshold

    # Which total should be used for final computation (set after human resolves mismatch)
    trust_computed: bool = True          # False → use printed_total as the authoritative number


# ──────────────────────────────────────────────
# People & Assignment layer
# ──────────────────────────────────────────────

class Person(BaseModel):
    id: str
    name: str
    left_early: bool = False             # Informational — affects assignment eligibility


class ItemAssignment(BaseModel):
    line_item_id: str
    # shares must sum to 1.0; equal split if frontend sends equal fractions
    shares: dict[str, float]             # person_id → fraction (0 < fraction ≤ 1)


# ──────────────────────────────────────────────
# Computation output
# ──────────────────────────────────────────────

class PersonItemDetail(BaseModel):
    line_item_id: str
    name: str
    your_share_amount: Decimal
    full_item_total: Decimal
    share_fraction: float


class PersonBreakdown(BaseModel):
    person_id: str
    name: str
    items: list[PersonItemDetail] = Field(default_factory=list)
    item_subtotal: Decimal
    tax_share: Decimal
    service_charge_share: Decimal
    discount_share: Decimal               # Always negative (savings)
    other_fee_share: Decimal
    final_total: Decimal
    formula_hint: str                     # Human-readable formula string, e.g. "₹120 + 9% GST − 5% disc"


class BillBreakdown(BaseModel):
    bill_id: str
    people: list[PersonBreakdown]
    grand_total_check: Decimal            # sum(person final_totals) — must equal computed_total
    rounding_adjustment: Decimal          # Paisa/cent correction applied
    rounding_adjusted_person_id: str | None = None
    authoritative_total: Decimal          # The total that was used (computed or printed)


# ──────────────────────────────────────────────
# API request / response shapes
# ──────────────────────────────────────────────

class UploadResponse(BaseModel):
    bill_id: str
    extracted: ExtractedBill


class CorrectionRequest(BaseModel):
    """Partial diff — only send the fields that changed."""
    restaurant_name: str | None = None
    date: str | None = None
    line_items: list[LineItem] | None = None
    charges: list[Charge] | None = None
    printed_subtotal: Decimal | None = None
    printed_total: Decimal | None = None
    trust_computed: bool | None = None


class PeopleRequest(BaseModel):
    people: list[Person]


class AssignRequest(BaseModel):
    assignments: list[ItemAssignment]


class BillStateResponse(BaseModel):
    bill_id: str
    extracted: ExtractedBill
    people: list[Person]
    assignments: list[ItemAssignment]
    breakdown: BillBreakdown | None = None
