from __future__ import annotations
import os
import ast
import pytest


PRODUCTION_DIRS = [
    "src/ingestion",
    "src/matching",
    "src/pipeline",
    "src/validation",
    "src/controller",
    "src/verification",
    "src/investigation",
    "src/audit",
]

FORBIDDEN_MODULE_PREFIXES = [
    "src.schemas.ground_truth",
    "src.data_generation",
    "src.evaluation",
]

FORBIDDEN_SYMBOLS = [
    "GroundTruthStore",
    "GroundTruthTransaction",
    "SyntheticDataGenerator",
    "Evaluator",
]


def get_production_py_files():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    py_files = []
    for prod_dir in PRODUCTION_DIRS:
        full_dir = os.path.join(base_dir, prod_dir.replace("/", os.sep))
        if os.path.exists(full_dir):
            for root, _, files in os.walk(full_dir):
                for f in files:
                    if f.endswith(".py"):
                        py_files.append(os.path.join(root, f))
    return py_files


class ImportBoundaryChecker(ast.NodeVisitor):
    def __init__(self, filename: str):
        self.filename = filename
        self.violations = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            for forbidden in FORBIDDEN_MODULE_PREFIXES:
                if alias.name.startswith(forbidden):
                    self.violations.append(
                        f"{self.filename}:{node.lineno}: Imports forbidden module '{alias.name}'"
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        mod = node.module or ""
        for forbidden in FORBIDDEN_MODULE_PREFIXES:
            if mod.startswith(forbidden):
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Imports from forbidden module '{mod}'"
                )
        for alias in node.names:
            if alias.name in FORBIDDEN_SYMBOLS:
                self.violations.append(
                    f"{self.filename}:{node.lineno}: Imports forbidden symbol '{alias.name}'"
                )
        self.generic_visit(node)


def test_production_modules_ground_truth_isolation():
    """Verify that no production module imports ground truth, evaluator, or synthetic data generator."""
    py_files = get_production_py_files()
    assert len(py_files) > 0, "No production files found to inspect"

    all_violations = []
    for fpath in py_files:
        with open(fpath, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=fpath)
            checker = ImportBoundaryChecker(fpath)
            checker.visit(tree)
            all_violations.extend(checker.violations)

    assert len(all_violations) == 0, (
        f"Ground-truth isolation boundary violated in production modules:\n"
        + "\n".join(all_violations)
    )
