from __future__ import annotations
from src.data_generation.generator import SyntheticDataGenerator, SyntheticDataset


def test_data_generation_init():
    gen = SyntheticDataGenerator()
    assert gen is not None


def test_data_generation_produces_dataset():
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=10)
    assert isinstance(dataset, SyntheticDataset)
    assert len(dataset.ledger_records) > 0
    assert len(dataset.bank_records) > 0
    assert len(dataset.invoice_records) > 0
    assert dataset.ground_truth_store.total_transactions == 10


def test_data_generation_reproducible():
    gen1 = SyntheticDataGenerator(seed=42)
    ds1 = gen1.generate(10)
    gen2 = SyntheticDataGenerator(seed=42)
    ds2 = gen2.generate(10)
    assert len(ds1.ledger_records) == len(ds2.ledger_records)
    assert len(ds1.bank_records) == len(ds2.bank_records)


def test_data_generation_has_discrepancies():
    gen = SyntheticDataGenerator(seed=42)
    dataset = gen.generate(num_transactions=60)
    # Should have ~5% duplicates in bank (60 * 0.05 = 3)
    assert len(dataset.bank_records) > 60
    # Should have ~8% missing in some source (60 * 0.08 ≈ 5 missing)
    assert len(dataset.invoice_records) < 60 or len(dataset.bank_records) != len(dataset.ledger_records)
