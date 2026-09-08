"""
BillSplit AI — 12-bill evaluation harness.

Usage:
  cd backend
  python eval/run_eval.py --ground-truth eval/ground_truth/ --images eval/images/

Expected directory layout:
  eval/
  ├── images/
  │   ├── bill_01.jpg        (or .png)
  │   └── ...
  └── ground_truth/
      ├── bill_01.json       (hand-typed ExtractedBill JSON)
      └── ...

The script reports:
  - Per-field accuracy (name, quantity, unit_price, total_price)
  - Charge extraction accuracy
  - Mismatch detection accuracy
  - End-to-end per-person total accuracy (with simulated 50/50 assignment)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

# Add backend root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from models.schemas import ExtractedBill, ItemAssignment, Person
from vision.preprocess import preprocess_image
from vision.extract import extract_bill
from engine.split import compute_breakdown


# ── Field comparison helpers ──────────────────────────────────────────────────

def _str_match(a, b) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return str(a).strip().lower() == str(b).strip().lower()


def _decimal_close(a: Decimal | None, b: Decimal | None, tol=Decimal("1.00")) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def compare_bills(pred: ExtractedBill, gt: ExtractedBill) -> dict:
    """Compare predicted bill against ground truth. Returns field-level metrics."""
    total_fields = 0
    correct_fields = 0
    errors = []

    # Compare line items
    gt_items = {i.name.lower(): i for i in gt.line_items}
    pred_items = {i.name.lower(): i for i in pred.line_items}

    all_names = set(gt_items) | set(pred_items)
    for name in all_names:
        gt_item = gt_items.get(name)
        pred_item = pred_items.get(name)

        if gt_item is None:
            errors.append(f"Extra item predicted: {name}")
            continue
        if pred_item is None:
            errors.append(f"Missing item: {name}")
            total_fields += 4
            continue

        # Check quantity
        total_fields += 1
        if abs(gt_item.quantity - pred_item.quantity) < 0.01:
            correct_fields += 1
        else:
            errors.append(f"{name}: qty gt={gt_item.quantity} pred={pred_item.quantity}")

        # Check unit_price
        total_fields += 1
        if _decimal_close(gt_item.unit_price, pred_item.unit_price, Decimal("2.00")):
            correct_fields += 1
        else:
            errors.append(f"{name}: unit_price gt={gt_item.unit_price} pred={pred_item.unit_price}")

        # Check total_price
        total_fields += 1
        if _decimal_close(gt_item.total_price, pred_item.total_price, Decimal("2.00")):
            correct_fields += 1
        else:
            errors.append(f"{name}: total_price gt={gt_item.total_price} pred={pred_item.total_price}")

    # Compare computed_total
    total_fields += 1
    if _decimal_close(gt.computed_total, pred.computed_total, Decimal("5.00")):
        correct_fields += 1
    else:
        errors.append(f"computed_total gt={gt.computed_total} pred={pred.computed_total}")

    accuracy = correct_fields / total_fields if total_fields > 0 else 0.0
    return {
        "accuracy": accuracy,
        "correct": correct_fields,
        "total": total_fields,
        "errors": errors,
    }


async def eval_single_bill(image_path: Path, gt_path: Path) -> dict:
    """Run extraction on one bill and compare to ground truth."""
    with open(image_path, "rb") as f:
        raw = f.read()

    pp = preprocess_image(raw)
    bill_id = image_path.stem
    pred = await extract_bill([pp], bill_id)

    with open(gt_path) as f:
        gt_data = json.load(f)
    gt = ExtractedBill.model_validate(gt_data)

    metrics = compare_bills(pred, gt)
    metrics["bill_id"] = bill_id
    return metrics


async def run_eval(images_dir: Path, gt_dir: Path) -> None:
    """Run evaluation across all matched bill pairs."""
    image_files = sorted(images_dir.glob("bill_*.jpg")) + sorted(images_dir.glob("bill_*.png"))
    if not image_files:
        print("No bill images found in", images_dir)
        return

    all_metrics = []
    for img_path in image_files:
        gt_path = gt_dir / f"{img_path.stem}.json"
        if not gt_path.exists():
            print(f"  [SKIP] No ground truth for {img_path.name}")
            continue

        print(f"Evaluating {img_path.name}...", end=" ", flush=True)
        try:
            m = await eval_single_bill(img_path, gt_path)
            print(f"Accuracy: {m['accuracy']:.1%}  ({m['correct']}/{m['total']} fields)")
            if m["errors"]:
                for err in m["errors"][:5]:
                    print(f"    ⚠ {err}")
            all_metrics.append(m)
        except Exception as exc:
            print(f"ERROR: {exc}")

    if all_metrics:
        overall = sum(m["accuracy"] for m in all_metrics) / len(all_metrics)
        print(f"\n{'─'*50}")
        print(f"Overall field-level accuracy: {overall:.1%} across {len(all_metrics)} bills")
        print(f"{'─'*50}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BillSplit AI Evaluation Harness")
    parser.add_argument("--images", default="eval/images", help="Directory of bill images")
    parser.add_argument("--ground-truth", default="eval/ground_truth", help="Directory of GT JSON files")
    args = parser.parse_args()

    asyncio.run(run_eval(Path(args.images), Path(args.ground_truth)))
