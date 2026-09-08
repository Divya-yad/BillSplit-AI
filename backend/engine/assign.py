"""
Assignment helper utilities for BillSplit AI.
Provides shortcut builders that all resolve to the same ItemAssignment shape.
"""
from __future__ import annotations

from models.schemas import ItemAssignment, Person


def solo_assignment(line_item_id: str, person_id: str) -> ItemAssignment:
    """Assign 100% of an item to one person."""
    return ItemAssignment(line_item_id=line_item_id, shares={person_id: 1.0})


def equal_split_assignment(line_item_id: str, person_ids: list[str]) -> ItemAssignment:
    """Split an item equally among a list of people."""
    if not person_ids:
        raise ValueError("Must specify at least one person for equal split.")
    n = len(person_ids)
    share = 1.0 / n
    return ItemAssignment(
        line_item_id=line_item_id,
        shares={pid: share for pid in person_ids},
    )


def everyone_assignment(
    line_item_id: str,
    people: list[Person],
    exclude_left_early: bool = True,
) -> ItemAssignment:
    """
    Assign an item to everyone at the table.
    By default, excludes people who left early.
    """
    eligible = [p for p in people if not (exclude_left_early and p.left_early)]
    if not eligible:
        raise ValueError("No eligible people for 'everyone' assignment (all left early?).")
    return equal_split_assignment(line_item_id, [p.id for p in eligible])


def weighted_assignment(
    line_item_id: str,
    weights: dict[str, float],
) -> ItemAssignment:
    """
    Assign an item with custom weights per person.
    Weights are normalised to sum to 1.0 automatically.
    E.g. {alice: 2, bob: 1} → alice gets 2/3, bob gets 1/3.
    """
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("Total weight must be positive.")
    normalised = {pid: w / total_weight for pid, w in weights.items()}
    return ItemAssignment(line_item_id=line_item_id, shares=normalised)


def validate_assignments(
    line_item_ids: list[str],
    assignments: list[ItemAssignment],
) -> list[str]:
    """
    Returns list of line_item_ids that have no assignment yet.
    Frontend uses this to gate the 'Continue' button.
    """
    assigned_ids = {a.line_item_id for a in assignments}
    return [lid for lid in line_item_ids if lid not in assigned_ids]
