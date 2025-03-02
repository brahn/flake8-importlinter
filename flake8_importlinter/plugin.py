import os
import re
import sys
from typing import Generator, Tuple, Optional, List, TYPE_CHECKING, Any, Union
import logging

from importlinter.application.use_cases import _register_contract_types
from importlinter.domain.contract import ContractCheck

# For type checking only
if TYPE_CHECKING:
    from importlinter.application.ports.reporting import Report
    from importlinter.domain.contract import Violation

# Initialize importlinter configuration
try:
    from importlinter.application.use_cases import create_report, read_user_options
    from importlinter.application.ports.reporting import Report
    from importlinter.configuration import configure as importlinter_configure
    from importlinter.domain.contract import Violation

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
        # Don't proceed unless import-linter is available, configured, and we're
        # checking a Python file
        if not IMPORT_LINTER_AVAILABLE:
            return
        if not self.filename.endswith(".py"):
            return
        if err := ImportLinterPlugin._configuration_error:
            yield self._make_flake8_error(1, "IMP000", f"Error configuring import-linter: {err}")
            return

        try:
            original_path = list(sys.path)
            if self.project_root_dir not in sys.path:
                sys.path.insert(0, self.project_root_dir)

            # Get the module name corresponding to the file getting checked
            module_name = self._get_module_name(self.filename)
            if not module_name:
                return

            # Read the user options from the config file, create the report of contract checks
            user_options = read_user_options(config_filename=self.config_filepath)
            _register_contract_types(user_options)
            report = create_report(
                user_options,
                cache_dir=os.path.join(os.path.expanduser("~"), ".cache", "flake8-importlinter"),
            )

            yield from self._flake8_errors_for_module(report, module_name)

        except Exception as e:
            error_str = str(e)
            logger.exception(f"Error running import-linter: {error_str}")
            yield self._make_flake8_error(1, "IMP000", f"Error running import-linter: {error_str}")

        finally:
            # Restore the original Python path
            sys.path = original_path

    def _flake8_errors_for_module(self, report: "Report", module_name: str) -> list[tuple[int, int, str, type]]:
        """
        Args:
            report: The Report object from import-linter
            module_name: The module name for the current file

        Returns:
            Tuples of (line_number, column, message, type) for each violation
        """
        errors = []
        # Iterate through all contract checks in the report
        for contract, check in report.get_contracts_and_checks():
            for v in contract.violations(check):
                errors.extend(self._flake8_errors_for_violation(contract.name, v, module_name))
        return errors

    def _flake8_errors_for_violation(
        self, contract_name: str, violation: "Violation", module_name: str
    ) -> list[tuple[int, int, str, type]]:
        line_numbers = []
        for note in violation.import_notes:
            if note.module == module_name:
                line_numbers.extend(list(note.line_numbers))
        return [
            self._make_flake8_error(line_num, "IMP001", f"{contract_name}: {violation.summary}")
            for line_num in line_numbers
        ]

    def _make_flake8_error(self, line_num, code, msg) -> tuple[int, int, str, type]:
        return (line_num, 0, f"{code} {msg}", type(self))

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
