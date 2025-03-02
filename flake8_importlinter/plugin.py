import os
import re
import sys
from typing import Generator, Tuple, Optional, List
import logging

from importlinter.application.use_cases import _register_contract_types


# Initialize importlinter configuration
try:
    from importlinter.application.use_cases import create_report, read_user_options
    from importlinter.application.ports.reporting import Report
    from importlinter.configuration import configure as importlinter_configure

    IMPORT_LINTER_AVAILABLE = True
except ImportError:
    IMPORT_LINTER_AVAILABLE = False

# Create a logger for our plugin
logger = logging.getLogger("flake8-importlinter plugin")


class ImportLinterPlugin:
    """
    Flake8 plugin for import-linter integration.

    This plugin runs import-linter on your project and reports any
    architecture violations as Flake8 errors, allowing them to appear
    directly in your editor.
    """

    name = "flake8-importlinter"
    version = __import__("flake8_importlinter").__version__

    # Class-level variable to track if we've tried to configure import-linter
    _configured = False
    _configuration_error = None

    def __init__(self, tree, filename, project_root_dir, config_filepath=None):
        """
        Initialize the plugin with the current file information.

        Args:
            _tree: AST tree of the file (required by Flake8 plugin interface, though we don't use it)
            filename: Path to the file being checked
            project_root_dir: Path to the project root directory. This will be added to the Python path
                             to ensure import-linter can resolve module names correctly.
            config_filepath: Path to the import-linter config file. If None,
                             import-linter will search for a config file.

        Note: Other import-linter options (limit_to_contracts, cache_dir,
              is_debug_mode, show_timings, verbose) are not yet implemented.
        """
        self.filename = filename
        self.project_root_dir = project_root_dir
        self.config_filepath = config_filepath
        if not IMPORT_LINTER_AVAILABLE:
            logger.warning("import-linter is not available")
            return
        self.setup_importlinter()

    def setup_importlinter(self):
        # Configure import-linter once per process
        if not ImportLinterPlugin._configured:
            try:
                importlinter_configure()
                ImportLinterPlugin._configured = True
            except Exception as e:
                logger.exception("Error configuring import-linter")
                ImportLinterPlugin._configuration_error = str(e)

    def run(self) -> Generator[Tuple[int, int, str, type], None, None]:
        """
        Run import-linter and yield any errors as Flake8 error messages.

        Yields:
            Tuples of (line_number, column, message, type) for each violation
        """
        if not IMPORT_LINTER_AVAILABLE:
            # Skip processing if import-linter is not installed
            return
        if not self.filename.endswith(".py"):
            # Only process Python files
            return
        if ImportLinterPlugin._configuration_error:
            # If there was a configuration error, report it and return
            yield (
                1,
                0,
                f"IMP000 Error configuring import-linter: {ImportLinterPlugin._configuration_error}",
                type(self),
            )
            return

        try:
            original_path = list(sys.path)
            if self.project_root_dir not in sys.path:
                sys.path.insert(0, self.project_root_dir)

            # Read the user options from the config file
            user_options = read_user_options(config_filename=self.config_filepath)
            _register_contract_types(user_options)

            # Create a report from the user options with caching
            report = create_report(
                user_options,
                cache_dir=os.path.join(os.path.expanduser("~"), ".cache", "flake8-importlinter"),
            )

            # Get the module name corresponding to this file
            module_name = self._get_module_name(self.project_root_dir)
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
            error_str = str(e)
            # Log the full stack trace
            logger.exception(f"Error running import-linter: {error_str}")
            yield (1, 0, f"IMP000 Error running import-linter: {error_str}", type(self))  # Report on first line

        finally:
            # Restore the original Python path
            sys.path = original_path

    def _get_module_name(self, project_root: str) -> Optional[str]:
        """
        Convert the current filename to a Python module name.

        Args:
            project_root: Path to the project root directory

        Returns:
            The Python module name for the current file, or None if not determinable
        """
        if not self.filename.endswith(".py"):
            return None

        # Find the relative path from the project root to this file
        rel_path = os.path.relpath(self.filename, project_root)

        # If the file is not under the project root, it's not part of the project
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
        - Contract violations are stored in ContractCheck.metadata for actual import-linter
          (though our test mocks have them directly as .violations)
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

            all_violations = check.metadata.get("violations", [])

            for violation in all_violations:
                violation_found = False

                # For contracts with direct importer/imported attributes (like ForbiddenContract)
                if hasattr(violation, "importer") and violation.importer == module_name:
                    line_num = self._get_line_number_from_violation(violation)
                    if line_num:
                        message = f"Forbidden import of {violation.imported}"
                        module_violations.append((line_num, message))
                        violation_found = True

                # For layers contract
                elif hasattr(violation, "higher_layer") and hasattr(violation, "lower_layer"):
                    # Check if the violation involves the current module
                    if module_name.startswith(violation.higher_layer):
                        higher_module = module_name
                        line_num = self._get_line_number_from_violation(violation)
                        if line_num:
                            message = (
                                f"Illegal import from higher layer {higher_module} to "
                                f"lower layer {violation.lower_layer}"
                            )
                            module_violations.append((line_num, message))
                            violation_found = True

                # For more complex violations (need to extract from string representation)
                if not violation_found and str(violation).startswith(f"{module_name} ->"):
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
