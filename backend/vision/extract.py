"""
Gemini extraction module for BillSplit AI.

Sends preprocessed images to Gemini with a structured-output prompt,
validates the JSON against the ExtractedBill schema, applies backend
sanity checks, and computes subtotals/totals server-side (never LLM-side).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from decimal import Decimal, InvalidOperation

from google import genai
from google.genai import types as genai_types
from dotenv import load_dotenv

from models.schemas import (
    Charge,
    Confidence,
    ExtractedBill,
    LineItem,
)

logger = logging.getLogger(__name__)

load_dotenv()

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Retrieve or initialize the Google GenAI client."""
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set.")
    if _client is None:
        _client = genai.Client(api_key=api_key)
    return _client


# Model configuration via environment variables (with fallback)
def get_model_name() -> str:
    """Primary Gemini model from environment (default: gemini-2.5-flash)."""
    return os.getenv("GEMINI_MODEL_NAME") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"


def get_fallback_model_name() -> str:
    """Fallback Gemini model from environment (default: gemini-3.5-flash)."""
    return os.getenv("GEMINI_FALLBACK_MODEL_NAME") or os.getenv("GEMINI_FALLBACK_MODEL") or "gemini-3.5-flash"


def get_candidate_models() -> list[str]:
    """Ordered candidate model list: primary, fallback, plus backup models."""
    primary = get_model_name()
    fallback = get_fallback_model_name()
    candidates = [primary, fallback, "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash"]
    seen = set()
    ordered: list[str] = []
    for m in candidates:
        if m and m not in seen and m != "gemini-flash-latest":
            seen.add(m)
            ordered.append(m)
    return ordered


# Module-level constant alias for backwards compatibility
_MODEL_NAME = get_model_name()

# Confidence threshold — below this a field is flagged for human review
CONFIDENCE_THRESHOLD = 0.75

EXTRACTION_PROMPT = """
You are a receipt-reading system. You will be given one or more photographs of a
single restaurant bill (if more than one photo, they are sequential parts of the
same physical receipt, in the order given).

Read every line item EXACTLY as printed. Do NOT normalize prices, do NOT guess
missing digits, do NOT "fix" arithmetic — report what is printed even if it looks
wrong. If a value is illegible, set it to null and give it a low confidence score
rather than inventing a plausible number.

For each line item, extract:
- name: cleaned name of the dish/item
- raw_text: the exact OCR string as it appears on the bill
- quantity: number of units (default 1 if not printed)
- unit_price: price per unit (in rupees, as a decimal string like "120.00")
- total_price: line total (in rupees, as a decimal string)
- script: "latin" | "devanagari" | "mixed" | "other"
- confidence: { value: 0.0–1.0, reason: "clear"|"blurry"|"occluded"|"handwritten"|"inferred"|"low_contrast" }
- bbox: [x0, y0, x1, y1] normalised 0–1 bounding box of this line on the image (best effort)
- photo_index: 0-based index of which photo this line came from

Separately extract every NON-food line as a "charge":
CGST, SGST, GST, service charge, packaging fee, delivery fee, discount, rounding — keep them
as DISTINCT entries if printed separately.
For each charge:
- label: exact label as printed (e.g. "CGST @ 2.5%")
- kind: "tax" | "service_charge" | "discount" | "other_fee"
- amount: flat rupee amount if printed (null otherwise)
- percent: percentage if printed (null otherwise)
- applies_to: "subtotal" | "subtotal_minus_discount" | "total" — based on its position on the receipt
- confidence: { value, reason }

Extract the restaurant's own PRINTED subtotal and PRINTED total VERBATIM if shown.
Do NOT calculate or correct these — just report what is printed, or null if absent.

For EVERY field, provide a confidence score 0.0–1.0. Confidence must reflect genuine visual
legibility — a clearly-printed but unusual number still gets high confidence.

If multiple photos are provided, treat them as ONE continuous receipt read in order.
If you suspect an overlapping duplicate line between two photos, include it ONCE and mark
confidence.reason as "inferred", and include "[possible duplicate, verify]" in raw_text.

IMPORTANT: Return ONLY valid JSON matching this exact schema. No markdown, no prose, no extra keys.

{
  "restaurant_name": "string or null",
  "date": "string or null",
  "line_items": [
    {
      "id": "auto-generated UUID string",
      "raw_text": "...",
      "name": "...",
      "quantity": 1,
      "unit_price": "0.00",
      "total_price": "0.00",
      "confidence": { "value": 0.95, "reason": "clear" },
      "script": "latin",
      "photo_index": 0,
      "bbox": [0.0, 0.0, 1.0, 0.1]
    }
  ],
  "charges": [
    {
      "id": "auto-generated UUID string",
      "label": "...",
      "kind": "tax",
      "amount": null,
      "percent": 2.5,
      "applies_to": "subtotal",
      "confidence": { "value": 0.9, "reason": "clear" }
    }
  ],
  "printed_subtotal": "0.00 or null",
  "printed_total": "0.00 or null"
}
""".strip()


