from __future__ import annotations
import datetime as dt
import uuid
import random
from dataclasses import dataclass, field
from typing import List, Dict, Any

from src.schemas.ground_truth import GroundTruthTransaction, GroundTruthStore
from src.data_generation.discrepancies import (
    COUNTERPARTY_CATALOG,
    DiscrepancyInjector,
    DiscrepancyProfile,
)


@dataclass
class SyntheticDataset:
    """Container returned by the generator — consumed by scripts and tests."""

    ledger_records: List[Dict[str, Any]] = field(default_factory=list)
    bank_records: List[Dict[str, Any]] = field(default_factory=list)
    invoice_records: List[Dict[str, Any]] = field(default_factory=list)
    ground_truth_store: GroundTruthStore = field(default_factory=GroundTruthStore)


class SyntheticDataGenerator:
    """Generates reproducible multi-source financial data with realistic discrepancies."""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.injector = DiscrepancyInjector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, num_transactions: int = 60) -> SyntheticDataset:
        ds = SyntheticDataset()

        for i in range(num_transactions):
            vendor = self.rng.choice(COUNTERPARTY_CATALOG)
            canonical = vendor["canonical"]
            lo, hi = vendor["base_amount_range"]
            base_amount = round(self.rng.uniform(lo, hi), 2)
            base_currency = vendor["typical_currency"]
            base_date = dt.date(2024, 1, 1) + dt.timedelta(days=self.rng.randint(0, 364))
            category = vendor["category"]

            # Pick a discrepancy profile for this transaction
            profile = self._pick_profile(i, num_transactions)

            # Generate deterministic IDs derived from index and seed
            gt_id = f"GT-{i+1:04d}"
            ledger_id = f"L-{i+1:04d}"
            bank_id = f"B-{i+1:04d}"
            invoice_id = f"I-{i+1:04d}"

            # ---- Ledger record (always uses canonical name) ----
            ledger_date = base_date
            ledger_amount = base_amount
            ledger_name = canonical

            # ---- Bank record (may have timing lag, amount fee, name noise) ----
            bank_date = base_date
            bank_amount = base_amount
            bank_name = canonical
            bank_currency = base_currency

            if profile == DiscrepancyProfile.TIMING_LAG:
                bank_date = self.injector.inject_timing_lag(base_date, self.rng)
            elif profile == DiscrepancyProfile.AMOUNT_VARIANCE:
                bank_amount = self.injector.inject_amount_fee(base_amount, self.rng)
            elif profile == DiscrepancyProfile.NAME_NOISE:
                bank_name = self.injector.inject_name_variation(
                    canonical, vendor["variations"], self.rng
                )

            # Bank narrative always adds a small variation
            if profile != DiscrepancyProfile.NAME_NOISE:
                bank_name = self.rng.choice(
                    [canonical, canonical.upper(), canonical + " INC"]
                )

            # ---- Invoice record (may have timing lag in other direction) ----
            inv_date = base_date
            inv_amount = base_amount
            inv_name = canonical
            if self.rng.random() < 0.3:
                inv_date = base_date - dt.timedelta(days=self.rng.randint(1, 3))
            if self.rng.random() < 0.2:
                inv_name = self.rng.choice(vendor["variations"])

            # ---- Handle missing record (~8%) ----
            skip_ledger = False
            skip_bank = False
            skip_invoice = False
            if profile == DiscrepancyProfile.MISSING_RECORD:
                choice = self.rng.choice(["bank", "invoice"])
                if choice == "bank":
                    skip_bank = True
                else:
                    skip_invoice = True

            # ---- Build source_record_ids for ground truth ----
            source_ids: Dict[str, List[str]] = {}
            if not skip_ledger:
                source_ids["LEDGER"] = [ledger_id]
            if not skip_bank:
                source_ids["BANK"] = [bank_id]
            if not skip_invoice:
                source_ids["INVOICE"] = [invoice_id]

            # ---- Emit raw records ----
            if not skip_ledger:
                ds.ledger_records.append({
                    "ledger_id": ledger_id,
                    "posting_date": ledger_date.isoformat(),
                    "amount": str(ledger_amount),
                    "currency": base_currency,
                    "vendor_account": ledger_name,
                    "reference": f"REF-{gt_id[:8]}",
                    "entry_type": "DEBIT",
                })

            if not skip_bank:
                ds.bank_records.append({
                    "transaction_id": bank_id,
                    "value_date": bank_date.strftime("%m/%d/%Y"),
                    "settled_amount": str(bank_amount),
                    "currency_code": bank_currency,
                    "statement_narrative": bank_name,
                    "ref_code": f"REF-{gt_id[:8]}",
                    "direction": "OUT",
                })

            if not skip_invoice:
                ds.invoice_records.append({
                    "internal_invoice_id": invoice_id,
                    "invoice_date": inv_date.isoformat(),
                    "total_amount": str(inv_amount),
                    "billing_currency": base_currency,
                    "supplier_name": inv_name,
                    "invoice_number": f"INV-{self.rng.randint(10000, 99999)}",
                })

            # ---- Ground truth ----
            gt_tx = GroundTruthTransaction(
                gt_id=gt_id,
                date=base_date,
                base_amount=base_amount,
                base_currency=base_currency,
                canonical_counterparty=canonical,
                category=category,
                description=f"Synthetic tx #{i + 1}",
                source_record_ids=source_ids,
            )
            ds.ground_truth_store.add_transaction(gt_tx)

        # ---- Inject ~5% duplicates ----
        self._inject_duplicates(ds, num_transactions)

        return ds

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pick_profile(self, index: int, total: int) -> DiscrepancyProfile:
        """Deterministically assign discrepancy profiles so the mix is realistic."""
        missing_count = max(1, int(total * 0.08))
        name_noise_count = max(1, int(total * 0.15))
        timing_count = max(1, int(total * 0.20))
        amount_count = max(1, int(total * 0.12))

        if index < missing_count:
            return DiscrepancyProfile.MISSING_RECORD
        elif index < missing_count + name_noise_count:
            return DiscrepancyProfile.NAME_NOISE
        elif index < missing_count + name_noise_count + timing_count:
            return DiscrepancyProfile.TIMING_LAG
        elif index < missing_count + name_noise_count + timing_count + amount_count:
            return DiscrepancyProfile.AMOUNT_VARIANCE
        else:
            return DiscrepancyProfile.EXACT

    def _inject_duplicates(self, ds: SyntheticDataset, total: int) -> None:
        """Clone ~5% of bank records to simulate duplicates."""
        dup_count = max(1, int(total * 0.05))
        if not ds.bank_records:
            return
        for dup_idx in range(dup_count):
            original = self.rng.choice(ds.bank_records)
            dup = dict(original)
            dup["transaction_id"] = f"{original['transaction_id']}-DUP{dup_idx + 1}"
            ds.bank_records.append(dup)
