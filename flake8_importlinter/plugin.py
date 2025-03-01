import os
import re
import sys
from typing import Generator, Tuple, Any, Dict, Optional, List

try:
    from importlinter.application.use_cases import create_report, read_user_options
    from importlinter.application.user_options import UserOptions
    from importlinter.application.ports.reporting import Report
    from importlinter.configuration import configure

    # Initialize importlinter configuration
    configure()

    IMPORT_LINTER_AVAILABLE = True
except ImportError:
    IMPORT_LINTER_AVAILABLE = False


class ImportLinterPlugin:
    """
    Flake8 plugin for import-linter integration.

    This plugin runs import-linter on your project and reports any
    architecture violations as Flake8 errors, allowing them to appear
    directly in your editor.
    """

    name = "flake8-importlinter"
    version = __import__("flake8_importlinter").__version__

    def __init__(self, tree, filename):
        """Initialize the plugin with the current file information."""
        self.filename = filename
        self.tree = tree
        self._config_file = None

    def run(self) -> Generator[Tuple[int, int, str, type], None, None]:
        """
        Run import-linter and yield any errors as Flake8 error messages.

        Yields:
            Tuples of (line_number, column, message, type) for each violation
        """
        # Skip processing if import-linter is not installed
        if not IMPORT_LINTER_AVAILABLE:
            return

        # Only process Python files
        if not self.filename.endswith(".py"):
            return

        # Only process if we're in a project with import-linter config
        config_file = self._find_config_file()
        if not config_file:
            return

        try:
            # Read the user options from the config file
            user_options = read_user_options(config_filename=config_file)

            # Create a report from the user options with caching
            report = create_report(
                user_options,
                cache_dir=os.path.join(os.path.expanduser("~"), ".cache", "flake8-importlinter"),
            )

            # Get the module name corresponding to this file
            module_name = self._get_module_name(config_file)
            if not module_name:
                return

            # Extract violations for this module from the report
            for contract_name, violations in self._extract_violations(report, module_name):
                for line_num, message in violations:
                    yield (
                        line_num,
                        0,  # Column number (always 0 for architectural violations)
                        f"IMP001 {contract_name}: {message}",
                        type(self),
                    )

        except Exception as e:
            # Handle errors gracefully
            yield (1, 0, f"IMP000 Error running import-linter: {str(e)}", type(self))  # Report on first line

    def _find_config_file(self) -> Optional[str]:
        """
        Find the nearest import-linter config file in parent directories.

        Returns:
            Path to the config file, or None if not found
        """
        if self._config_file:
            return self._config_file

        current_dir = os.path.dirname(os.path.abspath(self.filename))
        while current_dir != os.path.dirname(current_dir):  # Stop at root
            for config_name in [".importlinter", "pyproject.toml"]:
                config_path = os.path.join(current_dir, config_name)
                if os.path.exists(config_path):
                    self._config_file = config_path
                    return config_path
            current_dir = os.path.dirname(current_dir)
        return None

    def _get_module_name(self, config_file: str) -> Optional[str]:
        """
        Convert the current filename to a Python module name.

        Args:
            config_file: Path to the import-linter config file

        Returns:
            The Python module name for the current file, or None if not determinable
        """
        if not self.filename.endswith(".py"):
            return None

        # Find the root package directory based on config location
        config_dir = os.path.dirname(config_file)
        rel_path = os.path.relpath(self.filename, config_dir)

        # If the file is not under the config directory, it's not part of the project
        if rel_path.startswith(".."):
            return None

        # Convert path to module name
        module_parts = []
        path_parts = os.path.dirname(rel_path).split(os.sep)
        for part in path_parts:
            if part and not part.startswith("."):
                module_parts.append(part)

        # Add the file name without .py extension
        basename = os.path.basename(self.filename)
        if basename != "__init__.py":
            module_parts.append(os.path.splitext(basename)[0])

        return ".".join(module_parts)

    def _extract_violations(self, report: Report, module_name: str) -> List[Tuple[str, List[Tuple[int, str]]]]:
        """
        Extract violations for the current module from the report.

        Reference to import-linter structure:
        - Report object contains ContractCheck objects
        - Each ContractCheck has a `kept` attribute (boolean)
        - Contract violations are exposed via ContractCheck.violations
        - Violations contain importer, imported, and line number information

        Args:
            report: The Report object from import-linter
            module_name: The module name for the current file

        Returns:
            List of (contract_name, violations) tuples, where violations is a
            list of (line_number, message) tuples.
        """
        violations = []

        # Iterate through all contract checks in the report
        for contract, check in report.get_contracts_and_checks():
            if check.kept:
                continue

            # Find violations specific to this module
            module_violations = []
            for violation in check.violations:
                # Match violations from the current module
                # The violation might have different structures depending on the contract type
                # We need to handle different contract types differently

                # For contracts with direct importer/imported attributes (like ForbiddenContract)
                if hasattr(violation, "importer") and violation.importer == module_name:
                    line_num = self._get_line_number_from_violation(violation)
                    if line_num:
                        message = f"Forbidden import of {violation.imported}"
                        module_violations.append((line_num, message))

                # For more complex violations (need to extract from string representation)
                elif str(violation).startswith(f"{module_name} ->"):
                    line_match = re.search(r"\(l\.(\d+)\)", str(violation))
                    if line_match:
                        line_num = int(line_match.group(1))
                        imported_match = re.search(r"-> ([\w\.]+)", str(violation))
                        imported = imported_match.group(1) if imported_match else "unknown module"
                        message = f"Forbidden import of {imported}"
                        module_violations.append((line_num, message))

            if module_violations:
                violations.append((contract.name, module_violations))

        return violations

    def _get_line_number_from_violation(self, violation) -> Optional[int]:
        """
        Extract the line number from a violation object.

        This handles different ways that line numbers might be stored:
        1. As a direct attribute (violation.line_number)
        2. In a line_numbers tuple (violation.line_numbers[0])
        3. In the string representation using a regex

        Args:
            violation: The violation object from import-linter

        Returns:
            The line number or None if it can't be determined
        """
        # Try direct line_number attribute
        if hasattr(violation, "line_number") and violation.line_number is not None:
            return violation.line_number

        # Try line_numbers tuple attribute
        if hasattr(violation, "line_numbers") and violation.line_numbers:
            if violation.line_numbers[0] is not None:
                return violation.line_numbers[0]

        # Try extracting from string representation
        line_match = re.search(r"\(l\.(\d+)\)", str(violation))
        if line_match:
            return int(line_match.group(1))

        # Default to first line if we can't find a line number
        return 1
