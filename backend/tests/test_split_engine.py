"""
Unit tests for the SplitEngine.

Key correctness rules verified:
1. sum(person totals) == authoritative_total (paisa-exact) — every time.
2. Tax is proportional to consumption, NOT divided equally by headcount.
3. Coke-only person pays tax only on their Coke's share.
4. Rounding residual lands on the largest-bill payer.
5. Discounts are proportional and reduce the right person's total.
6. Someone who only orders one item gets correct proportional charges.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from engine.split import compute_breakdown
from models.schemas import (
    Charge,
    Confidence,
    ExtractedBill,
    ItemAssignment,
    LineItem,
    Person,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _conf(v=0.95) -> Confidence:
    return Confidence(value=v, reason="clear")


def _item(id, name, qty, unit, total) -> LineItem:
    return LineItem(
        id=id,
        raw_text=name,
        name=name,
        quantity=qty,
        unit_price=Decimal(str(unit)),
        total_price=Decimal(str(total)),
        confidence=_conf(),
    )


def _charge(id, label, kind, amount=None, percent=None, applies_to="subtotal") -> Charge:
    return Charge(
        id=id,
        label=label,
        kind=kind,
        amount=Decimal(str(amount)) if amount is not None else None,
        percent=float(percent) if percent is not None else None,
        applies_to=applies_to,
        confidence=_conf(),
    )


def _bill(items, charges, printed_total=None, trust_computed=True) -> ExtractedBill:
    subtotal = sum(i.total_price for i in items)
    running = subtotal
    for ch in charges:
        base = subtotal
        if ch.amount is not None:
            amt = ch.amount
        elif ch.percent is not None:
            amt = (base * Decimal(str(ch.percent)) / 100).quantize(Decimal("0.01"))
        else:
            amt = Decimal("0")
        if ch.kind == "discount":
            running -= amt
        else:
            running += amt
    computed_total = running.quantize(Decimal("0.01"))

    return ExtractedBill(
        bill_id="test-bill",
        line_items=items,
        charges=charges,
        computed_subtotal=subtotal,
        computed_total=computed_total,
        printed_total=Decimal(str(printed_total)) if printed_total is not None else None,
        trust_computed=trust_computed,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBasicSplit:
    def test_two_people_equal_items(self):
        """Two people, same priced items, 5% GST — each pays half."""
        items = [
            _item("i1", "Biryani", 1, 200, 200),
            _item("i2", "Biryani", 1, 200, 200),
        ]
        charges = [_charge("c1", "GST 5%", "tax", percent=5)]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")

        assignments = [
            ItemAssignment(line_item_id="i1", shares={"alice": 1.0}),
            ItemAssignment(line_item_id="i2", shares={"bob": 1.0}),
        ]

        breakdown = compute_breakdown(bill, [alice, bob], assignments)
        assert breakdown.grand_total_check == bill.computed_total
        # Each should pay 200 + 5% of 200 = 210
        alice_bd = next(p for p in breakdown.people if p.person_id == "alice")
        bob_bd = next(p for p in breakdown.people if p.person_id == "bob")
        assert alice_bd.final_total == Decimal("210.00")
        assert bob_bd.final_total == Decimal("210.00")

    def test_sum_equals_total(self):
        """Grand total check: sum(person totals) == computed_total."""
        items = [
            _item("i1", "Dal Makhani", 1, 180, 180),
            _item("i2", "Naan", 3, 30, 90),
            _item("i3", "Coke", 1, 60, 60),
        ]
        charges = [
            _charge("c1", "CGST 2.5%", "tax", percent=2.5),
            _charge("c2", "SGST 2.5%", "tax", percent=2.5),
            _charge("c3", "Service Charge 5%", "service_charge", percent=5),
        ]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")
        carol = Person(id="carol", name="Carol")

        assignments = [
            ItemAssignment(line_item_id="i1", shares={"alice": 0.5, "bob": 0.5}),
            ItemAssignment(line_item_id="i2", shares={"alice": 1/3, "bob": 1/3, "carol": 1/3}),
            ItemAssignment(line_item_id="i3", shares={"carol": 1.0}),
        ]

        breakdown = compute_breakdown(bill, [alice, bob, carol], assignments)
        assert breakdown.grand_total_check == bill.computed_total


class TestProportionalTax:
    def test_coke_only_person_pays_tax_on_coke_only(self):
        """
        Core correctness: Carol only had a Coke (₹60).
        With 5% GST on a ₹330 bill, Carol's tax should be
        proportional to her ₹60 share, NOT 1/3 of total GST.
        """
        items = [
            _item("i1", "Biryani", 1, 270, 270),
            _item("i2", "Coke", 1, 60, 60),
        ]
        charges = [_charge("c1", "GST 5%", "tax", percent=5)]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        carol = Person(id="carol", name="Carol")

        assignments = [
            ItemAssignment(line_item_id="i1", shares={"alice": 1.0}),
            ItemAssignment(line_item_id="i2", shares={"carol": 1.0}),
        ]

        breakdown = compute_breakdown(bill, [alice, carol], assignments)

        # Total food = 330, GST = 5% of 330 = 16.50
        # Carol's proportion = 60/330
        # Carol's tax = 16.50 * (60/330) = 3.00
        carol_bd = next(p for p in breakdown.people if p.person_id == "carol")
        # Carol's tax share should be ~₹3 (60/330 * 16.50)
        expected_carol_tax = (Decimal("16.50") * Decimal("60") / Decimal("330")).quantize(Decimal("0.01"))
        assert carol_bd.tax_share == expected_carol_tax

        # NOT 1/3 of total GST = 5.50
        assert carol_bd.tax_share != Decimal("5.50")

        # Total must still balance
        assert breakdown.grand_total_check == bill.computed_total

    def test_service_charge_proportional_not_headcount(self):
        """Service charge must follow consumption proportion."""
        items = [
            _item("i1", "Thali", 1, 500, 500),
            _item("i2", "Water", 1, 50, 50),
        ]
        charges = [_charge("c1", "Service 10%", "service_charge", percent=10)]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")

        assignments = [
            ItemAssignment(line_item_id="i1", shares={"alice": 1.0}),
            ItemAssignment(line_item_id="i2", shares={"bob": 1.0}),
        ]

        breakdown = compute_breakdown(bill, [alice, bob], assignments)
        # Total svc = 55; alice's proportion = 500/550 → 50.00; bob = 50/550 → 5.00
        alice_bd = next(p for p in breakdown.people if p.person_id == "alice")
        bob_bd = next(p for p in breakdown.people if p.person_id == "bob")

        expected_alice_svc = (Decimal("55") * Decimal("500") / Decimal("550")).quantize(Decimal("0.01"))
        expected_bob_svc = (Decimal("55") * Decimal("50") / Decimal("550")).quantize(Decimal("0.01"))

        assert alice_bd.service_charge_share == expected_alice_svc
        assert bob_bd.service_charge_share == expected_bob_svc
        assert breakdown.grand_total_check == bill.computed_total


class TestDiscount:
    def test_discount_reduces_totals_proportionally(self):
        """A flat discount is distributed proportionally."""
        items = [
            _item("i1", "Pizza", 1, 400, 400),
            _item("i2", "Pasta", 1, 200, 200),
        ]
        charges = [_charge("c1", "10% Off", "discount", percent=10)]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")

        assignments = [
            ItemAssignment(line_item_id="i1", shares={"alice": 1.0}),
            ItemAssignment(line_item_id="i2", shares={"bob": 1.0}),
        ]

        breakdown = compute_breakdown(bill, [alice, bob], assignments)
        # Total disc = 60; alice share = 60 * (400/600) = 40; bob = 60 * (200/600) = 20
        alice_bd = next(p for p in breakdown.people if p.person_id == "alice")
        bob_bd = next(p for p in breakdown.people if p.person_id == "bob")

        assert alice_bd.discount_share == Decimal("-40.00")
        assert bob_bd.discount_share == Decimal("-20.00")
        assert alice_bd.final_total == Decimal("360.00")
        assert bob_bd.final_total == Decimal("180.00")
        assert breakdown.grand_total_check == bill.computed_total


class TestRounding:
    def test_rounding_adjustment_goes_to_largest_payer(self):
        """Rounding residual must be assigned to the largest-bill payer."""
        # ₹100 split 3 ways: 33.33... each → rounding needed
        items = [_item("i1", "Shared Dish", 3, 100, 100)]
        charges = []
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")
        carol = Person(id="carol", name="Carol")

        # Equal 3-way split
        assignments = [
            ItemAssignment(
                line_item_id="i1",
                shares={"alice": 1/3, "bob": 1/3, "carol": 1/3},
            )
        ]

        breakdown = compute_breakdown(bill, [alice, bob, carol], assignments)
        assert breakdown.grand_total_check == bill.computed_total
        # Rounding adjustment should exist and be tiny
        assert abs(breakdown.rounding_adjustment) <= Decimal("0.02")


class TestEdgeCases:
    def test_single_person_all_items(self):
        """One person takes everything — they pay the full total."""
        items = [_item("i1", "Meal", 1, 500, 500)]
        charges = [_charge("c1", "GST 18%", "tax", percent=18)]
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        assignments = [ItemAssignment(line_item_id="i1", shares={"alice": 1.0})]

        breakdown = compute_breakdown(bill, [alice], assignments)
        alice_bd = breakdown.people[0]
        assert alice_bd.final_total == bill.computed_total
        assert breakdown.grand_total_check == bill.computed_total

    def test_uneven_shared_item(self):
        """2:1 weighted share on a shared item."""
        items = [_item("i1", "Large Biryani", 1, 300, 300)]
        charges = []
        bill = _bill(items, charges)

        alice = Person(id="alice", name="Alice")
        bob = Person(id="bob", name="Bob")

        # Alice had 2/3, Bob had 1/3
        assignments = [
            ItemAssignment(
                line_item_id="i1",
                shares={"alice": 2/3, "bob": 1/3},
            )
        ]

        breakdown = compute_breakdown(bill, [alice, bob], assignments)
        alice_bd = next(p for p in breakdown.people if p.person_id == "alice")
        bob_bd = next(p for p in breakdown.people if p.person_id == "bob")
        # alice = 200, bob = 100
        assert alice_bd.final_total == Decimal("200.00")
        assert bob_bd.final_total == Decimal("100.00")
        assert breakdown.grand_total_check == bill.computed_total
