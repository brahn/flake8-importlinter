# Development Guide for flake8-importlinter

This document provides information for developing and contributing to the flake8-importlinter plugin.

## Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`
4. Install development dependencies: `pip install -e ".[dev]"`

## Testing

Run tests with pytest:

```bash
pytest
```

## Import-Linter Integration Details

This plugin interacts with import-linter using the following API points:

1. `use_cases.create_report()` - Returns a Report object containing contract checks
2. Report Object Structure:
   ```python
   # Reference to relevant Report class structure
   class Report:
       def __init__(self, graph, show_timings=False, graph_building_duration=None):
           self._check_map = {}
           self.graph = graph
           self.show_timings = show_timings
           self.graph_building_duration = graph_building_duration

       def get_contract_checks(self):
           # Returns tuples of (Contract, ContractCheck)
           return [(contract, check) for contract, check in self._check_map.items()]

       def add_contract_check(self, contract, check, duration=None):
           # Adds a contract check to the report
           self._check_map[contract] = check

       @property
       def contains_failures(self):
           # Returns True if any contracts are broken
           return any(not check.kept for check in self._check_map.values())
   ```

3. Contract Check Structure:
   ```python
   # Reference to ContractCheck structure
   class ContractCheck:
       def __init__(self, kept, violations=None, warnings=None):
           self.kept = kept
           self.violations = violations or []
           self.warnings = warnings or []
   ```

4. Violation Structure:
   Violations can have different structures depending on the contract type:
   ```python
   # Example for ForbiddenContract
   class ForbiddenImportViolation:
       def __init__(self, importer, imported, line_number, line_contents):
           self.importer = importer  # The importing module
           self.imported = imported  # The imported module
           self.line_number = line_number  # The line where the import occurs
           self.line_contents = line_contents  # The actual import statement
   ```

## Key Components

### 1. Finding the Configuration

The plugin searches for `.importlinter` or `pyproject.toml` files in parent directories to identify import-linter projects.

### 2. Module Name Resolution

We convert filenames to Python module names to match against the violations reported by import-linter.

### 3. Processing the Report

We extract violations from the Report object that are specific to the current file, and convert them to Flake8 error messages.

### 4. Line Number Extraction

We extract line numbers from violations to report errors at the exact location of problematic imports.

## Common Challenges

1. **Different Contract Types**: Different contract types might structure their violations differently. The plugin attempts to handle these variations.

2. **Module Name Resolution**: Converting between file paths and module names can be tricky, especially with complex package structures.

3. **Caching**: We use import-linter's built-in caching to improve performance, but this might need tuning for large projects.