def _to_decimal(val: str | int | float | None) -> Decimal | None:
    if val is None:
        return None
    try:
        return Decimal(str(val))
    except InvalidOperation:
        return None


def _parse_raw_json(raw: str, bill_id: str) -> ExtractedBill:
    """Parse and validate Gemini's JSON response into an ExtractedBill."""
    # Strip any accidental markdown fences
    clean_raw = raw.strip()
    if clean_raw.startswith("```"):
        clean_raw = clean_raw.split("```")[1]
        if clean_raw.startswith("json"):
            clean_raw = clean_raw[4:]
    if clean_raw.endswith("```"):
        clean_raw = clean_raw[:-3]

    data = json.loads(clean_raw.strip())

    line_items = []
    for idx, li in enumerate(data.get("line_items", [])):
        conf_raw = li.get("confidence", {})
        conf = Confidence(
            value=float(conf_raw.get("value", 0.5)),
            reason=conf_raw.get("reason", "clear"),
        )
        item = LineItem(
            id=li.get("id") or str(uuid.uuid4()),
            raw_text=li.get("raw_text", ""),
            name=li.get("name", f"Item {idx+1}"),
            quantity=float(li.get("quantity", 1)),
            unit_price=_to_decimal(li.get("unit_price")) or Decimal("0"),
            total_price=_to_decimal(li.get("total_price")) or Decimal("0"),
            confidence=conf,
            script=li.get("script", "latin"),
            photo_index=int(li.get("photo_index", 0)),
            bbox=li.get("bbox"),
        )
        line_items.append(item)

    charges = []
    for ch in data.get("charges", []):
        conf_raw = ch.get("confidence", {})
        conf = Confidence(
            value=float(conf_raw.get("value", 0.5)),
            reason=conf_raw.get("reason", "clear"),
        )
        charge = Charge(
            id=ch.get("id") or str(uuid.uuid4()),
            label=ch.get("label", "Unknown"),
            kind=ch.get("kind", "other_fee"),
            amount=_to_decimal(ch.get("amount")),
            percent=float(ch["percent"]) if ch.get("percent") is not None else None,
            applies_to=ch.get("applies_to", "subtotal"),
            confidence=conf,
        )
        charges.append(charge)

    bill = ExtractedBill(
        bill_id=bill_id,
        restaurant_name=data.get("restaurant_name"),
        date=data.get("date"),
        line_items=line_items,
        charges=charges,
        printed_subtotal=_to_decimal(data.get("printed_subtotal")),
        printed_total=_to_decimal(data.get("printed_total")),
    )
    return bill


