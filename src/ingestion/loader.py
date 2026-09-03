from __future__ import annotations

import csv
from typing import Dict, List, Any


class DataLoader:
    """Loads raw data from various sources."""

    def load_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """Loads data from a CSV file."""
        data = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(dict(row))
        return data

    def load_from_dicts(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Pass-through for in-memory dictionaries."""
        return list(data)
