"""
Integration tests for flake8-importlinter.

These tests verify that the plugin works with actual import-linter contracts.
"""

import os
import shutil
import sys
from pathlib import Path
from unittest import mock

import pytest  # noqa: F401 - used for fixtures
from importlinter.adapters.filesystem import FileSystem

from flake8_importlinter.plugin import ImportLinterPlugin

# Adding the integration test directory to path
sys.path.append(str(Path(__file__).parent))


class TestIntegration:
    """Integration tests for the flake8-importlinter plugin."""

    def setup_method(self):
        """Set up the test environment."""
        # Get the path to the integration test directory
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.integration_dir = os.path.join(current_dir, "integration")

        # Add integration dir to path so import-linter can find modules
        if self.integration_dir not in sys.path:
            sys.path.append(self.integration_dir)

        # Patch FileSystem.getcwd to return the integration directory
        self.filesystem_patcher = mock.patch.object(FileSystem, "getcwd", return_value=self.integration_dir)
        self.mock_getcwd = self.filesystem_patcher.start()

    def teardown_method(self):
        """Clean up after the test."""
        # Remove integration dir from path
        if self.integration_dir in sys.path:
            sys.path.remove(self.integration_dir)

        # Stop the FileSystem.getcwd patch
        self.filesystem_patcher.stop()
        if os.path.exists(self._config_filepath()):
            os.remove(self._config_filepath())

    def _config_filepath(self):
        return os.path.join(self.integration_dir, ".importlinter")

    def test_forbidden_contract(self):
        """Test the plugin with a forbidden contract."""
        shutil.copy(
            os.path.join(self.integration_dir, ".importlinter.forbidden_contract"),
            self._config_filepath(),
        )

        # Run the plugin and collect any errors
        module_path = os.path.join(self.integration_dir, "mypackage", "high", "module_a.py")
        plugin = ImportLinterPlugin(
            tree=None,
            filename=module_path,
        )
        errors = list(plugin.run())

        # Check that we got one error with the expected format
        msg = f"Expected 1 error, got {len(errors)}: {errors}"
        assert len(errors) == 1, msg
        line, col, message, instance = errors[0]

        # Import is on line 2, import-linter might report line 1
        line_msg = f"Expected line 1 or 2, got {line}"
        assert line in (1, 2), line_msg

        assert col == 0
        assert "IMP001" in message
        assert "No direct imports from lower layers" in message
        assert "mypackage.high is not allowed to import mypackage.low" in message

    def test_layers_contract(self):
        """Test the plugin with a layers contract."""
        shutil.copy(
            os.path.join(self.integration_dir, ".importlinter.layers_contract"),
            self._config_filepath(),
        )

        # Run the plugin and collect any errors
        module_path = os.path.join(self.integration_dir, "mypackage", "low", "module_c.py")
        plugin = ImportLinterPlugin(
            tree=None,
            filename=module_path,
        )
        errors = list(plugin.run())

        # Check that we got at least one error with the expected format
        msg = f"Expected at least 1 error, got {len(errors)}: {errors}"
        assert len(errors) >= 1, msg

        # Check the first error
        line, col, message, instance = errors[0]
        assert col == 0
        assert "IMP001" in message
        assert "Layer boundaries" in message
        assert "mypackage.low is not allowed to import mypackage.high" in message