def _backend_sanity_checks(bill: ExtractedBill) -> ExtractedBill:
    """
    Backend validation layer — runs AFTER parsing Gemini output.
    1. Flag line items where qty × unit_price ≠ total_price.
    2. Compute backend subtotal and total (never trust LLM arithmetic).
    3. Detect mismatch between printed_total and computed_total.
    4. Set needs_review if any field confidence < threshold.
    """
    TOLERANCE = Decimal("1.00")  # ₹1 tolerance for rounding

    for item in bill.line_items:
        expected = (item.unit_price * Decimal(str(item.quantity))).quantize(Decimal("0.01"))
        if abs(expected - item.total_price) > Decimal("0.02"):
            # Arithmetic doesn't check out — lower confidence and flag
            if item.confidence.value > 0.5:
                item.confidence = Confidence(value=0.49, reason="inferred")

    # Backend computes subtotal — never use LLM-provided totals for math
    computed_subtotal = sum(item.total_price for item in bill.line_items)
    bill.computed_subtotal = computed_subtotal

    # Apply charges to compute the total
    running = computed_subtotal
    for charge in bill.charges:
        base = computed_subtotal
        if charge.applies_to == "total":
            base = running
        elif charge.applies_to == "subtotal_minus_discount":
            # Use subtotal minus any discounts already applied
            base = computed_subtotal

        if charge.amount is not None:
            amount = charge.amount
        elif charge.percent is not None:
            amount = (base * Decimal(str(charge.percent)) / Decimal("100")).quantize(Decimal("0.01"))
        else:
            amount = Decimal("0")

        if charge.kind == "discount":
            running -= amount
        else:
            running += amount

    bill.computed_total = running.quantize(Decimal("0.01"))

    # Mismatch detection
    if bill.printed_total is not None:
        delta = abs(bill.printed_total - bill.computed_total)
        bill.total_mismatch = delta > TOLERANCE
        bill.mismatch_delta = (bill.printed_total - bill.computed_total) if bill.total_mismatch else None

    # Overall confidence + needs_review
    all_confidences = (
        [item.confidence.value for item in bill.line_items]
        + [ch.confidence.value for ch in bill.charges]
    )
    bill.overall_confidence = min(all_confidences) if all_confidences else 1.0
    bill.needs_review = any(c < CONFIDENCE_THRESHOLD for c in all_confidences)

    return bill


async def extract_bill(image_bytes_list: list[bytes], bill_id: str) -> ExtractedBill:
    """
    Main entry point. Accepts 1–3 preprocessed JPEG byte strings.
    Calls Gemini, validates, sanity-checks, returns ExtractedBill.
    """
    client = get_client()

    # Build multimodal content parts using the new google-genai types
    contents: list = [EXTRACTION_PROMPT]
    for img_bytes in image_bytes_list:
        contents.append(
            genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")
        )

    generation_config = genai_types.GenerateContentConfig(
        temperature=0.0,         # Deterministic output for OCR
        response_mime_type="application/json",
    )

    async def _call(request_contents: list) -> tuple[str, str]:
        candidates = get_candidate_models()
        last_err: Exception | None = None

        for model_candidate in candidates:
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model_candidate,
                        contents=request_contents,
                        config=generation_config,
                    ),
                    timeout=25.0,
                )
                return response.text, model_candidate
            except Exception as err:
                logger.warning(
                    "Gemini generation with model '%s' failed: %s",
                    model_candidate,
                    err,
                )
                last_err = err
                continue

        raise last_err or RuntimeError("Gemini content generation failed with all candidate models.")

    # First attempt
    raw, used_model = await _call(contents)

    # Parse attempt with one repair-retry on failure
    try:
        bill = _parse_raw_json(raw, bill_id)
    except Exception as first_err:
        logger.warning(
            "First parsing attempt failed (%s). Attempting repair with Gemini...",
            first_err,
        )
        # Re-prompt with the error
        repair_prompt = (
            f"Your last output failed JSON validation: {first_err}\n"
            f"Return ONLY corrected JSON matching the schema. No prose, no markdown."
        )
        repair_parts = [repair_prompt, f"Previous output was:\n{raw}"]
        repair_raw, _ = await _call(repair_parts)
        bill = _parse_raw_json(repair_raw, bill_id)

    # Backend sanity checks (never trust LLM arithmetic)
    bill = _backend_sanity_checks(bill)
    return bill
