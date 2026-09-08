"""
SplitEngine — deterministic, pure-function bill splitting.
No LLM involvement. All arithmetic is explicit Decimal math.

Core guarantee: sum(person final_totals) == authoritative_total (to the paisa).
This is enforced via the largest-remainder rounding correction and asserted at the end.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from models.schemas import (
    BillBreakdown,
    ExtractedBill,
    ItemAssignment,
    Person,
    PersonBreakdown,
    PersonItemDetail,
)


_PAISA = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    """Quantize to 2 decimal places (paisa)."""
    return value.quantize(_PAISA, rounding=ROUND_HALF_UP)


def _get_item(bill: ExtractedBill, item_id: str):
    for item in bill.line_items:
        if item.id == item_id:
            return item
    raise ValueError(f"LineItem {item_id!r} not found in bill {bill.bill_id!r}")


def compute_breakdown(
    bill: ExtractedBill,
    people: list[Person],
    assignments: list[ItemAssignment],
) -> BillBreakdown:
    """
    Compute the per-person breakdown for a bill.

    Algorithm:
    1. Per-person item subtotals — from explicit assignment shares.
    2. Per-person charge shares — proportional to item subtotal, NOT headcount.
    3. Largest-remainder rounding correction so sum == authoritative_total.
    4. Assertion: grand_total_check == authoritative_total.
    """
    if not people:
        raise ValueError("Cannot compute breakdown with no people.")

    person_ids = [p.id for p in people]
    person_map = {p.id: p for p in people}

    # ── Step 1: Per-person item subtotals ─────────────────────────────────────
    person_item_total: dict[str, Decimal] = {pid: Decimal("0") for pid in person_ids}
    person_items: dict[str, list[PersonItemDetail]] = {pid: [] for pid in person_ids}

    for assignment in assignments:
        item = _get_item(bill, assignment.line_item_id)
        # Normalise shares so they sum to exactly 1
        raw_shares = assignment.shares
        share_sum = sum(raw_shares.values())
        if abs(share_sum - 1.0) > 1e-6:
            # Normalise
            raw_shares = {k: v / share_sum for k, v in raw_shares.items()}

        for person_id, share_fraction in raw_shares.items():
            if person_id not in person_item_total:
                continue  # Guard against stale assignments
            amount = _q(item.total_price * Decimal(str(share_fraction)))
            person_item_total[person_id] += amount
            person_items[person_id].append(
                PersonItemDetail(
                    line_item_id=item.id,
                    name=item.name,
                    your_share_amount=amount,
                    full_item_total=item.total_price,
                    share_fraction=share_fraction,
                )
            )

    subtotal = sum(person_item_total.values())
    if subtotal == Decimal("0"):
        subtotal = Decimal("1")  # Avoid division-by-zero; edge case guard

    # Authoritative total — human chose trust_computed or trust_printed
    if bill.trust_computed or bill.printed_total is None:
        authoritative_total = bill.computed_total
    else:
        authoritative_total = bill.printed_total

    # ── Step 2: Proportional charge distribution ───────────────────────────────
    # Charge kinds we track separately for transparency
    person_tax: dict[str, Decimal] = {pid: Decimal("0") for pid in person_ids}
    person_svc: dict[str, Decimal] = {pid: Decimal("0") for pid in person_ids}
    person_disc: dict[str, Decimal] = {pid: Decimal("0") for pid in person_ids}
    person_other: dict[str, Decimal] = {pid: Decimal("0") for pid in person_ids}

    for charge in bill.charges:
        # Determine the base for percentage charges
        if charge.applies_to == "subtotal":
            base = bill.computed_subtotal
        elif charge.applies_to == "subtotal_minus_discount":
            # Subtotal minus any discounts
            disc_total = sum(
                ch.amount or Decimal("0")
                for ch in bill.charges
                if ch.kind == "discount" and ch.amount is not None
            )
            base = bill.computed_subtotal - disc_total
        else:  # "total"
            base = bill.computed_total

        if charge.amount is not None:
            charge_amount = charge.amount
        elif charge.percent is not None:
            charge_amount = _q(base * Decimal(str(charge.percent)) / Decimal("100"))
        else:
            charge_amount = Decimal("0")

        for person_id in person_ids:
            # CRITICAL: proportion = person's share of subtotal, NOT 1/n
            person_subtotal = person_item_total[person_id]
            proportion = person_subtotal / subtotal if subtotal > 0 else Decimal("0")
            person_share = _q(charge_amount * proportion)

            if charge.kind == "tax":
                person_tax[person_id] += person_share
            elif charge.kind == "service_charge":
                person_svc[person_id] += person_share
            elif charge.kind == "discount":
                # Discounts are negative — reduce what the person owes
                person_disc[person_id] -= person_share
            else:
                person_other[person_id] += person_share

    # ── Step 3: Raw totals + largest-remainder rounding ────────────────────────
    raw_totals: dict[str, Decimal] = {}
    for pid in person_ids:
        raw_totals[pid] = _q(
            person_item_total[pid]
            + person_tax[pid]
            + person_svc[pid]
            + person_disc[pid]
            + person_other[pid]
        )

    grand_sum = sum(raw_totals.values())
    rounding_adjustment = _q(authoritative_total - grand_sum)

    rounding_person_id: Optional[str] = None
    if rounding_adjustment != Decimal("0"):
        # Assign residual to the person with the largest raw total (deterministic)
        biggest = max(raw_totals, key=lambda k: raw_totals[k])
        raw_totals[biggest] += rounding_adjustment
        rounding_person_id = biggest

    # ── Step 4: Build output + assert ─────────────────────────────────────────
    breakdown_people: list[PersonBreakdown] = []
    for p in people:
        pid = p.id
        item_sub = person_item_total[pid]
        tax = person_tax[pid]
        svc = person_svc[pid]
        disc = person_disc[pid]
        other = person_other[pid]
        final = raw_totals[pid]

        # Human-readable formula hint
        parts = [f"Items ₹{item_sub}"]
        if tax != 0:
            parts.append(f"+ Tax ₹{tax}")
        if svc != 0:
            parts.append(f"+ Service ₹{svc}")
        if disc != 0:
            parts.append(f"− Discount ₹{abs(disc)}")
        if other != 0:
            parts.append(f"+ Fees ₹{other}")
        formula = " ".join(parts) + f" = ₹{final}"

        breakdown_people.append(
            PersonBreakdown(
                person_id=pid,
                name=p.name,
                items=person_items[pid],
                item_subtotal=item_sub,
                tax_share=tax,
                service_charge_share=svc,
                discount_share=disc,
                other_fee_share=other,
                final_total=final,
                formula_hint=formula,
            )
        )

    grand_total_check = sum(pb.final_total for pb in breakdown_people)

    # Strict assertion — this must always hold
    assert grand_total_check == authoritative_total, (
        f"Rounding error: grand_total_check={grand_total_check} "
        f"!= authoritative_total={authoritative_total}"
    )

    return BillBreakdown(
        bill_id=bill.bill_id,
        people=breakdown_people,
        grand_total_check=grand_total_check,
        rounding_adjustment=rounding_adjustment,
        rounding_adjusted_person_id=rounding_person_id,
        authoritative_total=authoritative_total,
    )
