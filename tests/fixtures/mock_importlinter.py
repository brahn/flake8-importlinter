"""
Mock objects that replicate import-linter's structure for testing.
These are based on the actual import-linter implementation.
"""

from typing import List, Optional, Tuple, Any


class MockViolation:
    """Mock violation object that mimics import-linter's violations."""

    def __init__(self, importer: str, imported: str, line_number: int, line_contents: Optional[str] = None):
        self.importer = importer
        self.imported = imported
        self.line_number = line_number
        self.line_contents = line_contents or f"import {imported}"
        self.line_numbers = (line_number,) if line_number else None

    def __str__(self) -> str:
        return f"{self.importer} -> {self.imported} (l.{self.line_number})"


class MockContractCheck:
    """Mock contract check object that mimics import-linter's ContractCheck."""

    def __init__(
        self, kept: bool, violations: Optional[List[MockViolation]] = None, warnings: Optional[List[str]] = None
    ):
        self.kept = kept
        self.violations = violations or []
        self.warnings = warnings or []

    @property
    def metadata(self) -> dict:
        """Return a dictionary with violations, matching the structure expected by the plugin."""
        return {"violations": self.violations}


class MockContract:
    """Mock contract object that mimics import-linter's Contract."""

    def __init__(self, name: str, contract_type: str = "forbidden"):
        self.name = name
        self.type = contract_type


class MockReport:
    """Mock report object that mimics import-linter's Report."""

    def __init__(self, contract_checks: Optional[List[Tuple[MockContract, MockContractCheck]]] = None):
        self._contract_checks = contract_checks or []

    def get_contracts_and_checks(self) -> List[Tuple[MockContract, MockContractCheck]]:
        return self._contract_checks

    @property
    def contains_failures(self) -> bool:
        return any(not check.kept for _, check in self._contract_checks)


class MockGraph:
    """Mock graph object that mimics import-linter's ImportGraph."""

    def __init__(self, modules: Optional[List[str]] = None, imports: Optional[List[Tuple[str, str]]] = None):
        self.modules = modules or []
        self.imports = imports or []

    def get_modules(self) -> List[str]:
        return self.modules

    def count_imports(self) -> int:
        return len(self.imports)
