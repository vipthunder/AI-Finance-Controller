from __future__ import annotations
import sys
import os
import json
import csv
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_generation.generator import SyntheticDataGenerator


def main():
    root_dir = Path(__file__).parent.parent
    raw_dir = root_dir / "data" / "raw"
    gt_dir = root_dir / "data" / "ground_truth"

    raw_dir.mkdir(parents=True, exist_ok=True)
    gt_dir.mkdir(parents=True, exist_ok=True)

    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=60)

    def write_csv(filepath: Path, records: list[dict]):
        if not records:
            return
        keys = records[0].keys()
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(records)

    write_csv(raw_dir / "ledger.csv", dataset.ledger_records)
    write_csv(raw_dir / "bank.csv", dataset.bank_records)
    write_csv(raw_dir / "invoices.csv", dataset.invoice_records)

    # Serialize ground truth
    gt_data = {}
    for gt_id, tx in dataset.ground_truth_store._transactions.items():
        gt_data[gt_id] = {
            "gt_id": tx.gt_id,
            "date": tx.date.isoformat(),
            "base_amount": tx.base_amount,
            "base_currency": tx.base_currency,
            "canonical_counterparty": tx.canonical_counterparty,
            "category": tx.category,
            "description": tx.description,
            "source_record_ids": dict(tx.source_record_ids),
        }

    with open(gt_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump({"transactions": gt_data}, f, indent=2, default=str)

    print("Generation Complete:")
    print(f"  Ledger Records:  {len(dataset.ledger_records)}")
    print(f"  Bank Records:    {len(dataset.bank_records)}")
    print(f"  Invoice Records: {len(dataset.invoice_records)}")
    print(f"  Ground Truth:    {dataset.ground_truth_store.total_transactions}")


if __name__ == "__main__":
    main()
